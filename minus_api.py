"""
Discovered, with some specification bug-fixes, from the following URL:
https://github.com/minus-development/MinusAPI/blob/master/REST_API.markdown
"""
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
		"""
		Uploads one item, along with all the housekeeping of logging in,
		creating a gallery and then logging out.

		This would be a class method, but it is unclear if @classmethod
		works on older Pythons.

		:param local_path: the filesystem path you wish to upload.
		:param username: the min.us username to use
		:param password: the min.us password to use
		:returns: a tuple containing the file-id and the i.minus.com URL
			for your convenience
		"""
		self.login(username, password)
		gallery_id, _ = self.create_gallery()
		result = self.upload_item( gallery_id, local_path )
		self.logout()
		return result

	def login(self, username, password ):
		"""
		Does exactly what you would expect.

		:raises IOError: if the server doesn't answer with any indication,
		:raises ValueError: if the server specifically said unsuccessful
		"""
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
			raise ValueError("SignIn did not indicate success")
		self._authenticated = True

	def create_gallery(self):
		"""
		Does exactly what you would expect.

		You must have already called ``login()`` before this method will
		succeed.

		:raises ValueError: if the server does not answer with both the
			editor-id and reader-id values.
		:returns: a tuple containing the editor-id and reader-id for the
			newly created Gallery.
		"""
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
		"""
		Uploads the specified local file into the specified gallery.

		You must already be logged in to use this method.

		:param gallery_id: the editor-id for the target gallery
		:param local_path: the file system path you wish to send.
		:returns: a tuple containing the newly created file's id and
				the ``i.minus.com`` URL for that file
		:raises ValueError: if the server does not respond with the newly
				created file's id
		"""
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
		"""
		Does exactly what you would expect.
		"""
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
		"""
		Ensures the result is okay, raising an Error if not.

		:param res: the `Response` object from `urllib2.urlopen`
		:param action: the action used to report a helpful error message.
		:raise IOError: if the response is not HTTP-200
		"""
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
