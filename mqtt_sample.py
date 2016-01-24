#!/usr/bin/python

###############################################################################
#                                  mqttTest.py                                #
#                                                                             #
# This is a sample application implementation for UART_MH_MQTT.               #
#                                                                             #
# Copyright(C) 2015, Destrudo Dole                                            #
#                                                                             #
# This program is free software; you can redistribute it and/or modify it     #
# under the terms of the GNU General Public License as published by the Free  #
# Software Foundation, version 2 of the license.                              #
###############################################################################

from aumh import *
import pprint
import time

mqttI = aumhMQTT("127.0.0.1",1883)
UMH_00 = aumh("/dev/ttyUSB0")

#Instance all of the instances you want!
uartNeopixel_00 = aumhNeopixel(UMH_00)
uartConfig_00 = aumhConfig(UMH_00)
uartDigital_00 = aumhDigital(UMH_00)

#add all the instances you want.
mqttI.add_instance("mhconfig", uartConfig_00, uartConfig_00.device.identityS)
mqttI.add_instance("neopixel", uartNeopixel_00, uartNeopixel_00.device.identityS)
mqttI.add_instance("digital", uartDigital_00, uartDigital_00.device.identityS)

#This will run forever.
mqttI.run()