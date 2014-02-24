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
	

if __name__ == '__main__':
	pass

