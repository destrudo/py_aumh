###############################################################################
#                                 aumh.py                                     #
#                                                                             #
# Python library for controlling an arduino using Arduino_UART_MessageHandler #
#                                                                             #
# This is the 'base' library which handles all of the lowest level stuff.     #
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
import math #We needed the ceil() function.
import multiprocessing
import logging

# Debug value
DEBUG=0

# Baud rate default value
BAUD=250000

# Header data dictionary
headerOffsets = {
	"key_start":0,
	"msg_frag":1,
	"cmd_0":2,
	"cmd_1":3,
	"scmd":4,
	"version":5,
	"out_0":6,
	"out_1":7,
	"in_0":8,
	"in_1":9,
	"sum":10,
	"key_end":11
}

# Response data values, seems silly but it might come in
r_ack = "ACK\r\n"
r_nak = "NAK\r\n"

# Fragmentation response values
g_uart_frag_ok = "CT"
g_uart_frag_bad = "FF"

# Arduino serial fifo size (-1, since we can't actually fill it up.)
arduino_frag_size = 63
arduino_frag_wait_sec = 2

# isInt
#
# @i, type that can be casted to int.
# @ret, true or false depending on the cast ability.
def isInt(i):
	try:
		int(i)
		return True
	except ValueError:
		return False

# to_bytes
#
# @n, integer value
# @length, size in bytes that the integer should become
# @endianess, guess.
def to_bytes(n, length, endianess='big'):
	#print("to_bytes n is: '%s'" % str(n))
	h = '%x' % n
	s = ('0'*(len(h) % 2) + h).zfill(length*2).decode('hex')
	return s if endianess == 'big' else s[::-1]

# listOverlay
#
# @listBase, original list you wish you change.
# @listAdd, list that you want to put on top of listBase
# @offset, index offset you want to start listAdd at.
def listOverlay(listBase, listAdd, offset):
	for entry in range(0, len(listAdd)):
		if (entry + offset) >= len(listBase): #safety incase of insanity
			listBase.append(listAdd[entry])
		else:
			listBase[entry + offset] = listAdd[entry]

	return listBase

# lrcsum
#
# @dataIn, list of ints (Less than 255)
# @ret, sum output
def lrcsum(dataIn):
	lrc = 0

	for b in dataIn:
		lrc ^= struct.unpack('B', str(b))[0]

	return to_bytes(lrc, 1, 1)

# This is the UART_MH class.  Only one class instance per serial device unless
# you want to see resource conflicts.
class aumh:
	def __init__(self, serialInterface=None, lbaud=None, logmethod=None, logfile=None):

		self.logmethod = logmethod
		if logfile:
			self.logConfigure(logfile)

		self.running = False
		if serialInterface:
			self.serName = serialInterface
			self.begin()
			self.running = True
		else:
			self.serName = None

		#This.... sorta sucks...
		if lbaud:
			global BAUD
			BAUD = lbaud

	def logConfigure(self, logfile=None):
		if self.logmethod == "logger":
			if not logfile:
				print("aumh.logConfigure() called as logger type without filename for log.")
				sys.exit(1)

			self.logger = logging.getLogger("aumh")
			self.logger.setLevel(logging.INFO)
			self.logformatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
			self.loghandler = logging.FileHandler(logfile)
			self.loghandler.setFormatter(self.logformatter)
			self.logger.addHandler(self.loghandler)


	def log(self, data, mode=None):
		if (not self.logmethod) or (self.logmethod == "print"):
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

	#This should just get moved into the constructor.
	def begin(self):
		if not self.serName:
			print("UART_MH.begin, serial interface not configured!")
			sys.exit(1)

		self.serialSema = multiprocessing.Semaphore()
		#Here we define a bunch of class variables
		self.serialBaud = BAUD #This is the baud rate utilized by the device, we should probably define this higher for easy access.

		self.key_start = '\xaa'
		self.key_end = '\xfb'
		self.body_end = '\xdead' #We don't need this at the moment.
		self.uart_frag_ok = "CT"
		self.uart_frag_bad = "FF"

		self.ser = None

		self.mhcommands = {
			"mhconfig":b'\x00\x00', #This isn't used, but  it will be.
			"digital":b'\x01\x00',
			"neopixel":b'\x02\x00',
		}

		self.versions = [ 0x00 ] #This variable must be adjusted to accomodate
								# other compatible firmware versions.

		#Header length info
		self.header = {
			"key_start":1,
			"msg_frag":1,
			"cmd":2,
			"scmd":1,
			"version":1,
			"out":2,
			"in":2,
			"sum":1,
			"key_end":1,
		}

		#Get the total header length based on the above framework.  (Just so that we don't need to change a def if the header changes later)
		self.headerlen = 0
		for item in self.header:
			self.headerlen+=self.header[item]

		#self.serName = serialInterface
		self.version = 0x00 #We should sort by largest and select the highest one

		self.serialReset()

		self.running = True

	#  This method performs a hard open/close of the serial device for 
	# situations where calling open() just wasn't enough.
	def serialReset(self):
		if not isinstance(self.ser, serial.Serial):
			try:
				self.ser = serial.Serial(str(self.serName), self.serialBaud, timeout=5)
			except:
				self.log("UART_MH.serialReset() unable to create new serial instance.","err")
				return -1
		else:
			try:
				self.ser.close()
			except:
				pass #We don't care if it failed.

			self.ser = None
			try:
				self.ser = serial.Serial(str(self.serName), self.serialBaud, timeout=5)
			except:
				self.log("UART_MH.serialReset() unable to create new serial instance from previous instance.","err")
				return -1

		try:
			if not self.ser.isOpen():
				try:
					self.ser.open()
				except:
					self.log("UART_MH.serialReset() unable to open serial interface.","err")
					return -2
		except:
			self.log("UART_MH.serialReset() unable to call serial.isOpen().","err")
			return -3

		return 0


	#This prepares the initial message based on the main command type
	def assembleHeader(self,messageType):
		outBuf = [
			self.key_start,
			b'\x00',	#This is the fragment set, this needs to be set in finishMessage
			b'\x00',	#These are the two commands, they'll get set afterwards.
			b'\x00',	#cmd 1
			b'\x00',	#subcommand
			to_bytes(self.version, 1, 1), #We always want to present the highest compat version.
			b'\x00',	#out 0
			b'\x00',	#out 1
			b'\x00',	#in 0
			b'\x00',	#in 1
			b'\x00',	#sum, needs to be here as a dummy for the classes to populate via .append()
			self.key_end,
		]

		listOverlay(outBuf, self.mhcommands[messageType], headerOffsets["cmd_0"]) #Shifted the offset over to accomodate the fragment

		return outBuf


	#Compute the lrcsum for the message
	def finishMessage(self,curMsg):
		if len(curMsg) > 63:
			msgFrags = int(math.ceil((float(len(curMsg))/float(63))))
			if (msgFrags <= 255): #If it's in our range, cool, we'll set it.
				curMsg[headerOffsets["msg_frag"]] = to_bytes(msgFrags, 1)
		
		#Provided we don't move the sum to some strange place, this should be fine.
		curMsg[headerOffsets["sum"]] = lrcsum(curMsg[:headerOffsets["sum"]])

		return curMsg

	#wait for uart input to contain expected characters within timeout seconds
	def UARTWaitIn(self, timeout, expected=5):
		ltimeout = time.time() + timeout
		if not isinstance(self.ser, serial.Serial):
			self.log("UART_MH.UARTWaitIn(), serial instance does not exist.")
			return -1

		counter = 0

		try:
			while self.ser.inWaiting() < expected : #While we have no input data
				if (counter % 1000) == 0:
					if time.time() > ltimeout:
						return 1
				counter+=1
		except:
			self.log("UART_MH.UARTWaitIn(), failed to read serial interface.","err")
			self.ser.flush()
			return -1

		self.ser.flush()
		return 0


	#This sends the message
	def sendMessage(self,buf):
		t_000 = time.time()

		if isinstance(buf, int):
			self.log("UART_MH.sendMessage(), buffer incomplete.","warn")
			return 1
	
		self.serialSema.acquire()

		try:
			if isinstance(self.ser, serial.Serial):
				if not self.ser.isOpen():
					if self.serialReset():
						self.log("UART_MH.sendMessage(), Serial reset failed.","err")
						self.serialSema.release()
						return 2
			else:
				if self.serialReset():
					self.log("UART_MH.sendMessage(), serial create failed.","crit")
					self.serialSema.release()
					return 2

		except:
			self.log("UART_MH.sendMessage(), failed when polling serial interface.","err")
			self.serialSema.release()
			return 2

		msgFrag = struct.unpack('B', str(buf[headerOffsets["msg_frag"]]))[0]

		# If we are using fragmentation for this packet series.
		if (int(msgFrag) > 0):
			chunkTL = 0

			#Split the buffer into msg_frag lists 64 elements in size
			packetChunks = [ buf[ x:(x+arduino_frag_size) ] for x in xrange(0, len(buf), arduino_frag_size) ]
	
			for chunk in packetChunks:
				chunkTL = time.time() + arduino_frag_wait_sec #2 seconds to complete each chunk.
				chunkComplete = False

				while not chunkComplete:
					if time.time() > chunkTL:
						self.log("UART_MH.sendMessage(), chunk send timed out, abandoning attempt.")
						self.serialSema.release()
						return 20

					for b in chunk:
						try:
							self.ser.write(b)
						except:
							self.log("UART_MH.sendMessage(), failed to write to serial interface with fragment.")
							self.serialSema.release()
							#  If we have a failure to write, it's unlikely that we'll get it on the second pass.
							# Bail out now so that the controller doesn't need to deal with bullshit.
							return 11 

					state = self.ser.readline()

					if state.startswith(g_uart_frag_bad):
						time.sleep(0.1)

					elif state.startswith(g_uart_frag_ok):
						chunkComplete = True

						break #We probably don't need the stupid chunkComplete stuff.

		# If we are NOT using fragmentation...
		else:
			for b in buf:
				try:
					self.ser.write(b)
				except:
					self.log("UART_MH.sendMessage(), failed to write to serial interface")
					self.serialSema.release()
					return 10

		if self.UARTWaitIn(5):
			self.log("UART_MH.sendMessage(), input data timed out.")
			self.serialSema.release()
			return 4
	
		retd=""

		try:
			#We can no longer simply perform a readline for this command.  We should read until no more data is in the buffer.
			retd = self.ser.readline()

			#time.sleep(0.01)
			#If we still have data after performing the readline, continue reading lines.
			while(self.ser.inWaiting()):
				retd+=self.ser.readline()
				time.sleep(0.05) #I really do not want this delay here, but I can't think of a better way
				self.log("Read another line during message")


		except:
			self.log("UART_MH.sendMessage(), failed to readline (Response data unknown).")
			self.serialSema.release()
			return 5

		self.serialSema.release()

		if retd.startswith(r_ack):
			return 0

		#This is for the scenario where data beyond an ACK is returned (Such as the digital.get() method.)
		if r_ack in retd:
			return retd #Return the data in its raw form.

		return 7

	# Send a management message request to the firmware.
	def sendManageMessage(self,buf):
		if isinstance(buf, int):
			self.log("UART_MH.sendManageMessage(), buffer incomplete.")
			return 1

		self.serialSema.acquire()

		try:
			if isinstance(self.ser, serial.Serial):
				if not self.ser.isOpen():
					if self.serialReset():
						self.log("UART_MH.sendManageMessage(), serial reset failed.")
						self.serialSema.release()
						return 2
			else:
				if self.serialReset():
					self.log("UART_MH.sendManageMessage(), serial create failed.")
					self.serialSema.release()
					return 2	
		except:
			self.log("UART_MH.sendManageMessage(), failed when polling serial interface.")
			self.serialSema.release()
			return 2

		for b in buf:
			try:
				self.ser.write(b)
			except:
				self.log("UART_MH.sendManageMessage(), failed to write to serial interface")
				self.serialSema.release()
				return 10

		#Custom timing method
		ltimeout = time.time() + 1

		counter = 0

		try:
			#When it opens break
			while not self.ser.inWaiting():
				if (counter % 1000) == 0:
					if time.time() > ltimeout:
						self.log("UART_MH.sendManageMessage(), timeout in first completion loop.")
						self.serialSema.release()
						return 1
				counter+=1
		except:
			self.log("UART_MH.sendManageMessage(), failed when waiting for first response.")
			self.serialSema.release()
			return 4

		ltimeout = time.time() + 1
		complete = False
		counter = 0
		oBuf = ""

		while not complete:
			if (counter % 1000) == 0:
				if time.time() > ltimeout:
					self.log("UART_MH.sendManageMessage(), timeout in second completion loop.")
					self.serialSema.release()
					return 5

			try:
				while self.ser.inWaiting() > 0:
					oBuf+=self.ser.read(1)
			except:
				self.log("UART_MH.sendManageMessage(), failed when waiting for second response.")
				self.serialSema.release()
				return 6

			#If we've got at least 5 characters we can start performing the checks....
			if len(oBuf) >= 5:
				if oBuf[-5:].startswith("ACK") or oBuf[:5].startswith("NAK"):
					#We're good (Possibly)
					break

			counter+=1

		self.serialSema.release()

		return oBuf