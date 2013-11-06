""" runtimeInfo.py: a demo of some ways to use class psychopy.info.RunTimeInfo() to obtain current system and other data at run-time.
psychopy.info.RunTimeInfo calls visual.getMsPerFrame() to characterize the current monitor refresh rate and variability.
"""

# author and version are used in the demo, in the way you might in your experiment.
# They expected to be at the top of the script that calls RunTimeInfo()), with a string literal assigned to them (no variables).
__author__ = """Jeremy "R." Gray""" ## double-quotes will be silently removed, single quotes will be left, eg, O'Connor
__version__ = "v1.0.a#'''" ## in-line comments are ignored, but comment characters within strings are retained

from psychopy import visual, logging
import psychopy.info

# When creating an experiment, first define your window (& monitor):
myWin = visual.Window(fullscr=False,size=[200,200], monitor='testMonitor')
myWin.setRecordFrameIntervals(True)
logging.console.setLevel(logging.DEBUG)

# Then gather run-time info. All parameters are optional:
runInfo = psychopy.info.RunTimeInfo(
        # if you specify author and version here, it overrides the automatic detection of __author__ and __version__ in your script
        #author='<your name goes here, plus whatever you like, e.g., your lab or contact info>',
        #version="<your experiment version info>",
        win=myWin,    ## a psychopy.visual.Window() instance; None = default temp window used; False = no win, no win.flips()
        refreshTest='grating', ## None, True, or 'grating' (eye-candy to avoid a blank screen)
        verbose=True, ## True means report on everything 
        userProcsDetailed=True,  ## if verbose and userProcsDetailed, return (command, process-ID) of the user's processes
        randomSeed='set:time', ## a way to record, and optionally set, a random seed of type str for making reproducible random sequences
            ## None -> default 
            ## 'time' will use experimentRuntime.epoch as the value for the seed, different value each time the script is run
            ##'set:time' --> seed value is set to experimentRuntime.epoch, and initialized: random.seed(info['randomSeed'])
            ##'set:42' --> set & initialize to str('42'), and will give the same sequence of random.random() for all runs of the script
        )
myWin.close()

print """
System and other run-time details are now saved in "runInfo", a dict-like object. You have to decide
what to do with it.

"print runInfo" will give you the same as "print str(runInfo)". This format is intended to be useful 
for writing to a data file in a human readable form:"""
print runInfo
#print repr(runInfo)
infoCopy = eval(repr(runInfo)) # this works, but the type() of all values is now string

print """If that's more detail than you want, try: runInfo = info.RunTimeInfo(...,verbose=False,...)."""

# To get the same info in python syntax, use "print repr(info)". You could write this format into 
# a data file, and its fairly readable. And because its python syntax you could later simply 
# import your data file into python to reconstruct the dict.

print "\nYou can extract single items from info, using keys, e.g.:"
print "  psychopyVersion = %s" % runInfo['psychopyVersion']
try:
    runInfo["windowRefreshTimeAvg_ms"]  # just to raise exception here if no keys
    print "or from the test of the screen refresh rate:"
    print "  %.2f ms = average refresh time" % runInfo["windowRefreshTimeAvg_ms"]
    print "  %.2f ms = median (average of 12 at the median, best estimate of monitor refresh rate)" % runInfo["windowRefreshTimeMedian_ms"]
    print "  %.3f ms = standard deviation" % runInfo["windowRefreshTimeSD_ms"]

    ## Once you have run-time info, you can fine-tune things with the values, prior to running your experiment.
    refreshSDwarningLevel_ms = 0.20 ##ms
    if runInfo["windowRefreshTimeSD_ms"] > refreshSDwarningLevel_ms:
        print "\nThe variability of the refresh rate is sort of high (SD > %.2f ms)." % (refreshSDwarningLevel_ms)
        ## and here you could prompt the user with suggestions, possibly based on other info:
        if runInfo["windowIsFullScr"]: 
            print "Your window is full-screen, which is good for timing."
            print 'Possible issues: internet / wireless? bluetooth? recent startup (not finished)?'
            if len(runInfo['systemUserProcFlagged']):
                print 'other programs running? (command, process-ID):',info['systemUserProcFlagged']
        else: 
            print """Try defining the window as full-screen (its not currently), i.e. at the top of the demo change to:
    myWin = visual.Window((800,600), fullscr=True, ...
and re-run the demo."""
except:
    pass
print """
(NB: The visual is not the demo! Scroll up to see the text output.)"""
