#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  network.py
#  
#  Copyright 2014 Paul <paul@rhlaptop>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  

import 	socket


def portOpen(hostname, port, scan_timeout=0.05):
	""" return boolean denoting whether a given port on a host is open or not """
	
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.settimeout(scan_timeout)

	state = True if s.connect_ex((hostname,port)) == 0 else False
	
	return state
	
def IPtoHost(addr):
	""" convert an IP address to a host name """
	
	try:
		host_name = socket.gethostbyaddr(addr)[0].split('.')[0]
	except:
		# can't resolve it, so default to the address given
		host_name = addr
	
	return host_name	
	
	
def isIP(host_string):
	""" Quick method to determine whether a string is an IP address or not """
	
	try:
		x = socket.inet_aton(host_string)
		response = True
	except:
		response = False
	
	return response
	

if __name__ == '__main__':
	pass

