__docformat__ = 'restructuredtext en'
import logging
import os
import stat
# we *must* use urllib2 otherwise sending data uses x-www-form-urlencoded
import urllib2
import xmlrpclib

TEST_USER_AGENT = 'OS Test User Agent'

class SizeError(Exception):
    """
    Raised when the file is too small, which is currently (65536 * 2).

    :param size: the offending size
    """
    def __init__(self, size):
        Exception.__init__(self)
        self.size = size
class BadStatus( Exception ):
    """
    Raised when the OpenSubtitles server does not reply 200 OK
    :param status: the status that the server _did_ respond with.
    """
    def __init__(self, status):
        Exception.__init__(self)
        self.status = status
    def __str__(self):
        return repr(self)
    def __repr__(self):
        return 'The server responded with "status":%s' % self.status
class NoDataKey( Exception ):
    """
    Raised when the OpenSubtitles answer does not contain 'data'
    :param result: the map that the server _did_ respond with.
    """
    def __init__(self, result):
        Exception.__init__(self)
        self.result = result
    def __str__(self):
        return repr(self)
    def __repr__(self):
        return 'The server responded with %s' % self.result
class NoStatusKey( Exception ):
    """
    Raised when the OpenSubtitles answer does not contain 'status'
    :param result: the map that the server _did_ respond with.
    """
    def __init__(self, result):
        Exception.__init__(self)
        self.result = result
    def __str__(self):
        return repr(self)
    def __repr__(self):
        return 'The server responded with %s' % self.result
class NoTokenKey( Exception ):
    """
    Raised when the OpenSubtitles answer does not contain 'token'
    :param result: the map that the server _did_ respond with.
    """
    def __init__(self, result):
        Exception.__init__(self)
        self.result = result
    def __str__(self):
        return repr(self)
    def __repr__(self):
        return 'The server responded with %s' % self.result

class OpenSubtitlesClient(object):
    ENDPOINT_URL = 'http://api.opensubtitles.org/xml-rpc'
    # ENDPOINT_URL = 'http://localhost:8000/xml-rpc'
    def __init__(self, user_agent ):
        self.LOG = logging.getLogger('OpenSubtitlesClient')
        self.endpoint = OpenSubtitlesClient.ENDPOINT_URL
        self.lang_code = 'eng'
        self.token = None
        self.user_agent = user_agent

    def LogIn(self, login, password ):
        methodname = 'LogIn'
        params = (login, password, self.lang_code, self.user_agent )
        res = self._invoke( params, methodname )
        if 'status' not in res:
            self.LOG.error(
                'Result did not contain status: %s', repr(res))
            raise NoStatusKey( res )
        status = res['status']
        if '200 OK' != status:
            raise BadStatus( status )
        if 'token' not in res:
            raise NoTokenKey( res )
        self.token = res['token']
        self.LOG.debug( "LogIn.Token=%s", self.token )
    def SearchSubtitles(self, file_size, file_hash):
        """
        Searches for all the known subtitles that match
        your file size and file hash.

        :param file_size: the exact size in bytes of your file.
        :param file_hash: the hash code as computed by `hash_filename`
        :returns: a list of maps containing the query results
        :raise ValueError: if the ``file_size`` is not positive or
                            if the ``file_hash`` is empty
        :raise NoStatusKey: if the result did not contain a 'status' key
        :raise BadStatus: the server responded with a non-200 status
        :raise NoDataKey: if the response did not contain a 'data' key
        """
        methodname = 'SearchSubtitles'
        if not file_size:
            raise ValueError('file_size is required')
        if not file_hash:
            raise ValueError('file_hash is required')
        query_map = {}
        # and it has to be of XML-RPC type "double"
        file_size = float(file_size)
        query_map['moviebytesize']=file_size
        query_map['moviehash']=file_hash
        # this is actually a CSV, so tack on more if you want
        query_map['sublanguageid']='all'
        query_list = [ query_map ]
        params = ( self.token, query_list )
        res = self._invoke( params, methodname )
        if not res:
            return None
        if len(res) < 1:
            self.LOG.debug('result := %s', repr(res))
            return None
        if 'status' not in res:
            self.LOG.error(
                'Result did not contain status: %s', repr(res))
            raise NoStatusKey( res )
        item_status = res['status']
        if '200 OK' != item_status:
            raise BadStatus( item_status )
        if 'data' not in res:
            raise NoDataKey( res )
        result = res['data']
        return result
    def LogOut(self):
        """
        Kindly releases your server-side session.
        """
        methodname = 'LogOut'
        params = (self.token, )
        # we don't care about the result
        self._invoke( params, methodname )

    def _invoke(self, params, methodname ):
        """
        Handles the plumbing for invoking an XML-RPC call.
        Be aware your `params` need to be a *tuple* at all times,
        even with just one parameter.

        :param params: the *tuple* of your method's parameters.
        :param methodname: the name of your XML-RPC method to invoke
        :returns: the decoded response from the server
        :raise Exception: if the server indicated a Fault
        """
        req = xmlrpclib.dumps( params, methodname )
        self.LOG.debug(
            "[%s]::REQ=%s", methodname, req )
        http_headers = { 'User-Agent':self.user_agent,
                         'Content-Type':'text/xml; charset="UTF-8"'}
        http_req = urllib2.Request( self.endpoint, req, http_headers )
        http_res = urllib2.urlopen( http_req )
        res_xml = http_res.read()
        http_res.close()
        self.LOG.debug(
            "[%s]::RES.xml=%s", methodname, repr(res_xml) )
        res = xmlrpclib.loads( res_xml )
        del res_xml
        self.LOG.debug(
            "[%s]::RES=%s", methodname, repr(res) )
        x_fault = res[1]
        if x_fault is not None:
            raise Exception("Kaboom: %s" % str(x_fault))
        x_result = res[0][0]
        self.LOG.debug(
            "[%s]::RESULT=%s", methodname, repr(x_result) )
        return x_result
    def set_debug(self, value):
        if value:
            log_level = logging.DEBUG
        else:
            log_level = logging.INFO
        self.LOG.setLevel( log_level )

def read_uint64( f ):
    tmp = long(0)
    for i in xrange(0, 8):
        j = ord(f.read(1)) & 0xFFFFFFFFFFFFFFFF
        # u0 u1 ... u6 u7
        k = long(j << (8 * i)) & 0xFFFFFFFFFFFFFFFFL
        tmp |= k
    return tmp & 0xFFFFFFFFFFFFFFFFL

def hash_filename( fn ):
    """
    Constructs the hash according to the algorithm described
    at http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes

    This is a fresh implementation using the Public Domain C source,
    and thus not subject to the GPL.

    :param fn: the filename
    :return: the tuple (size, hash-string)
    """
    if not os.path.exists( fn ):
        raise IOError("Unable to find your file: %s'" % fn)
    st = os.stat( fn )
    siz = st[stat.ST_SIZE]
    if siz < 131072:
        # the specification for the hash claims it will only accept
        # files in the range (131072, 9000000000)
        raise SizeError( siz )
    chunk_size = 8192
    chunk_offset = -(chunk_size * 8)

    cksum = long(siz)
    f = open( fn, 'rb' )
    for x in xrange(0, chunk_size):
        cksum = (cksum + read_uint64( f )) & 0xFFFFFFFFFFFFFFFFL
    f.seek( chunk_offset, 2 )
    for x in xrange(0, chunk_size):
        cksum = (cksum + read_uint64( f )) & 0xFFFFFFFFFFFFFFFFL
    f.close()
    the_hash = '%016x' % cksum
    return siz, the_hash

if __name__ == '__main__':
    __doc__ = """
AVI file (12 909 756 bytes)
hash: 8e245d9679d31e12

DUMMY RAR file (2 565 922 bytes, 4 295 033 890 after RAR unpacking)
hash: 61f7751fc2a72bfb
    """
    import sys
    logging.basicConfig()
    fn = sys.argv[1]
    res = hash_filename( fn )
    fs = res[0]
    h = res[1]
    username = ''
    password = ''
    print "FILE(%s)=%s %s" % ( fn, fs, h )
    client = OpenSubtitlesClient( TEST_USER_AGENT )
    client.set_debug( os.getenv('OSC_DEBUG') is not None )
    client.LogIn( username, password )
    results = client.SearchSubtitles( fs, h )
    client.LogOut()
    if not results:
        print >> sys.stderr, "Sorry, no results"
        sys.exit( 1 )
    for x in results:
        for k in x.keys():
            v = x[k]
            print "  [%s]=%s"% (k, v)
        print "--\n"
    links = []
    for it in results:
        links.append( '[url=%s]%s[/url]' % (
                it['SubDownloadLink'], it['ISO639'], ) )
    print ' | '.join( links )

