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

from functions.syscalls	import issueCMD
from functions.utils	import displayBytes
from classes.gluster	import Cluster, Volume, Brick

# Known issues;
# if the checks are done right after a node down event, the vol status query does not
# complete and ends up blocking on the originating node until the node timeout occurs.

def main():
	
	print " "			# add some spacing to make the output stand out more

	cluster.initialise()

	cluster.updateState()

	active_nodes = cluster.checkNodes()
	active_bricks = cluster.checkBricks()
	active_volumes = cluster.checkVolumes()
	active_self_heal = cluster.checkSelfHeal()
	
	if status_request:

		print "Cluster Summary: %s"%(cluster.status).upper().ljust(50)
		print ("  Version - %s  Nodes - %2d/%2d  Bricks - %2d/%2d  Volumes - %2d/%2d  Self-Heal - %2d/%2d"
			%(cluster.glfs_version,
			active_nodes,cluster.numNodes(),
			active_bricks,cluster.numBricks(),
			active_volumes,cluster.numVolumes(),
			active_self_heal,cluster.numSelfHeal()))

		print "\nVolume Summary"
		for vol_name in cluster.volume:
			vol = cluster.volume[vol_name]
			(up,all) = vol.brickStates()
			print ("\t%s %s - %d/%d bricks up - %s"
				%(vol_name.ljust(16,' '), 
				vol.volume_state.upper(),
				up,all,
				vol.typeStr))
			print ("\t" + " "*17 + "Capacity: %s/%s (used,total)"
				%(displayBytes(vol.used_capacity),
				displayBytes(vol.usable_capacity)))
			print ("\t" + " "*17 + "Self Heal: %s"%(vol.self_heal_string))
			print ("\t" + " "*17 + "Enabled Protocols: Native:%s  NFS:%s  SMB:%s"
				%(vol.protocol['NATIVE'],vol.protocol['NFS'], vol.protocol['SMB']))
				

	print "\nStatus Messages"
	if cluster.messages:
		
		# Add the current cluster state as the first message to display
		cluster.messages.insert(0,"Cluster is %s"%(cluster.status.upper()))
		for info in cluster.messages:
			print "\t- " + info
			
	else:
		print "\t Cluster is healthy, all checks successful"

	print


if __name__ == '__main__':
	
	usageInfo = "usage: %prog [options]"
	
	parser = OptionParser(usage=usageInfo,version="%prog 0.2")
	parser.add_option("-s","--status",dest="status",action="store_true",default=True,help="Show highlevel health of the cluster")
	parser.add_option("-v","--volume",dest="volumes", help="Volume level view (NOT IMPLEMENTED YET!)")
	parser.add_option("-a","--all",dest="everything",action="store_true",default=False,help="Show all cluster information")
	parser.add_option("--xml",dest="xml",action="store_true",default=False,help="produce output in XML format (NOT IMPLEMENTED YET!)")
	(options, args) = parser.parse_args()

	status_request = options.status
	volume_request = options.volumes
	
	if options.everything:
		status_request = True
		volume_request = True

	# Create a cluster object. This will init the cluster with the current
	# node,volume and brick counts
	cluster = Cluster()
	
	main()

