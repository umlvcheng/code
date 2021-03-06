import sys, os.path
import common
import xmlstore.xmlstore
import xmlplot.common

class LoadException(Exception): pass

class SettingsStore(xmlstore.xmlstore.TypedStore):
    def __init__(self,schema=None):
        if schema is None: schema = os.path.join(common.getDataRoot(),'schemas/settings/gotmgui.schema')
        xmlstore.xmlstore.TypedStore.__init__(self,schema)
        
    def load(self):
        settingspath = self.getSettingsPath()
        if not os.path.isfile(settingspath): return
        try:
            xmlstore.xmlstore.TypedStore.load(self,settingspath)
        except Exception,e:
            raise LoadException('Failed to load settings from "%s".\nReason: %s.\nAll settings will be reset.' % (settingspath,e))
            self.setStore(None)
        self.removeNonExistent('Paths/RecentScenarios','Path')
        self.removeNonExistent('Paths/RecentResults',  'Path')

    @staticmethod    
    def getSettingsPath():
        if sys.platform == 'win32':
            try:
                from win32com.shell import shellcon, shell
                appdata = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0)
            except ImportError:
                appdata = os.environ['APPDATA']
            return os.path.join(appdata,'GOTM','settings.xml')
        else:
            return os.path.expanduser('~/.gotm.gui')

    def save(self):
        if not self.changed: return
        settingspath = self.getSettingsPath()
        settingsdir = os.path.dirname(settingspath)
        if not os.path.isdir(settingsdir): os.mkdir(settingsdir)
        xmlstore.xmlstore.TypedStore.save(self,settingspath)
        
    def removeNonExistent(self,parentlocation,nodename):
        """Removes nodes below specified location if their value is not
        a path to an existing file. Used to filter defunct most-recently-used
        files.
        """
        parent = self[parentlocation]
        currentnodes = parent.getLocationMultiple([nodename])
        for i in range(len(currentnodes)-1,-1,-1):
            path = currentnodes[i].getValue()
            if not os.path.isfile(path):
                parent.removeChild(nodename,i)

    def addUniqueValue(self,parentlocation,nodename,nodevalue):
        parent = self[parentlocation]
        currentnodes = parent.getLocationMultiple([nodename])
        if currentnodes:
            maxcount = currentnodes[0].templatenode.getAttribute('maxOccurs')
            for i in range(len(currentnodes)-1,-1,-1):
                if currentnodes[i].getValue()==nodevalue:
                    parent.removeChild(nodename,i)
                    currentnodes.pop(i)
            if maxcount!='unbounded':
                if maxcount=='': maxcount = 1
                parent.removeChildren(nodename,first=int(maxcount)-1)
        newnode = parent.addChild(nodename,position=0)
        newnode.setValue(nodevalue)