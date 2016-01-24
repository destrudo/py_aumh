###############################################################################
#                                aumhConfig.py                                #
#                                                                             #
# Python library for controlling an arduino using Arduino_UART_MessageHandler #
#                                                                             #
# This is the configuration library which controls all of the 'base' level    #
#  configuration methods for the firmware.                                    #
#                                                                             #
# Copyright(C) 2015, Destrudo Dole                                            #
#                                                                             #
# This program is free software; you can redistribute it and/or modify it     #
# under the terms of the GNU General Public License as published by the Free  #
# Software Foundation, version 2 of the license.                              #
###############################################################################

from __future__ import print_function

import serial
import pprint
import sys
import struct
import time
import socket
import logging

from aumh import *
from aumh import isInt
from aumh import to_bytes
from aumh import listOverlay
from aumh import aumh

class aumhConfig:
	def __init__(self, UMH_Instance, logmethod=None, logfile=None):
		self.logmethod = logmethod
		if logfile:
			self.logConfigure(logfile)

		self.device = UMH_Instance

		self.subcommands = {
			"manage":b'\xff'
		}

		self.id = None

		if self.device.running == False:
			self.device.begin()

		#For right now, we're gonna do it this way....
		good = False
		while not good:
			if not self.cfg_manage():
				self.log("Got no data from manage.")
				time.sleep(10)
				continue

			break

	def logConfigure(self, logfile=None):
		if self.logmethod == "logger":
			if not logfile:
				print("aumh.logConfigure() called as logger type without filename for log.")
				sys.exit(1)

			self.logger = logging.getLogger("aumhConfig")
			self.logger.setLevel(logging.INFO)
			self.logformatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
			self.loghandler = logging.FileHandler(logfile)
			self.loghandler.setFormatter(self.logformatter)
			self.logger.addHandler(self.loghandler)


	def log(self, data, mode=None):
		if not self.logmethod or self.logmethod == "print":
			print(data)
		elif self.logmethod == "logger":
			if mode == "err":
				self.logger.error(data)
			elif mode == "warn":
				self.logger.warning(data)
			elif mode == "crit":
				self.logger.critical(data)
			else: #Mode is info or something else.
				self.logger.info(data)

	def createMessage(self, dataIn):
		if "command" not in dataIn or dataIn["command"] not in self.subcommands:
			return 3

		buffer = self.device.assembleHeader("mhconfig")

		if dataIn['command'] == "manage":
			buffer = self.lmanage(buffer)
			return buffer #special case (And only at time of writing)

		else:
			self.log("UART_Config.createMessage(), Unknown command.")
			return None

		buffer = self.device.finishMessage(buffer)

		return buffer

	def lmanage(self, buffer):
		buffer[headerOffsets["scmd"]] = self.subcommands["manage"]
		buffer[headerOffsets["out_0"]] = b'\x01' #This should actually call to_bytes and listOverlay.
		buffer = self.device.finishMessage(buffer)

		buffer.append('\x00')

		rawMsg = self.device.sendManageMessage(buffer)

		try:
			if "NAK" in rawMsg:
				self.log("Bad response in lmanage.")
				return None
		except:
			self.log("Exception in lmanage.", "err")
			return None

		#We could still have an issue though...
		outMsg = rawMsg[:-1 * (rawMsg.find(r_ack) + 1)]

		if len(outMsg) != 4: #If we don't have an appropriate value...
			return None


		#We need to read the first nibble for determining device type ahead of time.
		self.device.type = (struct.unpack("B", outMsg[0])[0] & 0x0F)

		#Here we store the device identity as an integer inside our device.
		self.device.identity = struct.unpack('I', outMsg)[0]
		
		#And gere that identity is as a string (Which we will also return.)
		self.device.identityS = "{:08x}".format(self.device.identity)

		return self.device.identityS

	def cfg_manage(self):
		data = {
			"command":"manage"
		}

		return self.createMessage(data)