#!/usr/bin/env python

'''Stimulus object for drawing arbitrary bitmaps that can repeat (cycle) in either dimension
One of the main stimuli for PsychoPy'''

# Part of the PsychoPy library
# Copyright (C) 2013 Jonathan Peirce
# Distributed under the terms of the GNU General Public License (GPL).

# Ensure setting pyglet.options['debug_gl'] to False is done prior to any
# other calls to pyglet or pyglet submodules, otherwise it may not get picked
# up by the pyglet GL engine and have no effect.
# Shaders will work but require OpenGL2.0 drivers AND PyOpenGL3.0+
import pyglet
pyglet.options['debug_gl'] = False
import ctypes
GL = pyglet.gl

import psychopy  # so we can get the __path__
from psychopy import logging

from psychopy.tools.arraytools import val2array
from psychopy.tools.attributetools import attributeSetter
from psychopy.visual.basevisual import BaseVisualStim
from psychopy.visual.helpers import createTexture

import numpy


class GratingStim(BaseVisualStim):
    """Stimulus object for drawing arbitrary bitmaps that can repeat (cycle) in either dimension
    One of the main stimuli for PsychoPy.

    Formally GratingStim is just a texture behind an optional
    transparency mask (an 'alpha mask'). Both the texture and mask can be
    arbitrary bitmaps and their combination allows an enormous variety of
    stimuli to be drawn in realtime.

    **Examples**::

        myGrat = GratingStim(tex='sin',mask='circle') #gives a circular patch of grating
        myGabor = GratingStim(tex='sin',mask='gauss') #gives a 'Gabor'

    A GratingStim can be rotated scaled and shifted in position, its texture can
    be drifted in X and/or Y and it can have a spatial frequency in X and/or Y
    (for an image file that simply draws multiple copies in the patch).

    Also since transparency can be controlled two GratingStims can combine e.g.
    to form a plaid.

    **Using GratingStim with images from disk (jpg, tif, png...)**

    Ideally texture images to be rendered should be square with 'power-of-2' dimensions
    e.g. 16x16, 128x128. Any image that is not will be upscaled (with linear interpolation)
    to the nearest such texture by PsychoPy. The size of the stimulus should be
    specified in the normal way using the appropriate units (deg, pix, cm...). Be
    sure to get the aspect ratio the same as the image (if you don't want it
    stretched!).

    """
    def __init__(self,
                 win,
                 tex="sin",
                 mask="none",
                 units="",
                 pos=(0.0, 0.0),
                 size=None,
                 sf=None,
                 ori=0.0,
                 phase=(0.0, 0.0),
                 texRes=128,
                 rgb=None,
                 dkl=None,
                 lms=None,
                 color=(1.0, 1.0, 1.0),
                 colorSpace='rgb',
                 contrast=1.0,
                 opacity=1.0,
                 depth=0,
                 rgbPedestal=(0.0, 0.0, 0.0),
                 interpolate=False,
                 name='',
                 autoLog=True,
                 autoDraw=False,
                 maskParams=None):
        """
        :Parameters:

            texRes:
                resolution of the texture (if not loading from an image file)

            maskParams: Various types of input. Default to None.
                This is used to pass additional parameters to the mask if those
                are needed.
                - For the 'raisedCos' mask, pass a dict: {'fringeWidth':0.2},
                where 'fringeWidth' is a parameter (float, 0-1), determining
                the proportion of the patch that will be blurred by the raised
                cosine edge.

        """
        BaseVisualStim.__init__(self, win, units=units, name=name, autoLog=autoLog)
        self.useShaders = win._haveShaders  #use shaders if available by default, this is a good thing

        # UGLY HACK: Some parameters depend on each other for processing.
        # They are set "superficially" here.
        # TO DO: postpone calls to createTexture, setColor and _calcCyclesPerStim whin initiating stimulus
        self.__dict__['contrast'] = 1
        self.__dict__['size'] = 1
        self.__dict__['sf'] = 1
        self.__dict__['tex'] = tex

        #initialise textures and masks for stimulus
        self._texID = GL.GLuint()
        GL.glGenTextures(1, ctypes.byref(self._texID))
        self._maskID = GL.GLuint()
        GL.glGenTextures(1, ctypes.byref(self._maskID))
        self.texRes = texRes  #must be power of 2
        self.maskParams = maskParams
        self.interpolate = interpolate

        #NB Pedestal isn't currently being used during rendering - this is a place-holder
        self.rgbPedestal = val2array(rgbPedestal, False, length=3)
        self.__dict__['colorSpace'] = colorSpace  # No need to invoke decorator for color updating. It is done just below.
        if rgb != None:
            logging.warning("Use of rgb arguments to stimuli are deprecated. Please use color and colorSpace args instead")
            self.setColor(rgb, colorSpace='rgb', log=False)
        elif dkl != None:
            logging.warning("Use of dkl arguments to stimuli are deprecated. Please use color and colorSpace args instead")
            self.setColor(dkl, colorSpace='dkl', log=False)
        elif lms != None:
            logging.warning("Use of lms arguments to stimuli are deprecated. Please use color and colorSpace args instead")
            self.setColor(lms, colorSpace='lms', log=False)
        else:
            self.setColor(color, colorSpace=colorSpace, log=False)

        # set other parameters
        self.ori = float(ori)
        self.phase = val2array(phase, False)
        self._origSize = None  #if an image texture is loaded this will be updated
        self._requestedSize = size
        self.size = val2array(size)
        self.sf = val2array(sf)
        self.pos = val2array(pos, False, False)
        self.depth = depth

        self.tex = tex
        self.mask = mask
        self.contrast = float(contrast)
        self.opacity = float(opacity)
        self.autoLog = autoLog
        self.autoDraw = autoDraw

        #fix scaling to window coords
        self._calcPosRendered()
        self._calcCyclesPerStim()

        #generate a displaylist ID
        self._listID = GL.glGenLists(1)
        self._updateList()#ie refresh display list


    @attributeSetter
    def sf(self, value):
        """
        :ref:`x,y-pair <attrib-xy>` or :ref:`scalar <attrib-scalar>`
        Where `units` == 'deg' or 'cm' units are in cycles per deg/cm.
        If `units` == 'norm' then sf units are in cycles per stimulus (so scale with stimulus size).
        If texture is an image loaded from a file then sf defaults to 1/stim size to give one cycle of the image.

        Spatial frequency.
        """

        # Recode phase to numpy array
        if value == None:
            """Set the sf to default (e.g. to the 1.0/size of the loaded image etc)"""
            if self.units in ['pix', 'pixels'] \
                or self._origSize is not None and self.units in ['deg', 'cm']:
                value = 1.0 / self.size  #default to one cycle
            else:
                value = numpy.array([1.0, 1.0])
        else:
            value = val2array(value)

        # Set value and update stuff
        self.__dict__['sf'] = value
        self._calcCyclesPerStim()
        self._needUpdate = True

    @attributeSetter
    def phase(self, value):
        """
        :ref:`x,y-pair <attrib-xy>` or :ref:`scalar <attrib-scalar>`

        Phase of the stimulus in each direction.
        **NB** phase has modulus 1 (rather than 360 or 2*pi)
        This is a little unconventional but has the nice effect
        that setting phase=t*n drifts a stimulus at n Hz
        """
        # Recode phase to numpy array
        value = val2array(value)
        self.__dict__['phase'] = value
        self._needUpdate = True

    @attributeSetter
    def tex(self, value):
        """
        + **'sin'**,'sqr', 'saw', 'tri', None (resets to default)
        + or the name of an image file (most formats supported)
        + or a numpy array (1xN or NxN) ranging -1:1

        The texture forming the image
        """
        createTexture(value, id=self._texID, pixFormat=GL.GL_RGB, stim=self,
            res=self.texRes, maskParams=self.maskParams)
        #if user requested size=None then update the size for new stim here
        if hasattr(self, '_requestedSize') and self._requestedSize == None:
            self.size = None  # Reset size do default
        self.__dict__['tex'] = value

    @attributeSetter
    def mask(self, value):
        """
        + 'circle', 'gauss', 'raisedCos', **None** (resets to default)
        + or the name of an image file (most formats supported)
        + or a numpy array (1xN or NxN) ranging -1:1

            The alpha mask (forming the shape of the image)
        """
        createTexture(value, id=self._maskID, pixFormat=GL.GL_ALPHA, stim=self,
            res=self.texRes, maskParams=self.maskParams)
        self.__dict__['mask'] = value

    def setSF(self, value, operation='', log=True):
        """ Deprication Warning! Use 'stim.parameter = value' syntax instead"""
        self._set('sf', value, operation, log=log)
    def setPhase(self, value, operation='', log=True):
        """ Deprication Warning! Use 'stim.parameter = value' syntax instead"""
        self._set('phase', value, operation, log=log)
    def setTex(self, value, log=True):
        """ Deprication Warning! Use 'stim.parameter = value' syntax instead"""
        self.tex = value
    def setMask(self, value, log=True):
        """ Deprication Warning! Use 'stim.parameter = value' syntax instead"""
        self.mask = value

    def draw(self, win=None):
        """
        Draw the stimulus in its relevant window. You must call
        this method after every MyWin.flip() if you want the
        stimulus to appear on that frame and then update the screen
        again.
        """
        if win==None: win=self.win
        self._selectWindow(win)

        #do scaling
        GL.glPushMatrix()#push before the list, pop after
        win.setScale(self._winScale)
        #move to centre of stimulus and rotate
        GL.glTranslatef(self._posRendered[0],self._posRendered[1],0)
        GL.glRotatef(-self.ori,0.0,0.0,1.0)
        #the list just does the texture mapping

        desiredRGB = self._getDesiredRGB(self.rgb, self.colorSpace, self.contrast)
        GL.glColor4f(desiredRGB[0],desiredRGB[1],desiredRGB[2], self.opacity)

        if self._needUpdate:
            self._updateList()
        GL.glCallList(self._listID)

        #return the view to previous state
        GL.glPopMatrix()

    def _updateListShaders(self):
        """
        The user shouldn't need this method since it gets called
        after every call to .set() Basically it updates the OpenGL
        representation of your stimulus if some parameter of the
        stimulus changes. Call it if you change a property manually
        rather than using the .set() command
        """
        self._needUpdate = False
        GL.glNewList(self._listID,GL.GL_COMPILE)
        #setup the shaderprogram
        GL.glUseProgram(self.win._progSignedTexMask)
        GL.glUniform1i(GL.glGetUniformLocation(self.win._progSignedTexMask, "texture"), 0) #set the texture to be texture unit 0
        GL.glUniform1i(GL.glGetUniformLocation(self.win._progSignedTexMask, "mask"), 1)  # mask is texture unit 1
        #mask
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._maskID)
        GL.glEnable(GL.GL_TEXTURE_2D)#implicitly disables 1D

        #main texture
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texID)
        GL.glEnable(GL.GL_TEXTURE_2D)
        #calculate coords in advance:
        L = -self._sizeRendered[0]/2#vertices
        R =  self._sizeRendered[0]/2
        T =  self._sizeRendered[1]/2
        B = -self._sizeRendered[1]/2
        #depth = self.depth

        Ltex = -self._cycles[0]/2 - self.phase[0]+0.5
        Rtex = +self._cycles[0]/2 - self.phase[0]+0.5
        Ttex = +self._cycles[1]/2 - self.phase[1]+0.5
        Btex = -self._cycles[1]/2 - self.phase[1]+0.5
        Lmask=Bmask= 0.0; Tmask=Rmask=1.0#mask

        GL.glBegin(GL.GL_QUADS)                  # draw a 4 sided polygon
        # right bottom
        GL.glMultiTexCoord2f(GL.GL_TEXTURE0,Rtex, Btex)
        GL.glMultiTexCoord2f(GL.GL_TEXTURE1,Rmask,Bmask)
        GL.glVertex2f(R,B)
        # left bottom
        GL.glMultiTexCoord2f(GL.GL_TEXTURE0,Ltex,Btex)
        GL.glMultiTexCoord2f(GL.GL_TEXTURE1,Lmask,Bmask)
        GL.glVertex2f(L,B)
        # left top
        GL.glMultiTexCoord2f(GL.GL_TEXTURE0,Ltex,Ttex)
        GL.glMultiTexCoord2f(GL.GL_TEXTURE1,Lmask,Tmask)
        GL.glVertex2f(L,T)
        # right top
        GL.glMultiTexCoord2f(GL.GL_TEXTURE0,Rtex,Ttex)
        GL.glMultiTexCoord2f(GL.GL_TEXTURE1,Rmask,Tmask)
        GL.glVertex2f(R,T)
        GL.glEnd()

        #unbind the textures
        GL.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glDisable(GL.GL_TEXTURE_2D)#implicitly disables 1D
        #main texture
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glDisable(GL.GL_TEXTURE_2D)

        GL.glUseProgram(0)

        GL.glEndList()

    #for the sake of older graphics cards------------------------------------
    def _updateListNoShaders(self):
        """
        The user shouldn't need this method since it gets called
        after every call to .set() Basically it updates the OpenGL
        representation of your stimulus if some parameter of the
        stimulus changes. Call it if you change a property manually
        rather than using the .set() command
        """
        self._needUpdate = False

        GL.glNewList(self._listID,GL.GL_COMPILE)
        GL.glColor4f(1.0,1.0,1.0,1.0)#glColor can interfere with multitextures
        #mask
        GL.glActiveTextureARB(GL.GL_TEXTURE1_ARB)
        GL.glEnable(GL.GL_TEXTURE_2D)#implicitly disables 1D
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._maskID)

        #main texture
        GL.glActiveTextureARB(GL.GL_TEXTURE0_ARB)
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texID)
        #calculate coords in advance:
        L = -self._sizeRendered[0]/2#vertices
        R =  self._sizeRendered[0]/2
        T =  self._sizeRendered[1]/2
        B = -self._sizeRendered[1]/2
        #depth = self.depth
        Ltex = -self._cycles[0]/2 - self.phase[0]+0.5
        Rtex = +self._cycles[0]/2 - self.phase[0]+0.5
        Ttex = +self._cycles[1]/2 - self.phase[1]+0.5
        Btex = -self._cycles[1]/2 - self.phase[1]+0.5
        Lmask=Bmask= 0.0; Tmask=Rmask=1.0#mask

        GL.glBegin(GL.GL_QUADS)                  # draw a 4 sided polygon
        # right bottom
        GL.glMultiTexCoord2fARB(GL.GL_TEXTURE0_ARB,Rtex, Btex)
        GL.glMultiTexCoord2fARB(GL.GL_TEXTURE1_ARB,Rmask,Bmask)
        GL.glVertex2f(R,B)
        # left bottom
        GL.glMultiTexCoord2fARB(GL.GL_TEXTURE0_ARB,Ltex,Btex)
        GL.glMultiTexCoord2fARB(GL.GL_TEXTURE1_ARB,Lmask,Bmask)
        GL.glVertex2f(L,B)
        # left top
        GL.glMultiTexCoord2fARB(GL.GL_TEXTURE0_ARB,Ltex,Ttex)
        GL.glMultiTexCoord2fARB(GL.GL_TEXTURE1_ARB,Lmask,Tmask)
        GL.glVertex2f(L,T)
        # right top
        GL.glMultiTexCoord2fARB(GL.GL_TEXTURE0_ARB,Rtex,Ttex)
        GL.glMultiTexCoord2fARB(GL.GL_TEXTURE1_ARB,Rmask,Tmask)
        GL.glVertex2f(R,T)
        GL.glEnd()

        #disable mask
        GL.glActiveTextureARB(GL.GL_TEXTURE1_ARB)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

        #main texture
        GL.glActiveTextureARB(GL.GL_TEXTURE0_ARB)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

        #we're done!
        GL.glEndList()


    def __del__(self):
        GL.glDeleteLists(self._listID, 1)
        self.clearTextures()#remove textures from graphics card to prevent crash

    def clearTextures(self):
        """
        Clear the textures associated with the given stimulus.
        As of v1.61.00 this is called automatically during garbage collection of
        your stimulus, so doesn't need calling explicitly by the user.
        """
        GL.glDeleteTextures(1, self._texID)
        GL.glDeleteTextures(1, self._maskID)

    def _calcCyclesPerStim(self):
        if self.units in ['norm', 'height']:
            self._cycles = self.sf  #this is the only form of sf that is not size dependent
        else:
            self._cycles = self.sf * self.size

    def contains(self, *args, **kwargs):
        raise NotImplementedError("GratingStim do not have a contains() method")
    def overlaps(self, *args, **kwargs):
        raise NotImplementedError("GratingStim do not have an overlaps() method")
