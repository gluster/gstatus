#!/usr/bin/env python
def displayBytes(inBytes, units='bin'):
	"""
	Routine to convert a given number of bytes into a more human readable form
	
	- Based on code in Mark Pilgrim's Dive Into Python book
	
	Input  : number of bytes
	Output : returns a MB / GB / TB value for bytes
	
	"""

	SUFFIXES = {1000: ['KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'],
				1024: ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']}

	ROUNDING = { 'K': 0, 'M':0, 'G':0, 'T':1, 'P':2, 'Z':2, 'Y':2}

	size = float(inBytes)

	if size < 0:
		raise ValueError('number must be non-negative')

	divisor = 1024 if units == 'bin' else 1000
	for suffix in SUFFIXES[divisor]:
		size /= divisor
		if size < divisor:
			char1 = suffix[0]
			precision = ROUNDING[char1]
			size = round(size,precision)

			return '{0:.2f} {1}'.format(size, suffix)

	raise ValueError('number too large')

def getAttr(element,match_list):
	""" function to convert an xml node element with attributes, to a dict """
	
	attr_list = {}
	for node in element.getchildren():
		if node.tag in match_list:
			attr_list[node.tag] = node.text

	return attr_list
