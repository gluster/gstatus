#!/usr/bin/env python

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

