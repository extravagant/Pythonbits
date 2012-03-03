import os
import os.path
import stat
import urllib
import xmlrpclib
import logging

TEST_USER_AGENT = 'OS Test User Agent'
logging.basicConfig()

class SizeError(Exception):
    '''Raised when the file is too small,
which is currently (65536 * 2).
    :param size: the offending size
    '''
    def __init__(self, size):
        Exception.__init__(self)
        this.size = size
class BadStatus( Exception ):
    '''
    Raised when the opensubtitles server does not reply 200 OK
    :param status: the status that the server _did_ respond with.
    '''
    def __init__(self, status):
        Exception.__init__(self)
        this.status = status
class NoDataKey( Exception ):
    '''
    Raised when the opensubtitles answer does not contain 'data'
    :param result: the map that the server _did_ respond with.
    '''
    def __init__(self, result):
        Exception.__init__(self)
        this.result = result
class NoStatusKey( Exception ):
    '''
    Raised when the opensubtitles answer does not contain 'status'
    :param result: the map that the server _did_ respond with.
    '''
    def __init__(self, result):
        Exception.__init__(self)
        this.result = result

class OpenSubtitlesClient(object):
    # ENDPOINT_URL = 'http://api.opensubtitles.org/xml-rpc'
    ENDPOINT_URL = 'http://localhost:8000/xml-rpc'
    def __init__(self):
        self.endpoint = OpenSubtitlesClient.ENDPOINT_URL
        self.LOG = logging.getLogger('OpenSubtitlesClient')
        self.token = None
    def LogIn(self, login, password, user_agent):
        methodname = 'LogIn'
        params = (login, password, 'eng', user_agent)
        res = self._invoke( params, methodname )
        self.token = res['token']
        self.LOG.debug( "LogIn.Token=%s", self.token )
    def SearchSubtitles(self, file_size, file_hash):
        '''
        Does cool things
        '''
        methodname = 'SearchSubtitles'
        params = (file_size, file_hash)
        res = self._invoke( params, methodname )
        if not res:
            return None
        if len(res) < 1:
            self.LOG.debug('result := %s', repr(res))
            return None
        item = res[0]
        if 'status' not in item:
            self.LOG.error(
                'Item did not contain status: %s', repr(item))
            raise NoStatusKey( item )
        item_status = item['status']
        if '200 OK' != item_status:
            raise BadStatus( item_status )
        if 'data' not in item:
            raise NoDataKey( item )
        result = item['data']
        return result
    def LogOut(self):
        '''
        Kindly releases your server-side session.
        '''
        methodname = 'LogOut'
        params = (self.token, )
        res = self._invoke( params, methodname )

    def _invoke( self, params, methodname ):
        req = xmlrpclib.dumps( params, methodname )
        req_gz = xmlrpclib.gzip_encode( req )
        self.LOG.debug(
            "[%s]::REQ=%s", methodname, repr(req) )
        resf = urllib.urlopen( self.endpoint, req_gz )
        res_gz = resf.read()
        res_txt = xmlrpclib.gzip_decode( res_gz )
        res = xmlrpclib.loads( res_txt )
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
    '''
    :param fn: the filename
    :return: the tuple (size, hashstring)
    '''
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
    thehash = '%016x' % cksum
    return (siz, thehash)

if __name__ == '__main__':
    '''
AVI file (12 909 756 bytes)
hash: 8e245d9679d31e12 

DUMMY RAR file (2 565 922 bytes, 4 295 033 890 after RAR unpacking)
hash: 61f7751fc2a72bfb 
    '''
    import sys
    fn = sys.argv[1]
    res = hashFilename( fn )
    fs = res[0]
    h = res[1]
    username = ''
    password = ''
    print "FILE(%s)=%s %s" % ( fn, fs, h )
    client = OpenSubtitlesClient()
    client.set_debug( os.getenv('OSC_DEBUG') != None )
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

