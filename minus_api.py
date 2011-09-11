from hashlib import md5
import json
import logging
import os.path
from urllib import urlencode
import urllib2

class MinUsAPI(object):
	_MIN_US_API_PREFIX = 'http://min.us/api/'
	MIN_US_API_SIGNIN = _MIN_US_API_PREFIX+'SignIn'
	MIN_US_API_CREATE_GALLERY = _MIN_US_API_PREFIX+'CreateGallery'
	MIN_US_API_UPLOAD_ITEM = _MIN_US_API_PREFIX+'UploadItem'
	MIN_US_API_SIGNOUT = _MIN_US_API_PREFIX+'SignOut'

	def __init__(self):
		self._log = logging.getLogger('MinUsAPI')
		self._cookie_proc = urllib2.HTTPCookieProcessor()
		self._opener = urllib2.build_opener(
			urllib2.HTTPHandler, self._cookie_proc )
		self._authenticated = False

	def upload_one_item(self, local_path, username, password ):
		self.login(username, password)
		gallery_id, _ = self.create_gallery()
		result = self.upload_item( gallery_id, local_path )
		self.logout()
		return result

	def login(self, username, password ):
		signon_params = {'username':username, 'password1':password}
		signon_data = urlencode( signon_params )
		url = MinUsAPI.MIN_US_API_SIGNIN
		res = self._opener.open( url, data=signon_data )
		self._check_result( res, url )
		res_content = res.read()
		res.close()
		self._log.debug("%s :Content=%s", url, res_content)
		self._log.debug('cookie-jar=%s', self._cookie_proc.cookiejar)

		obj = self._decode_json( res_content )
		if 'success' not in obj:
			raise IOError("SignIn did not output success")
		if not obj['success']:
			raise IOError("SignIn did not indicate success")
		self._authenticated = True

	def create_gallery(self):
		url = MinUsAPI.MIN_US_API_CREATE_GALLERY
		res = self._opener.open( url )
		self._check_result( res, url )
		res_content = res.read()
		res.close()
		self._log.debug("%s :Content=%s", url, res_content)
		self._log.debug('cookie-jar=%s', self._cookie_proc.cookiejar)

		obj = self._decode_json( res_content )
		if 'editor_id' in obj:
			editor_id = obj['editor_id']
		else:
			raise ValueError("Expected to find 'editor_id' in %s but no" % obj)
		if 'reader_id' in obj:
			reader_id = obj['reader_id']
		else:
			raise ValueError("Expected to find 'reader_id' in %s but no" % obj)
		return editor_id, reader_id

	def upload_item(self, gallery_id, local_path ):
		# get this out of the way early, since if there is no file,
		# there is no further action
		basename = os.path.basename( local_path )
		file_ext = os.path.splitext( basename )[1]
		fh = open( local_path, 'rb' )
		bytes = fh.read()
		fh.close()

		boundary = md5(local_path).hexdigest()
		header = ('--%(bound)s\r\n' +
			'Content-Disposition: form-data; name="file"; filename="%(fn)s"\r\n'+
			'Content-type: application/octet-stream\r\n'+
			'\r\n') % {'bound':boundary, 'fn':basename }
		footer = "\r\n--%s--\r\n" % boundary
		clen = len(header) + len(bytes) + len(footer)
		ctype = 'multipart/form-data; boundary="%s"' % boundary

		params = {'code':'OK', 'editor_id':gallery_id, 'filename':basename}
		qstring = urlencode( params )
		url = '%s?%s' % (MinUsAPI.MIN_US_API_UPLOAD_ITEM, qstring )
		self._log.debug("UploadURL:", url)
		req = urllib2.Request( url )
		# be careful; urllib is case sensitive about this stuff
		req.add_header( 'Content-type', ctype )
		req.add_header( 'Content-length', str(clen) )
		req.add_data( header + bytes + footer )
		res = self._opener.open( req )
		self._check_result( res, url )
		res_content = res.read()
		res.close()
		self._log.debug("%s :Content=%s", url, res_content)
		self._log.debug('cookie-jar=%s', self._cookie_proc.cookiejar)

		obj = self._decode_json( res_content )
		if 'id' not in obj:
			raise ValueError("Expected to find 'id' but did not")
		file_id = obj['id']
		## BE CAREFUL: that leading "i" in the URI is significant
		## and don't use the min.us URL, as it returns 302 redirects to the .com
		## without the file extension, it barfs (what a retarded error)
		file_url = 'http://i.minus.com/i%s%s' % ( file_id, file_ext )
		self._log.info( "ItemURL=%s", file_url )
		return file_id, file_url

	def logout(self):
		if not self._authenticated:
			return
		url = MinUsAPI.MIN_US_API_SIGNOUT
		res = self._opener.open( url )
		self._check_result( res, url )
		# this is just the HTML for the front page, but read it out anyway
		res_content = res.read()
		res.close()
		self._log.debug("%s :Content=%s", url, res_content)
		self._log.debug('cookie-jar=%s', self._cookie_proc.cookiejar)
		self._authenticated = False

	def _check_result(self, res, action ):
		self._log.debug("RES :dir=%s %s", dir(res), res)
		if res.code != 200:
			raise IOError("Unable to %s: %s %s %s" %
						  (action, res.code, res.headers, res.msg))

	def _decode_json(self, json_string ):
		if hasattr(json, 'loads'):
			result = json.loads( json_string )
		elif hasattr(json, 'read'):
			result = json.read( json_string )
		else:
			raise Exception("Unknown `json` module")
		return result

	def __del__(self):
		"""
		Ensures that we are logged out when garbage collected.
		"""
		if self._opener and self._authenticated:
			self.logout()
			self.opener = None
