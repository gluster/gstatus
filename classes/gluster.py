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
import 	xml.etree.ElementTree 	as 	ETree

from 	functions.syscalls	import 	issueCMD
from 	functions.network	import	portOpen
#
#
#  
#		   1       M 	
#	Cluster-------- Volume
#   1 |               	| 1
#	  |					| 
#     |				    |
#	  |				   	|
#     |					|
#     |					|
#	  |	  				|
#	M | 				| M
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

	def __init__(self):
		self.glfs_version = ''	# version, or mixed
		self.msgs=[]
		self.node={}
		self.nodes_down = 0
		self.volume={}
		self.brick={}
		self.glfs_version = self.getVersion()
		self.raw_capacity = 0
		self.usable_capacity = 0
		self.messages = []
		
		self.status = "healthy"				# be optimistic at first :)	
		
		# cluster health is either healthy/recovery/unhealthy or down 
		#
		# unhealthy 
		#		a node is down
		#		a volume is in partial state (multiple bricks down)
		#
		# recovery
		#		self heal is operational recovering data
		#
		# down
		#		all nodes in the cluster are down
								
	
	def initialise(self):
		""" call the node, volume 'generator' to create the child objects 
			(bricks are created within the volume logic) """
		
		self.defineNodes()

		self.defineVolumes()


	def defineNodes(self):
		""" Define the nodes, by looking at 'gluster peer status' output """
		
		sys.stdout.write("Processing nodes"+" "*20+"\n\r\x1b[A")
		
		# We're using a peer status NOT pool list to determine cluster 
		# membership, so the first thing to do is create a node object for 
		# the localhost
		hostname = os.environ['HOSTNAME'].split('.')[0]
		
		# grab the uuid for the host the tool is running on
		uuid = open('/var/lib/glusterd/glusterd.info').readlines()[0].strip()
		
		connected = '1' if portOpen('localhost',24007) else '0'
		
		new_node = Node(hostname,uuid,connected)	# assuming local node is actually working!

		self.node[hostname] = new_node
		
		
		# define the fields that we're interested in 
		field_list = ['hostname','uuid','connected']
		
		# Issue the command to get the list of peers in the cluster
		# and set up the node objects
		(rc, peer_list) = issueCMD('gluster peer status --xml')
		if rc == 0:
			xml_string = ''.join(peer_list)
			xml_root = ETree.fromstring(xml_string)

			peer_list = xml_root.findall('.//peer')
			for peer in peer_list:
				
				node_info = getAttr(peer,field_list)

				new_node = Node(node_info['hostname'],
						node_info['uuid'],
						node_info['connected'])
						
				self.node[node_info['hostname']] = new_node
		
		

	def defineVolumes(self):
		""" Create the volume + brick objects """
		
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
			
			# add information about any volume options
			opt_nodes = vol_object.findall('.//option')
			for option in opt_nodes:
				for n in option.getchildren():
					if n.tag == 'name':
						key = n.text
					elif n.tag == 'value':
						value = n.text
						new_volume.options[key]=value
			
			# get bricks listed against this volume, and create the Brick object(s)
			brick_nodes = vol_object.findall('.//brick')
			
			# list holding brick paths
			repl = []
			ctr = 1
			
			for brick in brick_nodes:
				
				brick_path = brick.text
				(hostname,pathname) = brick_path.split(':')
				new_brick = Brick(brick_path, self.node[hostname])

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
			# is replicated and hasn't has self-heal explicitly disabled the
			# self heal state is inferred against the nodes that contain the 
			# bricks for the volume. With this state in place, the updateState
			# method can cross check to see what is actually happening

			if 'replicate' in new_volume.typeStr.lower():
				
				enable_self_heal = False		# assume it's off
					
				if 'cluster.self-heal-daemon' in new_volume.options:
					if new_volume.options['cluster.self-heal-daemon'].lower() in ['on','true']:
						enable_self_heal = True
				else:
					# replicated volume, without a self-heal-daemon setting - default is ON
					enable_self_heal = True

				if enable_self_heal:
					for brick_path in new_volume.brick:
						(hostname,brick_fsname) = brick_path.split(':')
						#new_volume.brick[brick_path].self_heal_enabled = True
						self.node[hostname].self_heal_enabled = True
						


	def getVersion(self):
		""" return the version of gluster """
		(rc, versInfo) = issueCMD("gluster --version")
		return versInfo[0].split()[1]
		

	def numVolumes(self):
			return len(self.volume)

	def numNodes(self):
		return len(self.node)

	def numBricks(self):
		return len(self.brick)

	def checkNodes(self):
		""" Count no. of nodes in an up state """
		ctr = 0
		for hostname in self.node:
			if self.node[hostname].state == '1':
				ctr += 1
			else:
				self.messages.append("%s is down"%(hostname))
				self.status = 'unhealthy'
				
		# if all the nodes are down - cluster state is Down
		if ctr == 0:
			self.status = 'down'
		
		return ctr

	def checkBricks(self):
		""" return the number of bricks in an up state """
		ctr = 0
		for brick_name in self.brick:
			if self.brick[brick_name].up:
				ctr +=1
			else:
				self.messages.append("Brick %s is down/unavailable"%(brick_name))

		return ctr


	def checkVolumes(self):
		""" return the number of volumes in an up state """
		
		ctr = 0 

		for volume_name in self.volume:
			if self.volume[volume_name].volume_state == 'up':
				ctr += 1
				continue
				
			# if this volume is down or in a partial state - propagate to the cluster
			if self.volume[volume_name].volume_state in ['down','up(partial)']:
				self.status = 'unhealthy'				
				
		return ctr
		
	def checkSelfHeal(self):
		""" return the number of nodes that have self-heal active """
		ctr = 0
		for node_name in self.node:
			if self.node[node_name].self_heal_active:
				ctr += 1
				
		return ctr

	def numSelfHeal(self):
		""" return the number of nodes with self heal enabled """
		ctr = 0
		for node_name in self.node:
			if self.node[node_name].self_heal_enabled:
				ctr += 1
				
		return ctr

	def updateState(self):
		""" update the state of the cluster by processing the output of 'vol status' commands
		
			- vol status all detail --> provides the brick info (up/down, type), plus volume capacity
			- vol status all --> self heal states 
		
		"""
		
		sys.stdout.write("Updating volume information"+" "*20+"\n\r\x1b[A")
		
		
		(rc, vol_status) = issueCMD("gluster vol status all detail --xml")
		
		if rc > 0:
			# unable to get updates from a vol status command
			self.messages.append('Unable to retrieve volume status information')
			return
			
		xml_string = ''.join(vol_status)
		xml_root = ETree.fromstring(xml_string)
		
		vol_elements = xml_root.findall('.//volume')
		
		for vol_object in vol_elements:
			
			volume_name = vol_object.find('./volName').text
			
			# Update the volume, to provide capacity and status information
			self.volume[volume_name].update(vol_object)
			
		# Now we look at a vol status output, to examine the self-heal states	
		(rc, vol_status) = issueCMD("gluster vol status --xml")
		if rc > 0:
			# unable to get updates from a vol status command
			self.messages.append('Unable to retrieve volume status information')
			return
			
		xml_string = ''.join(vol_status)
		xml_root = ETree.fromstring(xml_string)
		
		self_heal_list = []
		
		node_elements = xml_root.findall('.//node')
		
		# there's a big in 3.4, where when a node is missing the xml returned is malformed
		# returning a node within a node (the upper level nodes represents the missing
		# node slot I assume!)
		
		# To address, we look for the problem and work around it!
		for node in node_elements:
			
			if node.find('./node'):
				# reset the node elements to this inner level
				node_elements = node.findall('.//node')
				break
		
		# first get a list of self-heal elements from the xml
		for node in node_elements:
				
			if node.find('./hostname').text == 'Self-heal Daemon':
				self_heal_list.append(node)
				
		# Process the list, updating the node's self-heal state
		for sh_node in self_heal_list:
			node_name = sh_node.find('./path').text
			node_state = sh_node.find('./status').text
			
			node_name = os.environ['HOSTNAME'].split('.')[0] if node_name == 'localhost' else node_name

			if node_state == '1':
				self.node[node_name].self_heal_active = True
			else:
				self.node[node_name].self_heal_active = False
		
		# Propagate the self heal states to the clusters volume(s)
		for vol_name in self.volume:
			this_vol = self.volume[vol_name]
			this_vol.updateSelfHeal()

class Node:
	""" Node object, just used as a container as a parent for bricks """
	
	node_state = { '0':'down', '1':'up'}

	def __init__(self,node,uuid,state):
		self.node_name = node
		self.uuid=uuid
		self.state=state		# index for node_state dict
		self.state_text = Node.node_state[state]
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
	volume_attr = ['name', 'status', 'type', 'typeStr', 'replicaCount']

	# status - 1=started, 2 = stopped
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
		self.brick_total = 0
		self.replica_set=[]	   		# list, where each item is a tuple, of brick objects
		self.replica_set_state=[]  	# list show number of bricks offline in each repl set
		self.status_string = ''

		self.options = {} 
		self.raw_capacity = 0
		self.raw_used = 0
		self.usable_capacity = 0
		self.used_capacity = 0
		self.nfs_enabled = True
		self.self_heal_enabled = False
		self.self_heal_string = ''

		
		

	def update(self, volume_xml):
		""" receive an xml document containing volume's attributes, process
			each element updating the volume info and associated 
			brick information/state
		"""
			
		# Node elements correspond to a brick associated with this volume
		# so we first process the node elements to determine brick state
		for node in volume_xml.findall('.//node'):
			node_info = {}
			for brick_info in node.getchildren():
				node_info[brick_info.tag] = brick_info.text

			# Bug in gluster 3.4 malformed XML when a node is missing
			try:
				
				brick_path = node_info['hostname'] + ":" + node_info['path']
				
			except:
				
				print "Malformed XML detected - node element, without a 'hostname' tag"
				
				# skip this node element and continue with the next one
				continue

			this_brick = self.brick[brick_path]	
			brick_state = True if node_info['status'] == '1' else False
			
			# update this brick
			this_brick.update(brick_state,
					int(node_info['sizeTotal']),
					int(node_info['sizeFree']),
					node_info['fsName'],
					node_info['device'],
					node_info['mntOptions'])
					
			self.raw_capacity += int(node_info['sizeTotal'])
			self.raw_used += int(node_info['sizeTotal']) - int(node_info['sizeFree'])


		# ----------------------------------------------------------------
		# Brick info has been updated, we can calculate the volume capacity
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
					self.volume_state += '(partial)'
	


	def pctUsed(self):
		""" PLACEHOLDER """
		pass
	
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

	def updateSelfHeal(self):
		""" Updates the state of self heal for this volume """
		
		# first check if this volume is a replicated volume, if not
		# set the state string to "not applicable"
		if 'replicate' not in self.typeStr.lower():
			self.self_heal_string = 'N/A'
			
		# so it's replicated, but is self-heal disabled?	
		elif 'cluster.self-heal-daemon' in self.options:
			if self.options['cluster.self-heal-daemon'].lower() in ['off','false']:
				self.self_heal_string = 'DISABLED'
			else:
				self.self_heal_string = self.calcSelfHealStr()
		else:
			self.self_heal_string = self.calcSelfHealStr()
			
	def calcSelfHealStr(self):
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

class Brick:
	""" Brick object populated initially through vol info, and then updated
		with data from a vol status <bla> detail command """
		
	def __init__(self, brick_path, node_instance):
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

def getAttr(element,match_list):
	""" function to convert an xml node element with attributes, to a dict """
	
	attr_list = {}
	for node in element.getchildren():
		if node.tag in match_list:
			attr_list[node.tag] = node.text

	return attr_list
