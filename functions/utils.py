#!/usr/bin/env python
def displayBytes(inBytes, kb_is_1024_bytes=True):
	"""
	Routine to convert a given number of bytes into a more human readable form
	
	- Based on code in Mark Pilgrim's Dive Into Python book
	
	Input  : number of bytes
	Output : returns a MB / GB / TB value for bytes
	
	"""

	SUFFIXES = {1000: ['KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'],
				1024: ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']}

	

	size = float(inBytes)

	if size < 0:
		raise ValueError('number must be non-negative')

	divisor = 1024 if kb_is_1024_bytes else 1000
	for suffix in SUFFIXES[divisor]:
		size /= divisor
		if size < divisor:
			return '{0:.2f} {1}'.format(size, suffix)

	raise ValueError('number too large')

