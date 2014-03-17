#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  gstatus.py
#  
#  Copyright 2014 Paul Cuzner 
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
from 	optparse 	import OptionParser			# command line option parsing
import 	os

from gstatus.functions.syscalls	import issueCMD
from gstatus.functions.utils	import displayBytes
from gstatus.classes.gluster	import Cluster, Volume, Brick

MIN_VERSION = 3.4

# Known issues;
# if the checks are done right after a node down event, the vol status query does not
# complete and ends up blocking on the originating node until the node timeout occurs.

def main():
	
	print " "			# add some spacing to make the output stand out more
	
	cluster.initialise()
	cluster.updateState()
	cluster.calcCapacity()

	active_nodes = cluster.activeNodes()
	active_bricks = cluster.activeBricks()
	active_self_heal = cluster.checkSelfHeal()
	
	cluster.healthChecks()
	
	if cluster.messages:
		status_msg = "%s(%d)"%(cluster.status.upper(),len(cluster.messages))
	else:
		status_msg = cluster.status.upper()

	print ("      Status: %s Capacity: %s(raw bricks)"%(status_msg.ljust(17),
			displayBytes(cluster.raw_capacity,display_units)))
		
	print ("   Glusterfs: %s           %s(usable)\n"%(cluster.glfs_version.ljust(17),
			displayBytes(cluster.usable_capacity,display_units)))	
	
	if state_request:
		
		print ("   Nodes    : %2d/%2d\t\tVolumes: %2d Up"
				%(active_nodes,cluster.numNodes(),
				cluster.volume_summary['up']))

		print ("   Self Heal: %2d/%2d\t\t         %2d Up(Degraded)"
				%(active_self_heal,cluster.numSelfHeal(),
				cluster.volume_summary['degraded']))

		print ("   Bricks   : %2d/%2d\t\t         %2d Up(Partial)"
				%(active_bricks,cluster.numBricks(),
				cluster.volume_summary['partial']))

		print (" "*41 + "%2d Down"
				%(cluster.volume_summary['down']))

	if volume_request:
		print "Volume Information"
		
		for vol_name in cluster.volume:
			
			if len(volume_list) == 0 or vol_name in volume_list:
				vol = cluster.volume[vol_name]
				(up,all) = vol.brickStates()
				print ("\t%s %s - %d/%d bricks up - %s"
					%(vol_name.ljust(16,' '), 
					vol.volume_state.upper(),
					up,all,
					vol.typeStr))
				print ("\t" + " "*17 + "Capacity: (%d%% used) %s/%s (used/total)"
					%(vol.pct_used,
					displayBytes(vol.used_capacity,display_units),
					displayBytes(vol.usable_capacity,display_units)))
				print ("\t" + " "*17 + "Self Heal: %s"%(vol.self_heal_string))
				print ("\t" + " "*17 + "Protocols: glusterfs:%s  NFS:%s  SMB:%s"
					%(vol.protocol['NATIVE'],vol.protocol['NFS'], vol.protocol['SMB']))
					
				if volume_layout:
					print
					vol.printLayout()	
					
					
				print
				
	if state_request:
		print "Status Messages"
		if cluster.messages:
			
			# Add the current cluster state as the first message to display
			cluster.messages.insert(0,"Cluster is %s"%(cluster.status.upper()))
			for info in cluster.messages:
				print "  - " + info
				
		else:
			print "  - Cluster is HEALTHY, all checks successful"

	print


if __name__ == '__main__':
	
	usageInfo = "usage: %prog [options]"
	
	parser = OptionParser(usage=usageInfo,version="%prog 0.46")
	parser.add_option("-s","--state",dest="state",action="store_true",help="show highlevel health of the cluster")
	parser.add_option("-v","--volume",dest="volumes", action="store_true",help="volume info (default is ALL, or supply a volume name)")
	parser.add_option("-a","--all",dest="everything",action="store_true",default=False,help="show all cluster information")
	parser.add_option("-u","--units",dest="units",choices=['bin','dec'],help="display capacity units in DECimal or BINary format (GB vs GiB)")
	parser.add_option("-l","--layout",dest="layout",action="store_true",default=False,help="show brick layout when used with -v, or -a")
	#parser.add_option("--xml",dest="xml",action="store_true",default=False,help="produce output in XML format (NOT IMPLEMENTED YET!)")
	(options, args) = parser.parse_args()

	state_request = options.state
	volume_request = options.volumes
	
	volume_layout = options.layout
	
	display_units = options.units if options.units else 'bin'
	
	volume_list = []				# empty list of vols = show them all 
	
	if volume_request and args:
		volume_list = args
		
	
	if options.everything:
		state_request = True
		volume_request = True

	# Create a cluster object. This simply creates the structure of 
	# the object and populates the glusterfs version 
	cluster = Cluster()
	
	if cluster.glfsVersionOK(MIN_VERSION):
		
		main()
		
	else:
		
		print "gstatus is not compatible with this version of glusterfs %s"%(cluster.glfs_version)
		exit(16)


