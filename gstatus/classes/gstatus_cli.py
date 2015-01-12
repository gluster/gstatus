#!/usr/bin/env python
#
import os
import signal
#
import socket
import glob
import subprocess
import threading
#
import 	xml.etree.ElementTree 		as	ETree
import 	gstatus.functions.config 	as 	cfg

def set_active_peer():

	""" Supplemental function to set the target node for the GlusterCommand
		instances """

	def __port_open(hostName='localhost'):
		portNumber = 24007
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		return True if s.connect_ex((hostName,portNumber)) == 0 else False

	glusterdPeers = "/var/lib/glusterd/peers/*"

	listeningPeer = ''
	# we first look at glusterd on the local machine
	if __port_open():
		listeningPeer = 'localhost'
	else:
		# Get a list of peers
		try:

			for peerFile in glob.glob(glusterdPeers):
				with open(peerFile) as peer:
					for option in peer:
						if option.startswith('hostname'):
							key, hostName = option.split('=')
							hostName = hostName.strip()

							if __port_open(hostName):
								raise StopIteration

		except StopIteration:
			listeningPeer = hostName

	GlusterCommand.targetNode = listeningPeer


class GlusterCommand(object):

	targetNode = 'localhost'		# default to local machine

	def __init__(self, cmd, timeout=1):
		self.cmd = cmd
		self.cmdProcess= None
		self.timeout = timeout
		self.rc = 0                 # -1 ... timeout
									# 0 .... successful
									# n .... RC from command
		
		self.stdout = []
		self.stderr = []


	def run(self):
		""" Run the command inside a thread to enable a timeout to be 
			assigned """
			
		def command_thread():
			""" invoke subprocess to run the command """
			
			if GlusterCommand.targetNode is not "localhost":
				self.cmd += " --remote-host=%s"%(GlusterCommand.targetNode)
		
			self.cmdProcess = subprocess.Popen(self.cmd, 
											  shell=True,
											  stdout = subprocess.PIPE, 
											  stderr = subprocess.PIPE,
											preexec_fn=os.setsid)
												
			stdout, stderr = self.cmdProcess.communicate()
			self.stdout = stdout.split('\n')[:-1]
			self.stderr = stderr.split('\n')[:-1]
			

  
		thread = threading.Thread(target=command_thread)
		thread.start()
		
		thread.join(self.timeout)
		
		if thread.is_alive():
			if cfg.debug:
				print "gstatus_cli. Response from glusterd has exceeded the %d secs timeout, terminating the request"%(cfg.CMD_TIMEOUT)
			os.killpg(self.cmdProcess.pid, signal.SIGTERM)
			self.rc = -1  

		else:
			# the thread completed normally
			if '--xml' in self.cmd:
				# set the rc based on the xml return code
				xmldoc = ETree.fromstring(''.join(self.stdout))
				self.rc = int(xmldoc.find('.//opRet').text)
			else:
				# set the rc based on the shell return code
				self.rc = self.cmdProcess.returncode  			      
			
					
