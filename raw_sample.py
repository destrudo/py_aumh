#!/usr/bin/python

from aumh import *
import pprint
import sys
import time
import binascii

UMH_00 = aumh("/dev/ttyUSB0")

CFGI = aumhConfig(UMH_00)
umhNPInstance = aumhNeopixel(UMH_00)
umhInstance = aumhDigital(UMH_00)
mgmtO = CFGI.cfg_manage()

print "Manage data: "
pprint.pprint(mgmtO)

print "Running NP get"
pprint.pprint(umhNPInstance.np_get(0,{ "id":0 }))

print "Running NP add"
umhNPInstance.np_add(0,3,100)

print "Running NP add"
umhNPInstance.np_add(1,6,100)

print "Running NP add"
umhNPInstance.np_add(2,10,100)

while (True):
	print "Setting gradient."
	umhNPInstance.np_gradient(0, { "start":0, "end":100, "startColor":[255,100,0], "endColor":[0,100,100] })

	print "Running NP get 3"
	pprint.pprint(umhNPInstance.np_get_all(0,{ "id":0 }))

	print "Clearing."
	umhNPInstance.np_clear(0)

	time.sleep(1)