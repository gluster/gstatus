#!/usr/bin/env python
#
#	syscalls.py - module that provides an system related function to gstatus 
#
#   Copyright (C) 2014 Paul Cuzner
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


import subprocess
import shlex




def issueCMD(command, shellNeeded=False):
	""" issueCMD takes a command to issue to the host and returns the response as a list """

	if shellNeeded:
		args =command
	else:
		args = shlex.split(command)

	try:
		child = subprocess.Popen(args,shell=shellNeeded,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		
		# Get output...response is a byte string that includes \n		
		(response, errors)=child.communicate()
		
		# Add any errors to the response string
		response += errors
		rc = child.returncode	 

	except Exception:
		response = 'command failed\n' 
		rc=12
		
	cmdText = response.split('\n')[:-1]
	
	return (rc, cmdText)                 

