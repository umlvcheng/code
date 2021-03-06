# Import modules from standard Python (>= 2.4) library
import datetime,time,xml.dom.minidom,codecs

verbose = False

# ------------------------------------------------------------------------------------------
# Base class that supports reference counting
# ------------------------------------------------------------------------------------------

class referencedobject(object):
    """Abstract base class for an object that supports reference counting,
    and cleans up after the last reference has been released.
    
    Of course Python does its own garbage collection and reference counting.
    However, sometime we use objects that *must* be cleaned up immediately
    when the object goes fully out of scope. This applies for instance to
    objects that lock a file on disk. The garbage collection implementation
    cannot guarantee immediate clean-up when the object goes out of scope.
    Moreover, Python implementations are not even required to implement
    garbage collection. Hence the existence of this class.
    
    It supports some rudimentary functionality for checking if all references
    were cleanly released at exit (i.e., if no objects exist that have one or
    more references. For this to work the user has to take care to release
    all references to objects of this type explicitly at exit.
    """
    
    # Debug switch: it determines whether at exit we check for unreleased objects.
    # WARNING! Enabling this has been found to be very expensive!
    checkreferences = False

    # Debug objects: list of created objects, and list of tracebacks at creation.
    objs,tracebacks = None,None
    
    @staticmethod
    def onNewObject(obj):
        """If reference checking is enabled, this method is called on creation
        of a referenced object.
        """
        if referencedobject.objs is None:
            referencedobject.objs = []
            referencedobject.tracebacks = []
            import atexit
            atexit.register(referencedobject.cleanup)
        referencedobject.objs.append(obj)
        import traceback
        referencedobject.tracebacks.append(traceback.format_list(traceback.extract_stack(limit=10)[:-3]))
    
    @staticmethod
    def cleanup():
        """If reference checking is enabled, this method is called at exit.
        It then checks if there are any unreleased objects around, and reports
        those.
        """
        nrefs,nobjs = 0,0
        type2count = {}
        for obj,tb in zip(referencedobject.objs,referencedobject.tracebacks):
            if obj.refcount!=0:
                print '%i references for %s.' % (obj.refcount,object.__str__(obj))
                print ''.join(tb)
                nrefs += obj.refcount
                nobjs += 1
                type2count[obj.__class__.__name__] = type2count.get(obj.__class__.__name__,0) + 1
        if nrefs==0:
            print 'No remaining references.'
            return
        print '%i objects have a total of %i references.' % (nobjs,nrefs)
        for t,c in type2count.iteritems():
            if c>0: print '%s: %i references.' % (t,c)

    def __init__(self):
        self.refcount=1
        if referencedobject.checkreferences:
            referencedobject.onNewObject(self)
    
    def release(self):
        """Decreases the reference count of the object with one.
        """
        assert self.refcount>0, 'Reference count of object has already decreased to zero, but release is being called. Object: %s' % str(self)
        self.refcount -= 1
        if self.refcount==0: self.unlink()

    def addref(self):
        """Increments the reference count of the object and returns the object.
        """
        assert self.refcount>0, 'Reference count of object has decreased to zero, but addref is being called. Object: %s' % str(self)
        self.refcount += 1
        return self
        
    def unlink(self):
        """Called when all references to the object have been released.
        Inheriting classes should perform clean-up here.
        """
        pass
        
# ------------------------------------------------------------------------------------------
# Date-time parsing variables and functions
# ------------------------------------------------------------------------------------------

class UTC(datetime.tzinfo):
    """Minimal tzinfo class for UTC
    """
    ZERO = datetime.timedelta(0)

    def utcoffset(self, dt):
        return UTC.ZERO

    def tzname(self, dt):
        return 'UTC'

    def dst(self, dt):
        return UTC.ZERO
        
# Date format used for datetime strings visible to the user.
utc = None
def getUTC():
    global utc
    if utc is None: utc = UTC()
    return utc

def dateTimeFromTuple(tup):
    """Returns a datetime object from a sequence with six items: year,
    month, day, hours, minutes, seconds. The resulting object will use
    time zone UTC explicitly.
    """
    return datetime.datetime(tup[0],tup[1],tup[2],tup[3],tup[4],tup[5],tzinfo=getUTC())

def parseDateTime(str,fmt):
    """Convert string to Python datetime object, using specified format.
    Counterpart of datetime.strftime.
    """
    return dateTimeFromTuple(time.strptime(str,fmt))
    
def formatDateTime(dt,iso=False):
    """Converts a datetime object into a string.
    Uses ISO format (%Y-%m-%d %H:%M:%S) if "iso" is set to True; otherwise
    uses a pretty output format. NB currently the pretty output format is
    ISO as well...
    """
    return '%04i-%02i-%02i %02i:%02i:%02i' % (dt.year,dt.month,dt.day,dt.hour,dt.minute,dt.second)

    # strftime below cannot handle year<1900
    #return dt.strftime('%Y-%m-%d %H:%M:%S')

# ------------------------------------------------------------------------------------------
# XML helper functions
# ------------------------------------------------------------------------------------------

def findDescendantNode(root,location,create=False):
    """Return the first child XML DOM node with the specified location
    (location = array of path components) below the specified XML DOM node
    (root). If create = True, the node will be created if it does not exist
    yet.
    """
    assert root is not None,'findDescendantNode called on non-existent parent node (parent = None).'
    node = root
    for childname in location:
        if childname=='': continue
        foundchild = None
        for ch in node.childNodes:
            if ch.nodeType==ch.ELEMENT_NODE and ch.localName==childname:
                foundchild = ch
                break
        else:
            if create:
                doc = root
                while doc.parentNode is not None: doc=doc.parentNode
                assert doc.nodeType==doc.DOCUMENT_NODE, 'Could not find DOM document node needed to create %s. Node "%s" does not have a parent.' % (location,doc.tagName)
                foundchild = doc.createElementNS(node.namespaceURI,childname)
                node.appendChild(foundchild)
            else:
                return None
        node = foundchild
    return node

def findDescendantNodes(root,location):
    """Return a list of all child XML DOM nodes with the specified location
    (location = array of path components) below the specified XML DOM node
    (root).
    """
    parentloc = location[:]
    name = parentloc.pop()
    parent = findDescendantNode(root,parentloc,create=False)
    children = []
    if parent is not None:
        for ch in parent.childNodes:
            if ch.nodeType==ch.ELEMENT_NODE and ch.localName==name:
                children.append(ch)
    return children

def getNodeText(node):
    """Gets all text directly below the specified node. If the node contains
    multiple text nodes, their contents will be concatenated and returned.
    """
    return ''.join([ch.data for ch in node.childNodes if ch.nodeType==ch.TEXT_NODE]).strip()

def setNodeText(node,text,xmldocument=None):
    if xmldocument is None:
        xmldocument = node
        while xmldocument.parentNode is not None: xmldocument=xmldocument.parentNode
    for ch in reversed(node.childNodes):
        if ch.nodeType == ch.TEXT_NODE:
            node.removeChild(ch)
            ch.unlink()
    val = xmldocument.createTextNode(text)
    node.insertBefore(val,node.firstChild)
    
def removeNodeChildren(node):
    """Removes all child nodes from the specified node.
    """
    for ch in reversed(node.childNodes):
        node.removeChild(ch)
        ch.unlink()

def copyNode(sourcenode,newparent,targetdoc=None,name=None,before=None):
    """Creates a deep copy of the supplied XML node below the specified
    parent node. This function copies all attributes and element nodes.
    
    Argument "targetdoc" is optional and may be used to increase efficiency.
    It should then be set to the XML DOM that contains the new parent node.
    
    Argument "name" is optional, and may be set to a string that is then used
    as name of the copy of the source node, instead of the source node's
    original name.
    
    Argument "before" is optional, and may be set to a child node of the new
    parent. The copy of the source node will then be inserted just before this
    child node.
    """

    # Create new document or find existing one if not provided.
    if newparent is None:
        if targetdoc is None:
            impl = xml.dom.minidom.getDOMImplementation()
            targetdoc = impl.createDocument(None, None, None)
        newparent = targetdoc
    elif targetdoc is None:
        targetdoc = newparent
        while targetdoc.parentNode is not None: targetdoc = targetdoc.parentNode

    # Create new node
    cpy = None
    if sourcenode.nodeType==sourcenode.ELEMENT_NODE:
        if name is None: name = sourcenode.localName
        cpy = targetdoc.createElementNS(newparent.namespaceURI,name)
        for key in sourcenode.attributes.keys():
            cpy.setAttribute(key,sourcenode.getAttribute(key))
    elif sourcenode.nodeType==sourcenode.TEXT_NODE:
        cpy = targetdoc.createTextNode(sourcenode.data)
    elif sourcenode.nodeType==sourcenode.COMMENT_NODE:
		pass
    else:
        print 'WARNING: do not know how to copy node with type %s. Skipping...' % sourcenode.nodeType
        
    # Insert new node
    if cpy is not None:
        if before is None:
            cpy = newparent.appendChild(cpy)
        else:
            cpy = newparent.insertBefore(cpy,before)
        for ch in sourcenode.childNodes: copyNode(ch,cpy,targetdoc)
        
    # Return new node
    return cpy
    
def stripWhitespace(node):
    """Removes nodes that contain only white space from the beginning
    and end of the list of child nodes of the specified node.
    """
    # Process element child nodes.
    textnodes = []
    for ch in node.childNodes:
        if ch.nodeType==ch.ELEMENT_NODE:
            stripWhitespace(ch)
        elif ch.nodeType==ch.TEXT_NODE:
            textnodes.append(ch)
            
    if textnodes:
        # Reuse first text node to absorbed merged and whitespace-stripped text, and delete any other text nodes.
        text = ''.join([ch.data for ch in textnodes]).strip()
        if text:
            textnodes[0].data = text
            textnodes = textnodes[1:]
        for ch in textnodes: node.removeChild(ch)

def getRootNodeInfo(path):
    """Use SAX to parse XML file up to the first node (root node) only,
    and returns the local name of that node, and its attributes.
    Should be far more efficient than complete DOM-based parsing.
    """
    import xml.sax
    class DoneException(Exception): pass
    class handler(xml.sax.handler.ContentHandler):
        def __init__(self):
            self.rootname,self.rootattributes = None,{}
        def startElement(self,name,attr):
            self.rootname = name
            self.rootattributes = dict([(k,attr.getValue(k)) for k in attr.getNames()])
            raise DoneException
    h = handler()
    try:
        xml.sax.parse(path,h)
    except DoneException:
        pass
    return h.rootname,h.rootattributes
        
# ------------------------------------------------------------------------------------------
# Progress report merging class
# ------------------------------------------------------------------------------------------

class ProgressSlicer(object):
    """Progress reporting class that merges the progress of multiple steps
    that each report their individual progress.
    
    Generic progress reporting works as follows:
    
    The process that performs the (lenghty) operation calls at regular
    intervals a callback function with two arguments: (1) the current progress
    as a float value between 0 and 1, and (2) a string describing the current
    task being performed.
    
    This class gathers several of such processes, with each process getting
    attributed a weight describing the time it will take compared to the others.
    The progress messages of individual steps are caught, and translated
    into a global progress value and descriptive string.
    """
    def __init__(self,callback,totalweight):
        self.callback = callback
        self.step = -1
        self.total = totalweight
        self.prefix = ''
        self.currentweight = 1.
        
    def nextStep(self,prefix='',weight=1.,nodetailedmessage=False):
        """Registers that the previous subprocess has completed, and a new
        subprocess will begin. The prefix is a string that will be used to
        prefix the progress messages of the upcoming subprocess when global
        progress messages are built. The weight equals the relative weight of
        subprocess about to start.
        """
        assert not (prefix=='' and nodetailedmessage), 'If nodetailedmessage is set, the prefix must be specified.'
        self.step += self.currentweight
        if self.callback is not None: self.callback(float(self.step)/self.total,self.prefix)
        self.prefix = prefix
        self.currentweight = weight
        self.nodetailedmessage = nodetailedmessage
        
    def onStepProgressed(self,progress,status):
        """Called by subprocesses when they have progressed.
        """
        strings = []
        if self.prefix!='':            strings.append(self.prefix)
        if not self.nodetailedmessage: strings.append(status)
        self.callback((self.step+progress*self.currentweight)/self.total,' - '.join(strings))

    def getStepCallback(self):
        """Returns the callback function that the subprocess should use for
        reporting progress.
        """
        if self.callback is None: return None
        return self.onStepProgressed

charreplacements = {176:'deg',178:'^2',179:'^3'}
def unicodechar2ascii(ch):
    ich = ord(ch)
    if ich not in charreplacements:
        import unicodedata
        repl = unicodedata.name(ch,u'0x%x' % ich)
        if repl.startswith('GREEK SMALL LETTER '):
            repl = '\\'+repl[19:].lower()
        elif repl.startswith('GREEK CAPITAL LETTER '):
            repl = '\\'+repl[21:].capitalize()
        charreplacements[ich] = repl
    return charreplacements[ich]

def ascii_encode_error_handler(exc):
    assert isinstance(exc, UnicodeEncodeError), 'do not know how to handle %r' % exc
    l = []
    for c in exc.object[exc.start:exc.end]:
        l.append(unicodechar2ascii(c))
    return (u', '.join(l), exc.end)
codecs.register_error('xmlstore_descrepl', ascii_encode_error_handler)

def unicode2ascii(string):
    return string.encode('ascii','xmlstore_descrepl')
    
