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

import 	gstatus.functions.config as cfg

import 	socket
import 	netifaces


def portOpen(hostname, port, scan_timeout=0.05):
	""" return boolean denoting whether a given port on a host is open or not """
	
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.settimeout(scan_timeout)

	state = True if s.connect_ex((hostname,port)) == 0 else False
	
	return state
	
def IPtoHost(addr):
	""" convert an IP address to a host name, returning shortname and fqdn to the 
		caller
	"""
	
	
	try:
		fqdn = socket.gethostbyaddr(addr)[0]
		shortName = fqdn.split('.')[0]
		if fqdn == shortName:
			fqdn = ""
		
	except:
		# can't resolve it, so default to the address given
		shortName = addr
		fqdn = ""
	
	return (shortName, fqdn)
	

def hostToIP(hostname):
	""" provide a IP address for a given fqdn """
	
	try:
		return socket.gethostbyname(hostname)
	except:
		return hostname

	
def isIP(host_string):
	""" Quick method to determine whether a string is an IP address or not """
	
	try:
		x = socket.inet_aton(host_string)
		response = True
	except:
		response = False
	
	return response
	

def hostAliasList(host):
	""" for any given host attempt to return an alias list of names/IP """
	
	alias_list = []
	fqdn = ''
	shortname = ''
	ip_addr = ''
	
	alias_list.append(host)						
	
	if isIP(host):
	
		try:
			fqdn = socket.gethostbyaddr(host)[0]

		except:		
			# could get "socket.herror: [Errno 1] Unknown host"
			# indicating that reverse DNS is not working for this IP
			
			# If this is an IP on the local machine, use gethostname()
			if host in getIPv4Addresses():
				fqdn=socket.gethostname()	
			else:
				# however, if the IP is foreign and not resolving check
				# /etc/hosts for an answer
				with open('/etc/hosts') as hosts_file:
					ip_match = [host_entry for host_entry in hosts_file.readlines() if host in host_entry]
				if ip_match:
					fqdn = ip_match[0].split()[1]

				
		
		shortname = fqdn.split('.')[0]
		alias_list.append(fqdn)
		alias_list.append(shortname)
		
	else:
		try:
			if '.' in host:
				shortname = host.split('.')[0]
				alias_list.append(shortname)
			else:
				fqdn = socket.gethostbyname_ex(host)[0]
				alias_list.append(fqdn)
			
			ip_addr = socket.gethostbyname(host)
		except:
			pass

		alias_list.append(ip_addr)
						
	return sorted(alias_list)

def getIPv4Addresses():
	""" return a list of ipv4 addresses on this host from a specific list of 
		suitable interfaces (ethX, ibX etc)
		AF_INET = ipv4, AF_INET6 = ipv6
	"""
	ip_list =[]
	good_interface = ('eth','br','bond','ib','rhevm')
	
	interface_list = [ iface for iface in netifaces.interfaces() if iface.startswith((good_interface))]
	
	for interface in interface_list:
		link = netifaces.ifaddresses(interface)
		if netifaces.AF_INET in link:
			ipv4List = link[netifaces.AF_INET]
			for ip in ipv4List:
				ip_list.append(ip['addr'])
	
	return ip_list
	
	


if __name__ == '__main__':
	pass

