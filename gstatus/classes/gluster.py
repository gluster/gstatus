#!/usr/bin/env python
#
#	gluster.py - module that defines the gluster objects used by gstatus
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


import 	os
import 	sys
import 	re
import 	glob
import 	xml.etree.ElementTree 	as 	ETree
import 	json
from 	decimal import *


from 	gstatus.functions.syscalls	import 	issueCMD
from 	gstatus.functions.network	import	portOpen, isIP, IPtoHost
from 	gstatus.functions.utils		import 	displayBytes

#
#
# Object Model 
#
#          1           M 	
#   Cluster---------- Volume
#   1 |\                | 1
#     |  \              | 
#     |    \            | 
#     |      \          | 
#     |        \        | 
#     |          \      | 
#     |            \    | 
#     |              \  | 
#   M |                \| M
#	 Node ------------Brick
#		  1			M
#
# Impact Analysis
# 1. A brick down affects volume and cluster
# 2. A node down affects Upstream and down stream (cluster and brick)
# 3. A volume down affects cluster
# 
#
#
#


class Cluster:
	""" The cluster object is the parent of nodes, bricks and volumes """

	# definition of the cluster attributes that should be used when 
	# displaying the cluster in json/keyvalue format
	attr_list = [	'status','glfs_version','node_count','nodes_active',
					'volume_count','brick_count','bricks_active','volume_summary',
					'sh_enabled','sh_active','raw_capacity','usable_capacity',
					'client_count','used_capacity',
					]


	def __init__(self):

		
		# counters
		self.node_count = 0
		self.volume_count = 0
		self.brick_count = 0 
		self.sh_enabled = 0		# sh = self heal
		
		self.nodes_active = 0
		self.bricks_active = 0
		self.sh_active = 0
				
		self.node={}			# dict of node objects indexed by node name
		
		self.node_names = []	# list of node names populated from the 
								# queryVolFiles method
		self.nodes_down = 0
		self.localhost = ''		# name of the current host running the 
								# tool from gluster's perspective
		self.volume={}
		self.brick={}
		
		self.glfs_version = self.getVersion()
		
		self.raw_capacity = 0
		self.usable_capacity = 0
		self.used_capacity = 0
		
		self.messages = []			# cluster error messages
		
									# flag showing whether the cluster
		self.name_based = True		# was formed based on name or IP
		
		self.has_volumes = False		
		self.status = "healthy"				# be optimistic at first :)	
		
		self.volume_summary = {'up':0, 'degraded':0,'partial':0,'down':0}

		self.output_mode = ''		# console, json, keyvalue based output
		
		self.client_count = 0
		self.client_set = set()
		
		# cluster status is either healthy/unhealthy or potentially down
		# (although a down cluster means all nodes are non-responsive)
		#
		# unhealthy 
		#		a node is down
		#		a volume is in partial state (multiple bricks down)
		#
		# down
		#		all nodes in the cluster are down
								
								
								
	
	def initialise(self):
		""" call the node, volume 'generator' to create the child objects 
			(bricks are created within the volume logic) """
		
		self.queryVolFiles()			# populate node names and type
										# by looking at the vol files
	
		# has_volumes is defined in the queryVolFiles call, so the logic 
		# here is that if we have seen vol files, then it's ok to
		# run the queries to define the node and volume objects
		if self.has_volumes:
			
			self.defineNodes()
			
			#self.numNodes()

			self.defineVolumes()
			
		else:
			# no volumes in this cluster, print a message and abort
			print "This cluster doesn't have any volumes/daemons running."
			print "The output below shows the current nodes attached to this host.\n"
			(rc, peers) = issueCMD('gluster pool list')
			for line in peers:
				print line
			print
			exit(12)




	def defineNodes(self):
		""" Define the nodes, by looking at 'gluster peer status' output """
		
		if self.output_mode == 'console':
			# display a progress message
			sys.stdout.write("Processing nodes"+" "*20+"\n\r\x1b[A")
		
		(rc, peer_list) = issueCMD('gluster peer status --xml')
		
		if rc > 0:
			print "gluster did not respond to a peer status request, gstatus"
			print "can not continue.\n"
			exit(12)

		# at this point the peer status worked, so lets process the list 
		# of nodes, comparing them against the source of truth aka the 
		# volfile :) This is necessary, since a peer status and pool list
		# doesn't return the same output on every node, IP addresses can 
		# appear in the output even though the peer probes were all done
		# by name!.
		
		#define the fields that we're interested in 
		field_list = ['hostname','uuid','connected']
		
		# create a copy of the nodes as discovered from the volfile(s)
		valid_nodes = list(self.node_names)
		
		xml_string = ''.join(peer_list)
		xml_root = ETree.fromstring(xml_string)

		peer_list = xml_root.findall('.//peer')
		
		# peer list will be cluster_size - 1 elements, since localhost is not used
		# by matching on these peers, and removing matched names from a 
		# a list, the remaining name from the reference list - derived from
		# the volfile(s) - has got to be the localhost ip
		
		for peer in peer_list:
			
			node_info = getAttr(peer,field_list)
			this_hostname = node_info['hostname']
			add_node = False
			if this_hostname in valid_nodes:
				add_node = True
				#
			elif not isIP(this_hostname) and self.name_based:
				add_node = True
			elif isIP(this_hostname) and self.name_based:
				# try to change the IPaddr to a hostname
				replacement_name = IPtoHost(this_hostname)
				if replacement_name in valid_nodes:
					this_hostname = replacement_name
					add_node = True
				else:
					print "gstatus is unable to resolve peer name of %s"%(this_hostname)
					print "and can not continue.\n"
					exit(12)
				
				
			if add_node:
				# 
				new_node = Node(this_hostname,
								node_info['uuid'],
								node_info['connected'])
				self.node[this_hostname] = new_node
				if this_hostname in valid_nodes:
					valid_nodes.remove(this_hostname)				
		
		# that's the remote nodes created, now for the localhost
		local_uuid = open('/var/lib/glusterd/glusterd.info').readlines()[0].strip()
		local_connected = '1' if portOpen('localhost',24007) else '0'
		if len(valid_nodes) == 1:
			local_hostname = valid_nodes[0]			# take what's left
			self.localhost = local_hostname
			new_node = Node(local_hostname,
							local_uuid,
							local_connected)
			self.node[local_hostname] = new_node
			
		else:
			print "Too many peers were not resolved when creating node"
			print "objects. gstatus can not continue.\n"
			exit(12)
			

		self.node_count = len(self.node)
		

	def defineVolumes(self):
		""" Create the volume + brick objects """
		
		if self.output_mode == 'console':
			# print a progress message
			sys.stdout.write("Building volume objects"+" "*20+"\n\r\x1b[A")
		
		(rc, vol_info) = issueCMD("gluster vol info --xml")
		
		xml_string = ''.join(vol_info)
		xml_root = ETree.fromstring(xml_string)
		
		vol_nodes = xml_root.findall('.//volume')
		
		for vol_object in vol_nodes:
			
			# set up a dict for the initial definition of the volume 
			vol_dict = {}
			
			# build a dict for the initial volume settings
			for attr in Volume.volume_attr:
				vol_dict[attr] = vol_object.find('./'+attr).text
			
			# create a volume object, for this volume
			new_volume = Volume(vol_dict)
			self.volume[new_volume.name] = new_volume
			
			#print "DEBUG - adding volume " + new_volume.name
			
			# add information about any volume options
			opt_nodes = vol_object.findall('.//option')
			for option in opt_nodes:
				for n in option.getchildren():
					if n.tag == 'name':
						key = n.text
					elif n.tag == 'value':
						value = n.text
						new_volume.options[key]=value
						
						# Protocols are enabled by default, so we look
						# for the volume tuning options that turn them 
						# off
						if key == 'user.cifs':
							if value in ['disable','off','false']:
								new_volume.protocol['SMB'] = 'off'
							
						elif key == 'nfs.disable':
							if value in ['on','true']:
								new_volume.protocol['NFS'] = 'off'
							
							
			
			# get bricks listed against this volume, and create the Brick object(s)
			brick_nodes = vol_object.findall('.//brick')
			
			# list holding brick paths
			repl = []
			ctr = 1
			
			for brick in brick_nodes:
				
				brick_path = brick.text
				new_volume.brick_order.append(brick_path)
				(hostname,pathname) = brick_path.split(':')
				
				# print "DEBUG - adding brick " + brick_path
				
				new_brick = Brick(brick_path, self.node[hostname], new_volume.name)

				# Add the brick to the cluster and volume
				self.brick[brick_path] = new_brick
				new_volume.brick[brick_path] = new_brick

				# add this brick to the owning node
				brick_owner = self.node[hostname]
				brick_owner.brick[brick_path] = new_brick

				if new_volume.replicaCount > 1:
					repl.append(brick_path)
					ctr +=1
					if ctr > new_volume.replicaCount:
						ctr = 1

						# add this replica set to the volume's info
						new_volume.replica_set.append(repl)
						# drop all elements from temporary list
						repl =[]

			# By default from gluster 3.3 onwards, self heal is enabled for 
			# all replicated volumes. We look at the volume type, and if it 
			# is replicated and hasn't had self-heal explicitly disabled the
			# self heal state is inferred against the nodes that contain the 
			# bricks for the volume. With this state in place, the updateState
			# method can cross-check to see what is actually happening

			if 'replicate' in new_volume.typeStr.lower():
				
				heal_enabled = True						# assume it's on
					
				if 'cluster.self-heal-daemon' in new_volume.options:
					if new_volume.options['cluster.self-heal-daemon'].lower() in ['off','false']:
						heal_enabled = False

				new_volume.self_heal_enabled = heal_enabled

				if heal_enabled:
					
					for brick_path in new_volume.brick:
						
						(hostname,brick_fsname) = brick_path.split(':')
						self.node[hostname].self_heal_enabled = True
						self.sh_enabled += 1
						
			self.volume_count = len(self.volume)
			self.brick_count  = len(self.brick)

	def getVersion(self):
		""" return the version of gluster """
		(rc, versInfo) = issueCMD("gluster --version")
		return versInfo[0].split()[1]
		
	def queryVolFiles(self):
		""" Look at the vol files and determine whether they are name
			based, returning a boolean to the caller """
		
		ip_ctr, named_ctr = 0, 0
		
		# use glob to find the vol files
		vol_files = glob.glob('/var/lib/glusterd/vols/*/trusted-*-fuse.vol')
		
		if vol_files:
			self.has_volumes = True
		
			# get a list of unique remote host names used in the vol files
			hosts = set([l.strip().split()[2] for f in vol_files 
						for l in open(f).readlines() if 'remote-host' in l])
			
			# Hopefully all the hosts will be either named or IP's not a mix
			# but if not, we'll side with the majority!			
			for hostname in hosts:
				if isIP(hostname):
					ip_ctr += 1
				else:
					named_ctr += 1
		
			self.node_names = list(hosts)
		
		self.name_based = True if named_ctr >= ip_ctr else False

		

	def glfsVersionOK(self, min_version):
		
		(min_major, min_minor) = str(min_version).split('.')
		(host_major, host_minor) = self.glfs_version.split('.')[:2]
		
		if ( int(host_major) >= int(min_major) and 
			int(host_minor) >= int(min_minor)):
			return True
		else:
			return False


	def activeNodes(self):
		""" Count no. of nodes in an up state """
		
		for hostname in self.node:
			if self.node[hostname].state == '1':
				self.nodes_active += 1
		
		return self.nodes_active

	def activeBricks(self):
		""" return the number of bricks in an up state """
		
		for brick_name in self.brick:
			if self.brick[brick_name].up:
				self.bricks_active +=1
		
		return self.bricks_active

	def healthChecks(self):
		""" perform checks on elements that affect the reported state of the cluster """
		
		# The idea here is to perform the most significant checks first
		# so the message list appears in a priority order
		
		# 1. volumes in a down or partial state
		for volume_name in self.volume:
			this_volume = self.volume[volume_name]
			
			if 'down' in this_volume.volume_state:
				self.messages.append("Volume '%s' is down"%(volume_name))
				self.status = 'unhealthy'
				
			if 'partial' in this_volume.volume_state:
				self.messages.append("Volume '%s' is in a PARTIAL state, some data is inaccessible data, due to missing bricks"%(volume_name))
				self.messages.append("WARNING -> Write requests may fail against volume '%s'"%(this_volume.name))				
				self.status = 'unhealthy'								
		
		
		
		# 2. nodes that are down
		for node_name in self.node:
			this_node = self.node[node_name]
			if this_node.state != '1':
				self.messages.append("Cluster node '%s' is down"%(node_name))
				self.status = 'unhealthy'
		
		# 3. check the bricks
		for brick_name in self.brick:
			
			this_brick = self.brick[brick_name]
			
			# 3.1 check for state
			if not this_brick.up:
				self.messages.append("Brick %s in volume '%s' is down/unavailable"%(brick_name, this_brick.owning_volume))
			
			# 3.2 check for best practice goes here (minor error messages - FUTURE)
			
			
		# 4. Insert your checks HERE!
		

		
	def checkSelfHeal(self):
		""" return the number of nodes that have self-heal active """

		for node_name in self.node:
			if self.node[node_name].self_heal_active:
				self.sh_active += 1
				
		return self.sh_active

	def numSelfHeal(self):
		""" return the number of nodes with self heal enabled """
		
		for node_name in self.node:
			if self.node[node_name].self_heal_enabled:
				self.sh_enabled += 1
				
		return self.sh_enabled

	def updateState(self):
		""" update the state of the cluster by processing the output of 'vol status' commands
		
			- vol status all detail --> provides the brick info (up/down, type), plus volume capacity
			- vol status all --> self heal states 
		
		"""
		if self.output_mode == 'console':
			# print a progress message
			sys.stdout.write("Updating volume information"+" "*20+"\n\r\x1b[A")
		
		# WORKAROUND
		# The code issues n vol status requests because issueing a vol status
		# wih the 'all' parameter can give bad xml when nodes are not
		# present in the cluster. By stepping through each volume, the 
		# xml, while still buggy can be worked around
		# Process all volumes known to the cluster
		for volume_name in self.volume:
	
			# 'status' is set from a vol info command. This will show whether the
			# vol is created (0), started (1), or stopped (2). We're only interested
			# in the started state, when issuing the vol status	command
			if self.volume[volume_name].status == 1:
				
				(rc, vol_status) = issueCMD("gluster vol status %s detail --xml"%(volume_name))
			
				# Need to check opRet element since for xml based gluster commands
				# do NOT pass a return code back to the shell!
				gluster_rc = int([line.replace('<',' ').replace('>',' ').split()[1] 
								for line in vol_status if 'opRet' in line][0])
			
				if gluster_rc == 0:
					xml_string = ''.join(vol_status)
					xml_obj = ETree.fromstring(xml_string)

					# Update the volume, to provide capacity and status information
					self.volume[volume_name].update(xml_obj)					
			
				else:
					# Being unable to get a vol status for a known volume
					# may indicate a peer transitioning to disconnected state
					# so issue an error message and abort the script
					print "\n--> gstatus has been unable to query volume '" + volume_name + "'"
					print "\nPossible cause: cluster is currently reconverging after a node"
					print "has entered a disconnected state."
					print "\nResponse: Rerun gstatus or issue a peer status command to confirm\n"
					exit(16)
				
				# ---------------------------------------------------------------------
				# The volume is in a started state, so look for self-heal
				# information - if this volume actually has self heal enabled!
				# ---------------------------------------------------------------------			
				if self.volume[volume_name].self_heal_enabled:
					
					if self.output_mode == 'console':
						sys.stdout.write("Analysing Self Heal daemons"+" "*20+"\n\r\x1b[A")
						
					(rc, vol_status) = issueCMD("gluster vol status %s --xml"%(volume_name))
					gluster_rc = int([line.replace('<',' ').replace('>',' ').split()[1] 
								for line in vol_status if 'opRet' in line][0])
				
					if gluster_rc == 0:
			
						xml_string = ''.join(vol_status)
						xml_root = ETree.fromstring(xml_string)
					
						self_heal_list = []
					
						node_elements = xml_root.findall('.//node')
						# print "DEBUG --> node elements in vol status is " + str(len(node_elements))
					
						# first get a list of self-heal elements from the xml
						for node in node_elements:
						
							# WORKAROUND
							# there's a big in 3.4, where when a node is missing 
							# the xml returned is malformed returning a node 
							# within a node so we need to check the subelements 
							# to see if they're valid. 
							if node.find('./node'):
								continue
						
								
							if node.find('./hostname').text == 'Self-heal Daemon':
								node_name = node.find('./path').text
								node_state = node.find('./status').text
								
								if node_name == 'localhost':
									node_name = self.localhost
								
								# check for a node name that is fqdn	
								elif '.' in node_name:
									node_name = node_name.split('.')[0]
									
								elif isIP(node_name) and self.name_based:
									
									# WORKAROUND
									# gluster's self info sometimes puts an IP not
									# name as the hostname, so we need to catch that 
									# and correct it if possible
									resolved_name = IPtoHost(node_name)	
									if resolved_name in self.node_names:
										node_name = resolved_name
									else:
										# tried to resolve the IP, but the name
										# doesn't tally with our cluster nodes
										print "gstatus has been given an IP address for a self-heal daemon that"
										print "does not correspond to a cluster node name, and can not continue\n"
										exit(16)
										
			
								if node_state == '1':
									self.node[node_name].self_heal_active = True
								else:
									self.node[node_name].self_heal_active = False

					# update the self heal flags, based on the vol status
					self.volume[volume_name].updateSelfHeal(self.output_mode)
					
					
		
			this_state = self.volume[volume_name].volume_state
			
			if this_state == 'up':
				self.volume_summary['up'] += 1
			elif 'degraded' in this_state:
				self.volume_summary['degraded'] += 1
			elif 'partial' in this_state:
				self.volume_summary['partial'] += 1
			else:
				self.volume_summary['down'] += 1
		
		
		self.activeNodes()		# update active node couter
		self.activeBricks()		# update active brick counter
		self.checkSelfHeal()

		self.calcConnections()
		
	def calcCapacity(self):
		""" update the cluster's overall capacity stats based on the
			volume information """
		
		for vol_name in self.volume:
			this_vol = self.volume[vol_name]
		
			self.raw_capacity += this_vol.raw_capacity
			self.usable_capacity += this_vol.usable_capacity
			self.used_capacity += this_vol.used_capacity
		
	def __str__(self):
		""" return a human readable form of the cluster object for processing 
			by logstash, splunk etc """

		data = {}
		data_string = ''
		
		for key,value in sorted(vars(self).iteritems()):
			
			if key in Cluster.attr_list:
				
				if self.output_mode == 'json':
					data[key] = value
					
				elif self.output_mode == 'keyvalue':
					if isinstance(value,dict):
						for dict_key in value:
							item_value = value[dict_key] if isinstance(value[dict_key],int) else "'%s'"%(value[dict_key])
							data_string += "%s_%s=%s,"%(key,dict_key,item_value)
							
					else:
						item_value = value if isinstance(value,int) else "'%s'"%(value)
						data_string += "%s=%s,"%(key,item_value)
						
		if self.output_mode == 'json':
			data_string = json.dumps(data,sort_keys=True)
			
		elif self.output_mode == 'keyvalue':
			data_string = data_string[:-1]
		
			
		return data_string
		
	def calcConnections(self):
		""" Issue a vol status all clients --xml and invoke the volume's
			clientCount method to determine unique clients connected to 
			the clusters volume(s) """
			
		if self.output_mode == 'console':
			# print a progress message
			sys.stdout.write("Processing gluster client connections"+" "*20+"\n\r\x1b[A")
		
		(rc, vol_clients) = issueCMD("gluster vol status all clients --xml")
		gluster_rc = int([line.replace('<',' ').replace('>',' ').split()[1] 
						for line in vol_clients if 'opRet' in line][0])
		
		if gluster_rc > 0:
			# unable to get the client connectivity information
			print "\ngstatus has been unable to get the output of a 'vol status all clients --xml' command"
			print "and can not continue.\n"
			exit(16)
		
		# At this point the command worked, so we can process the results
		xml_string = ''.join(vol_clients)
		xml_root = ETree.fromstring(xml_string)
		
		volumes = xml_root.findall('.//volume')
		
		for volume_xml in volumes:
			# Find the volume name
			vol_name = volume_xml.find('./volName').text
			
			# process the volume xml
			self.volume[vol_name].clientCount(volume_xml)

			# add the volumes unique set of clients to the clusters set
			self.client_set.update(self.volume[vol_name].client_set)
			
		self.client_count = len(self.client_set)
			
			

class Node:
	""" Node object, just used as a container as a parent for bricks """
	
	node_state = { '0':'down', '1':'up'}

	def __init__(self,node,uuid,state):
		self.node_name = node
		self.uuid=uuid
		self.state=state		# index for node_state dict
		# self.state_text = Node.node_state[state]
		self.brick = {}
		self.daemon_state = {}
		self.local=False		# is this the localhost?
		self.self_heal_enabled = False
		self.self_heal_active = False

	

class Volume:
	""" Volume object, linking out to the bricks, and holding the description
		of the volume's attributes """
		
	# Vol states are 
	# 	up		... all bricks online, operational
	# 	up(partial)	... one or more bricks offline, but replica in place
	# 	up(degraded) ... at least one replica set is offline
	# 	down		... volume is down/stopped

	volume_states = ['unknown','up', 'down','up(partial)', 'up(degraded)']
	
	# declare the attributes that we're interested in from the vol info output
	volume_attr = ['name', 'status', 'statusStr', 'type', 'typeStr', 'replicaCount']

	# status - 0=created, 1=started, 2 = stopped
	#
	# type - 5 = dist-repl

	def __init__(self,attr_dict):
		""" caller provides a dict, with the keys in the volume_attr list
			which we then apply when a volume is instantiated """
			
		# volume attribute names match those in the xml output
		for key, value in attr_dict.items():
			value = int(value) if value.isdigit() else value
			setattr(self, key, value)
			
	
		self.volume_state = 'down'	# start with a down state
		self.brick = {}				# pointers to the brick objects that make up this vol
		self.brick_order = []		# list of the bricks in the order they appear
		self.brick_total = 0
		self.replica_set=[]	   		# list, where each item is a tuple, of brick objects
		self.replica_set_state=[]  	# list show number of bricks offline in each repl set
		self.status_string = ''

		self.options = {} 
		self.raw_capacity = 0
		self.raw_used = 0
		self.usable_capacity = 0
		self.used_capacity = 0
		self.pct_used = 0
		self.nfs_enabled = True
		self.self_heal_enabled = False
		self.self_heal_string = 'N/A'
		self.self_heal_active = False	# default to not active
		self.self_heal_count = 0		# no. files being tracked for self heal
		
		# By default all these protocols are enabled by gluster
		self.protocol = {'SMB':'on', 'NFS':'on','NATIVE':'on'}
		
		self.client_count = 0
		self.client_set = set()

	def brickUpdate(self,brick_xml):
		""" method to update a volume's brick"""

		node_info = {}
		for brick_info in brick_xml.getchildren():

			# print "DEBUG setting " + brick_info.tag + " to " + brick_info.text
			node_info[brick_info.tag] = brick_info.text

		brick_path = node_info['hostname'] + ":" + node_info['path']
		brick_state = True if node_info['status'] == '1' else False
		this_brick = self.brick[brick_path]

		# update this brick
		this_brick.update(brick_state,
						int(node_info['sizeTotal']),
						int(node_info['sizeFree']),
						node_info['fsName'],
						node_info['device'],
						node_info['mntOptions'])

		# Add this bricks capacity info to the volume's stats                                           
		self.raw_capacity += int(node_info['sizeTotal'])
		self.raw_used += int(node_info['sizeTotal']) - int(node_info['sizeFree'])


	def update(self, volume_xml):
		""" receive an xml document containing volume's attributes, process
			each element updating the volume info and associated 
			brick information/state
		"""
		
		# print "DEBUG --> Attempting to update volume " + self.name

		node_elements = volume_xml.findall('.//node')
		# print "DEBUG --> this volume xml has %d node elements"%(len(node_elements))
		
		for node in node_elements:
			sub_element_count = len(node.getchildren())
			
			# for a good node definition, there are child elements but the 
			# number of elements varies by gluster version
			# Version 3.4 ... 11 sub elements of <node>
			# Version 3.5 ... 12 sub elements of <node> 3.5 adds a 'peerid' child element
			if sub_element_count >= 11:
				# print "DEBUG --> Updating a brick"
				self.brickUpdate(node)
			else:
				# Skipping this node element since it doesn't have child elements
				# and is therefore malformed xml
				pass
				# print "DEBUG --> skipping a node element"
		
		# ----------------------------------------------------------------
		# Brick info has been updated, we can calculate the volume capacity
		# but the volume needs to up at least partially up for the vol status 
		# to return information.
		# ----------------------------------------------------------------		

		(up_bricks, total_bricks) = self.brickStates()
		
		# if all the bricks are online the usable is simple
		if up_bricks == total_bricks:
			
			self.usable_capacity = self.raw_capacity / self.replicaCount
			self.used_capacity = self.raw_used / self.replicaCount

		else:
			
			# have to account for the available space in each replica set
			# for the calculation
			if self.replicaCount > 1:
				for set in self.replica_set:
					for brick_path in set:
						if self.brick[brick_path].up:
							self.usable_capacity += self.brick[brick_path].size
							self.used_capacity += self.brick[brick_path].used
							break
			else:
				self.usable_capacity = self.raw_capacity
				self.used_capacity = self.raw_used

		# with the volume used and usable calculated, we can derive the %used
		self.pct_used = (self.used_capacity / float(self.usable_capacity)) * 100

		# ----------------------------------------------------------------
		# Now look at the brick status and volume type to derive the volume
		# status
		# ----------------------------------------------------------------
		if up_bricks == 0:
			self.volume_state = 'down'
		else:
			self.volume_state = 'up'
			
			# Replicated volume
			if self.replicaCount > 1:
				# this is a replicated volume, so check the status of the 
				# bricks in each replica set
	
				set_state = []
				for this_set in self.replica_set:
					state = 0		# initial state is 0 = all good, n > 0 = n bricks down
	
					for brick_path in this_set:
						if not self.brick[brick_path].up:
							state += 1
					set_state.append(state)
	
				self.replica_set_state = set_state	
	
				worst_set = max(set_state)
				
				# check if we have a problem
				if worst_set > 0:
					if worst_set == self.replicaCount:
						self.volume_state += "(partial)"
					else:
						self.volume_state += "(degraded)"
			
			else:
				
				# This volume is not replicated, so brick disruption leads
				# straight to a 'partial' availability state
				if up_bricks != total_bricks:
					self.volume_state += '(partial) '
	
	def numBricks(self):
		""" return the number of bricks in the volume """
		
		return len(self.brick)

	def brickStates(self):
		""" return a tupe of online bricks and total bricks for this volume """
		
		all_bricks = len(self.brick)
		online_bricks = 0
		for brick_path in self.brick:
			if self.brick[brick_path].up:
				online_bricks += 1
		return (online_bricks, all_bricks)

	def updateSelfHeal(self,output_mode):
		""" Updates the state of self heal for this volume """
		
		# first check if this volume is a replicated volume, if not
		# set the state string to "not applicable"
		if 'replicate' not in self.typeStr.lower():
			self.self_heal_string = 'N/A'
			return
			
		# is self-heal is disabled by option
		if 'cluster.self-heal-daemon' in self.options:
			if self.options['cluster.self-heal-daemon'].lower() in ['off','false']:
				self.self_heal_string = 'DISABLED'
				return
				
		self.self_heal_string = self.getSelfHealStats()
		
		if output_mode == 'console':
			sys.stdout.write("Analysing Self Heal backlog"+" "*20+"\n\r\x1b[A")
		
		# On gluster 3.4 & 3.5 vol heal with --xml is not supported so parsing
		# has to be done the old fashioned way :)
		(rc, vol_heal_output) = issueCMD("gluster vol heal %s info"%(self.name))

		if rc == 0:
			
			total_heal_count = 0
			
			for line in vol_heal_output:
				line = line.lower()			# drop to lower case for consistency

				if line.startswith('brick'):
					(node,path_name) = line.replace(':',' ').split()[1:]
					
					# 3.4.0.59 in RHS returning fqdn node names
					if '.' in node:
						node = node.split('.')[0]

					# 3.4.0.59 adding trailing '/' to brick path
					brick_path = node + ":" + path_name.rstrip('/')

				if  line.startswith('number'):
					heal_count = int(line.split(':')[1])
					self.brick[brick_path].heal_count = heal_count
					total_heal_count += heal_count
						
			self.self_heal_count = total_heal_count
			if total_heal_count > 0:
				self.self_heal_string += "   Heal backlog of %d files"%(total_heal_count)
			else:
				self.self_heal_string += "   All files in sync"
			
		else:
			# vol heal command failed - just flag the problem
			self.self_heal_string += " BACKLOG DATA UNAVAILABLE"

			
	def getSelfHealStats(self):
		""" return a string active/enable self heal states for the
			nodes that support this volume """
			
		enabled = 0
		active = 0 	
		
		for brick_path in self.brick:
			this_brick = self.brick[brick_path]
			
			if this_brick.node.self_heal_enabled:
				enabled += 1
			if this_brick.node.self_heal_active:
				active += 1
			
		return "%2d/%2d"%(active, enabled)

	def printLayout(self):
		""" print function used to show the relationships of the bricks in
			a volume """

		supported_volume_types = ['Replicated', 'Distribute', 'Distributed-Replicate']

		if self.typeStr not in supported_volume_types:
			print "\tDisplay of this volume type has yet to be implemented"
			return

		print "\t%s %s"%(self.name.ljust(16,'-'),'+')
		print "\t" + " "*17 + "|"
		offset=16

		if self.typeStr.startswith('Dist'):
			print " "*offset + "Distribute (dht)"
			offset=25
		else:
			print " "*offset + "Replicated (afr)"
			offset = 25


		if self.replicaCount == 1:

			# Distributed layout
			for brick_name in self.brick_order:
				brick_info = self.brick[brick_name].printBrick()
				print (" "*offset + "|\n" + " "*offset + "+--" + brick_info)

		else:

			# Replicated volume
			repl_set = 0
			num_repl_sets = len(self.replica_set)
			link_char = "|"
			for replica_set in self.replica_set:

				if repl_set == (num_repl_sets -1):
					link_char = " "

				print (" "*offset + "|\n" + " "*offset + "+-- Repl Set "
						+ str(repl_set) + " (afr)" )
				padding = " "*offset + link_char + "     "
				for brick_path in replica_set:
					brick_info = self.brick[brick_path].printBrick()
					print (padding + "|\n" + padding + "+--" + brick_info)
				repl_set += 1
		print

	def clientCount(self,vol_stat_clients_xml):
		""" receive volume xml, and parse to determine the total # of
			unique clients connected to the volume """
		
		# By default the xml provides a 'clientCount' child element for 
		# the volume, but this number does not account for duplicate clients
		# connected e.g. One client can connect to a volume multiple times
		# getting counted 'n' times. This code determines unique clients
		# connected to the volume - since that would be more useful to 
		# sysadmins/Operations
		
		brick_clients_list = vol_stat_clients_xml.findall('.//clientsStatus')

		# Since sets only store unique values, we'll use that to track
		# unique clients
		
		for brick in brick_clients_list:
			clients = brick.findall('.//hostname')
			for client in clients:
				client_name = client.text.split(':')[0]
				self.client_set.add(client_name)
		
		self.client_count = len(self.client_set)
			

class Brick:
	""" Brick object populated initially through vol info, and then updated
		with data from a vol status <bla> detail command """
		
	def __init__(self, brick_path, node_instance, volume_name):
		self.brick_path = brick_path
		self.node = node_instance
		self.node_name = brick_path.split(':')[0] 
		self.up = False 
		self.mount_options = {}
		self.fs_type = ''
		self.device = ''
		self.device_type = ''			# LVM, partition
		self.size = 0
		self.free = 0 
		self.used = 0
		self.heal_count = 0
		self.owning_volume = volume_name
		#self.self_heal_enabled = False	# default to off

	def update(self,state, size, free, fsname, device, mnt_options):
		""" apply attributes to this brick """
		
		self.up = state
		self.size=size	#KB to convert to GB
		self.free=free
		self.used=size-free
		self.fs_type=fsname
		self.device=device
		if 'mapper' in device:
			self.device_type = 'LVM'

		# convert the mount options to a dict, for easy query later
		mnt_parms = mnt_options.split(',')
		for opt in mnt_parms:
			if '=' in opt:
				(key,value) = opt.split('=')
				self.mount_options[key] = value
			else:
				
				self.mount_options[opt] = True

	def printBrick(self):
		""" provide an overview of this brick for display """

		state = "UP" if self.up else "DOWN"

		if self.heal_count > 0:
				heal_string = "S/H Backlog %d"%(self.heal_count)
		else:
				heal_string = ""

		fmtd = ("%s(%s) %s/%s %s"
				%(self.brick_path, state,
				displayBytes(self.used),
				displayBytes(self.size),
				heal_string))


		return fmtd



def getAttr(element,match_list):
	""" function to convert an xml node element with attributes, to a dict """
	
	attr_list = {}
	for node in element.getchildren():
		if node.tag in match_list:
			attr_list[node.tag] = node.text

	return attr_list
