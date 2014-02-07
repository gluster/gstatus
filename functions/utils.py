#!/usr/bin/env python
def displayBytes(inBytes):
	"""
	Routine to convert a given number of bytes into a more human readable form
	
	Input  : number of bytes
	Output : returns a MB / GB / TB value for bytes
	
	"""
	
	
	bytes = float(inBytes)
	if bytes >= 1125899906842624:
		size = round(bytes / 1125899906842624)
		#displayBytes = '%.1fP' % size
		displayBytes = '%dP' % size
	elif bytes >= 1099511627776:
		size = round(bytes / 1099511627776)
		displayBytes = '%dT' % size
	elif bytes >= 1073741824:
		size = round(bytes / 1073741824)
		displayBytes = '%dG' % size 
	elif bytes >= 1048576:
		size = int(round(bytes / 1048576))
		displayBytes = '%dM' % size
	elif bytes >= 1024:
		size = int(round(bytes / 1024))
		displayBytes = '%dK' % size 
	else:
		displayBytes = '%db' % bytes 
	return displayBytes
