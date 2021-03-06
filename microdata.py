"""
Tries to extract the information described by the
http://schema.org/ microdata attributes.
"""

def run_scope( item_type ):
	"""
	Finds the microdata properties of the provided itemtype node.
	If this item type has sub-item-types in it, they will live under a
	*non-qualified* key called ``children``.
	:param item_type: the HTML element that has an ``itemtype`` attribute
	:returns: a map containing the namespace-qualified item properties
	"""
	DEBUG = False
	import re
	HEX_CHAR_RE = re.compile(r'\&#(x?[0-9A-Fa-f]+);')
	result = {}
	i_type = item_type['itemtype']
	if DEBUG:
		print '<%s> isa %s' % (item_type.name, i_type)
	# have to run the sub-scopes first so we can delete them
	# that prevents their attributes from showing up as ours
	children = run_scopes( item_type )
	if children:
		# don't qualify this so it isn't mistaken for a microdata attribute
		result[ 'children' ] = children
	props = item_type.findAll( attrs={'itemprop':True} )
	for prop in props:
		p_name = prop['itemprop']
		# we just want the first child but calling prop.children
		# doesn't work, which explains this foolishness:
		p_value = [p for p in prop.childGenerator()]
		if DEBUG:
			print "P_VALUE=(((%s)))" % p_value
		if len(p_value) == 0:
			p_value = ''
		elif len(p_value) > 0:
			p_value = str(p_value[0]).strip()
		def unescaper( ma ):
			txt = ma.group(1)
			if 'x' == txt[0]:
				val = int(txt[1:], 16)
			else:
				val = int(txt)
			result = chr( val )
			if DEBUG:
				print "UNESC(%s)=>(%s)" % (txt, result)
			return result
		p_value = HEX_CHAR_RE.sub( unescaper, p_value )
		result_key = '%s/%s' % (i_type, p_name)
		if result_key in result:
			# a multi-value
			old_value = result[ result_key ]
			if isinstance(old_value, str) \
			or isinstance(old_value, unicode):
				new_value = [ old_value, p_value ]
				result[ result_key ] = new_value
			elif isinstance(old_value, list):
				old_value.append( p_value )
			else:
				raise ValueError("What is %s?" % type(old_value))
		else:
			result[ result_key ] = p_value
	# remove this item from the 'Soup tree
	item_type.extract()
	if not len(result):
		result = None
	if DEBUG:
		print "RESULT(((%s)))" % result
	return result

def run_scopes( starting_with ):
	"""
	Finds all of the microdata item types starting from the provided node.
	Please consult the documentation for ``run_scope`` to see what will
	be in this list.
	:param starting_with: the node from which to begin our search
	:returns: a list of microdata items, the format of which is described
	by ``run_scope``
	"""
	results = []
	while True:
		# re-query to account for any scopes that were deleted
		# if we just run this once, it will cache all the scopes in
		# the document
		types = starting_with.findAll( attrs={'itemtype':True} )
		if not types:
			break
		t = types[0]
		item = run_scope( t )
		if item:
			results.append( item )
		t.extract()
	return results

def extract( text_or_file ):
	"""
	Extracts any microdata found in the provided text.
	:param text_or_file: either the HTML text or a ``file``-esque object
	that I can ``read`` from.
	:returns: the output of running ``run_scopes`` upon the HTML you provide
	"""
	from BeautifulSoup import BeautifulSoup
	txt = text_or_file
	if hasattr(text_or_file,'read'):
		txt = text_or_file.read()
	soup = BeautifulSoup( txt )
	return run_scopes( soup )

if __name__ == '__main__':
	print extract("""<html>
<body>
<div itemscope itemtype="urn:Fred">
	<span itemprop='name'>Tommy&#x27;s Treehouse</span>
	<span itemprop='phone'>0800 22 33 55</span>
	<span itemprop='phone'>1-800-555-1212</span>
	<div itemscope itemtype="urn:Address">
		<span itemprop='city'>Topeka</span>
		<span itemprop='state'>Missouri</span>
	</div>
</div>
<div itemscope itemtype="urn:Bob">
	<span itemprop='name'>Bob the Builder</span>
	<div itemscope itemtype="urn:Address">
		<span itemprop='city'>Orlando</span>
		<span itemprop='state'>Florida</span>
	</div>
</div>
</body>
</html>
""")
# vim:noexpandtab:
