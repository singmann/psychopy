'''
Module containing validators for various parameters.
'''
import wx

class NameValidator(wx.PyValidator):
    """
    Component name validator for _BaseParamsDlg class. It depends on accesss to
    an experiment namespace. Validation checks if it is a valid Python
    identifier and if it does not clash with existing names.
    
    @see: _BaseParamsDlg
    """
    def __init__(self):
        super(NameValidator, self).__init__()
        self.message = ""
    
    def Clone(self):
        return NameValidator()
    
    def Validate(self, parent):
        message, valid = self.checkName(parent)
        parent.nameOKlabel.SetLabel(message)
        return valid
    
    def TransferFromWindow(self):
        return True
     
    def TransferToWindow(self):
        return True
    
    def checkName(self, parent):
        """checks namespace, return error-msg (str), enable (bool)
        """
        control = self.GetWindow()
        newName = control.GetValue()
        if newName=='':
            return "Missing name", False
        else:
            namespace = parent.frame.exp.namespace
            used = namespace.exists(newName)
            same_as_old_name = bool(newName == parent.params['name'].val)
            if used and not same_as_old_name:
                return "That name is in use (it's a %s). Try another name." % used, False
            elif not namespace.isValid(newName): # valid as a var name
                return "Name must be alpha-numeric or _, no spaces", False
            elif namespace.isPossiblyDerivable(newName): # warn but allow, chances are good that its actually ok
                return namespace.isPossiblyDerivable(newName), True
            else:
                return "", True
