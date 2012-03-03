__docformat__ = 'restructuredtext en'
import logging
import os
import stat
import httplib
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
    Raised when the opensubtitles server does not reply 200 OK
    :param status: the status that the server _did_ respond with.
    """
    def __init__(self, status):
        Exception.__init__(self)
        self.status = status
    def __repr__(self):
        return 'The server responded with "status":%s' % self.status
class NoDataKey( Exception ):
    """
    Raised when the opensubtitles answer does not contain 'data'
    :param result: the map that the server _did_ respond with.
    """
    def __init__(self, result):
        Exception.__init__(self)
        self.result = result
    def __repr__(self):
        return 'The server responded with %s' % self.result
class NoStatusKey( Exception ):
    """
    Raised when the opensubtitles answer does not contain 'status'
    :param result: the map that the server _did_ respond with.
    """
    def __init__(self, result):
        Exception.__init__(self)
        self.result = result
    def __repr__(self):
        return 'The server responded with %s' % self.result
class NoTokenKey( Exception ):
    """
    Raised when the opensubtitles answer does not contain 'token'
    :param result: the map that the server _did_ respond with.
    """
    def __init__(self, result):
        Exception.__init__(self)
        self.result = result
    def __repr__(self):
        return 'The server responded with %s' % self.result

class OpenSubtitlesClient(object):
    ENDPOINT_URL = 'http://api.opensubtitles.org/xml-rpc'
    # ENDPOINT_URL = 'http://localhost:8000/xml-rpc'
    def __init__(self):
        self.endpoint = OpenSubtitlesClient.ENDPOINT_URL
        self.LOG = logging.getLogger('OpenSubtitlesClient')
        self.token = None
    def LogIn(self, login, password, user_agent):
        methodname = 'LogIn'
        lang_code = 'eng'
        if len(username) == 0:
            lang_code = ''
        params = (login, password, lang_code, user_agent)
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
        :raise NoStatusKey: if the result did not contain a 'status' key
        :raise BadStatus: the server responded with a non-200 status
        :raise NoDataKey: if the response did not contain a 'data' key
        """
        methodname = 'SearchSubtitles'
        query_list = [ {'moviebytesize':file_size, 'moviehash':file_hash} ]
        params = (self.token, query_list )
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
            "[%s]::REQ=%s", methodname, repr(req) )
        # req_gz = xmlrpclib.gzip_encode( req )
        req_gz = req
        send_gz = False
        del req
        # we need all of this tomfoolery because we have to
        # indicate that the content has been gzip-ed, and to
        # indicate that we accept gzip responses
        http_proxy = os.getenv('http_proxy')
        if http_proxy is not None:
            _, netloc, _, _, _ = httplib.urlsplit( http_proxy )
            path = self.endpoint
        else:
            _, netloc, path, _, _ = httplib.urlsplit( self.endpoint )
        conn = httplib.HTTPConnection( netloc )
        conn.set_debuglevel( 10 )
        conn.putrequest('POST', path, skip_accept_encoding=1 )
        # conn.putheader( 'Accept-Encoding', 'gzip' )
        if send_gz:
            conn.putheader( 'Content-Encoding', 'gzip' )
        conn.putheader( 'Content-Length', str(len(req_gz)))
        conn.putheader( 'Connection', 'close' )
        conn.endheaders()
        conn.send( req_gz )
        del req_gz
        http_res = conn.getresponse()
        self.LOG.debug(
            'HTTP Response := status:%s headers:%s',
            http_res.status, http_res.getheaders())
        if http_res.status != 200:
            raise IOError('Bogus HTTP response: %s' % http_res.status)
        ce = http_res.getheader('content-encoding')
        res_gz = http_res.read()
        http_res.close()
        conn.close()
        do_gzip = ce is not None and 'gzip' == ce.lower()
        if do_gzip:
            try:
                res_xml = xmlrpclib.gzip_decode( res_gz )
            except ValueError:
                self.LOG.error(
                    'Unable to gunzip %s', repr(res_gz), exc_info=1)
                # good luck!
                res_xml = res_gz
        else:
            res_xml = res_gz
        del res_gz
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
        tmp = tmp | k
    return tmp & 0xFFFFFFFFFFFFFFFFL

def hashFilename( fn ):
    """
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
    return (siz, the_hash)

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
    res = hashFilename( fn )
    fs = res[0]
    h = res[1]
    username = ''
    password = ''
    print "FILE(%s)=%s %s" % ( fn, fs, h )
    client = OpenSubtitlesClient()
    client.set_debug( os.getenv('OSC_DEBUG') is not None )
    client.LogIn( username, password, TEST_USER_AGENT)
    results = client.SearchSubtitles( fs, h )
    client.LogOut()
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

