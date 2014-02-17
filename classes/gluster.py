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



class Cluster:
	""" The cluster class is the parent of nodes, bricks and volumes """

	def __init__(self):
		self.glfs_version = ''	# version, or mixed
		self.msgs=[]
		self.node={}
		self.volume={}
		self.brick={}
		self.glfs_version = self.getVersion()
		self.raw_capacity = 0
		self.usable_capacity = 0
		self.messages = []
	
	def initialise(self):
		""" call the node, brick and volume 'generator' to create the child objects """
		
		self.defineNodes()

		self.defineBricks()
		
		self.defineVolumes()
		
		print "Analysis complete"+" "*20

	def defineVolumes(self):
		""" Create the volume objects """
		
		vol_list = os.listdir('/var/lib/glusterd/vols')

		for volume in vol_list:
			vol = Volume(volume)
			self.volume[volume] = vol

			sys.stdout.write("Processing volume %s\n\r\x1b[A"%(volume))
			
			# first populate the high level info from the output of a 
			# volinfo query
			vol.populate(self.brick)
			if vol.status == 1:
				vol.update()	# apply vol status detail information to meta data
				vol.calcState()	# assess status of the volume

	def defineNodes(self):
		""" Define the nodes, by looking at 'gluster pool list' output """
		
		sys.stdout.write("Processing nodes"+" "*20+"\n\r\x1b[A")
	
		# define the fields that we're interested in 
		field_list = ['hostname','uuid','connected']

       		(rc, peer_list) = issueCMD('gluster pool list --xml')
		if rc == 0:
			xml_string = ''.join(peer_list)
			xml_root = ETree.fromstring(xml_string)

			peer_list = xml_root.findall('.//peer')
			for peer in peer_list:
				node_info = getAttr(peer,field_list)

				if node_info['hostname'] == 'localhost':
					node_info['hostname'] = os.environ['HOSTNAME'].split('.')[0]

				new_node = Node(node_info['hostname'],
						node_info['uuid'],
						node_info['connected'])
				self.node[node_info['hostname']] = new_node

	def getVersion(self):
		""" return the version of gluster """
		(rc, versInfo) = issueCMD("gluster --version")
		return versInfo[0].split()[1]
		
	def defineBricks(self):
		""" Populate brick objects based on 'gluster vol info', and link them back
			to parent object(s) """
			
		sys.stdout.write("Processing Bricks"+" "*20+"\n\r\x1b[A")

		(rc, vol_info) = issueCMD("gluster vol info --xml")
		if rc == 0:
			xml_stream = ''.join(vol_info)
			xml_root = ETree.fromstring(xml_stream)
			brick_elements = xml_root.findall('.//brick')
			for brick in brick_elements:
				brick_path = brick.text
				(hostname,pathname) = brick_path.split(':')
				new_brick = Brick(brick_path)

				# Add the brick to the cluster
				self.brick[brick_path] = new_brick

				# add the brick to the owning node
				brick_owner = self.node[hostname]
				brick_owner.brick[brick_path] = new_brick

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

		for vol_name in self.volume:
			if self.volume[vol_name].volume_state == 'up':
				ctr += 1
		return ctr

class Node:
	""" Node object, just used as a container as a parent for bricks """
	
	node_state = { '0':'disconnected', '1':'connected'}

	def __init__(self,node,uuid,state):
		self.node_name = node
		self.uuid=uuid
		self.state=state		# index for node_state dict
		self.state_text = Node.node_state[state]
		self.brick = {}
		self.daemon_state = {}
		self.local=False		# is this the localhost?

	

class Volume:
	""" Volume object, linking out to the bricks, and holding the description
		of the volume's attributes """
		
	# Vol states are 
	#	ready		... defined, but not started
	# 	up		... all bricks online, operational
	# 	up(partial)	... one or more bricks offline, but replica in place
	# 	up(degraded) ... at least one replica set is offline
	# 	down		... volume is down/stopped

	volume_states = ['ready','up', 'down','up(partial)', 'up(degraded)']

	def __init__(self,vol_name):
		self.name = vol_name
		self.type = 0  		# 5=dist-repl
		self.type_string = ''
		self.volume_state = 'down'
		self.brick = {}
		self.brick_total = 0
		self.replica_set=[]	   # list, where each item is a tuple, of brick objects
		self.replica_set_state=[]  # list show number of bricks offline in each repl set
		self.replica_count=0
		self.status = 0		# 2=stopped, 1=started
		self.status_string = ''
		self.user_state = ''	# meaningful description of the volume's state
		self.options = {} 
		self.raw_capacity = 0
		self.raw_used = 0
		self.usable_capacity = 0
		self.used_capacity = 0


	def populate(self, cluster_brick):
		""" run vol info to create a volume object """
		
		(rc, vol_info) = issueCMD("gluster vol info %s --xml"%(self.name))
		
		xml_stream = ''.join(vol_info)
		xml_root = ETree.fromstring(xml_stream)

		vol = xml_root.find(".//volume")

		self.status = int(vol.find("./status").text)

		# may need to change the following assignment, based on further testing
		self.volume_state = Volume.volume_states[self.status]

		self.status_string = vol.find('./statusStr').text
		self.brick_count = int(vol.find('./brickCount').text)
		self.type = int(vol.find('./type').text)
		self.type_string = vol.find('./typeStr').text
		self.replica_count = int(vol.find('./replicaCount').text)

		# Cycle through options stanza - not really needed but could be 
		# used to infer volume use cases by the settings later
		opt_list = vol.findall('.//option')
		for option in opt_list:
			for n in option.getchildren():
				if n.tag == 'name':
					key = n.text
				elif n.tag == 'value':
					value = n.text
					self.options[key]=value


		brick_list = vol.findall('.//brick')
		ctr = 1
		repl = []
		for brick in brick_list:
			brick_path = brick.text

			if self.replica_count > 1:
				repl.append(brick_path)
				ctr +=1
				if ctr > self.replica_count:
					ctr = 1

					# add this replica set to the volume's info
					self.replica_set.append(repl)
					# drop all elements from temporary list
					repl =[]

			# Link the volume's brick reference to the brick object created earlier
			self.brick[brick_path] = cluster_brick[brick_path]

	def calcState(self):
		""" Process the bricks related to this volume, to refine it's state """
		
		if self.replica_count > 1:
			# this is a replicated volume, so check the status of the 
			# bricks in each replica set


			set_state = []
			for set in self.replica_set:
				state = 0		# initial state is 0 = all good

				for brick_path in set:
					if not self.brick[brick_path].up:
						state += 1
				set_state.append(state)

			self.replica_set_state = set_state	

			worst_set = max(set_state)
			# check if we have a problem
			if worst_set > 0:
				if worst_set == self.replica_count:
					self.volume_state += "(partial)"
				else:
					self.volume_state += "(degraded)"
		
		else:
			# this volume is not replicated, so brick disruption leads
			# to an 'partial' state
			total = self.numBricks()
			down = 0
			for brick_path in self.brick:
				if self.brick[brick_path].up:
					continue
				else:
					down += 1
			if down == total:
				self.volume_state = 'down'
			elif down > 0:
				self.volume_state += '(partial)'


					

	def update(self):
		""" run vol status detail for rhe volume and apply the info to 
		    the volume object """
		(rc,vol_status) = issueCMD("gluster vol status %s detail --xml"%(self.name))
		if rc == 0:
			xml_string = ''.join(vol_status)
			xml_root = ETree.fromstring(xml_string)
		for node in xml_root.findall('.//node'):
			node_info = {}
			for brick_info in node.getchildren():
				node_info[brick_info.tag] = brick_info.text

			# Bug in gluster 3.4 malformed XML when a node is missing
			try:
				brick_path = node_info['hostname'] + ":" + node_info['path']
			except:
				continue

			this_brick = self.brick[brick_path]	
			brick_state = True if node_info['status'] == '1' else False
			this_brick.update(brick_state,
					int(node_info['sizeTotal']),
					int(node_info['sizeFree']),
					node_info['fsName'],
					node_info['device'],
					node_info['mntOptions'])
			self.raw_capacity += int(node_info['sizeTotal'])
			self.raw_used += int(node_info['sizeTotal']) - int(node_info['sizeFree'])

		# if all the bricks are online the usable is simple
		(up_bricks, total_bricks) = self.brickStates()
		if up_bricks == total_bricks:
			self.usable_capacity = self.raw_capacity / self.replica_count
			self.used_capacity = self.raw_used / self.replica_count
		else:
			# have to account for the available space in each replica set
			# for the calculation
			if self.replica_count > 1:
				for set in self.replica_set:
					for brick_path in set:
						if self.brick[brick_path].up:
							self.usable_capacity += self.brick[brick_path].size
							self.used_capacity += self.brick[brick_path].used
							break

			else:
				self.usable_capacity = self.raw_capacity
				self.used_capacity = self.raw_used


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

class Brick:
	""" Brick object populated initially through vol info, and then updated
		with data from a vol status <bla> detail command """
		
	def __init__(self, brick_path):
		self.brick_path = brick_path
		self.node = brick_path.split(':')[0] 
		self.up = False 
		self.mount_options = {}
		self.fs_type = ''
		self.device = ''
		self.device_type = ''			# LVM, partition
		self.size = 0
		self.free = 0 
		self.used = 0

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
