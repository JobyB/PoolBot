#!/usr/bin/python

"""Simulates Aqualink PDA remote with a RS485 interface."""

from __future__ import (division, print_function)

import logging
import string
import serial
import struct
import sys
import time
import os


class Aqualink:

    # ASCII constants
    NUL = '\x00'
    DLE = '\x10'
    STX = '\x02'
    ETX = '\x03'

    # Address of Aqualink controller
    masterAddr = '\x00'

    # Address of PDA remote to emulate
    ID = '60'

    def __str__(self):
        return self.__class__.__name__ + ' Controller'

    def __init__(self, serial_dev):

        self.serial_dev = serial_dev
        self.port = None

        self.log = logging.getLogger(self.__class__.__name__)

        self.log.info('Init')
        self.log.debug('Using serial device: ' + self.serial_dev)

        # Check to see if the port exists, if we just booted it may take a little time to be available
        for i in range(5):
            if os.path.exists(self.serial_dev):
                break
            else:
                time.sleep(2)

        # Final check to make sure its there
        if os.path.exists(self.serial_dev):
            self.log.critical(self.serial_dev + ' does not exist')

        self.port = serial.Serial(self.serial_dev, baudrate=9600,
                                      bytesize=serial.EIGHTBITS,
                                      parity=serial.PARITY_NONE,
                                      stopbits=serial.STOPBITS_ONE,
                                      timeout=None)

        if self.port is None:
            self.log.critical('Unable to create port')


    def _sync(self):
        """Sync with the message bus"""

        # Init the msg so we enter the loop below
        data = Aqualink.NUL + Aqualink.NUL

        # Skip bytes until synchronized with the start of a message
        while (data[-1] != Aqualink.STX) or (data[-2] != Aqualink.DLE):
            data += self.port.read(1)

            if self.debugRawMsg:
                self.debugRaw(data[-1])

        self.log.info('Init complete')


    def readMsg(self):
        """ Read the next valid message from the serial port.
        Parses and returns the destination address, command, and arguments as a
        tuple."""

        while True:
            dleFound = False
            # read what is probably the DLE STX
            try:
                self.msg += self.port.read(2)
            except serial.SerialException:
                self.msg += chr(0) + chr(0)
                self._open()
            if debugRaw:
                self.debugRaw(self.msg[-2])
                self.debugRaw(self.msg[-1])
            while len(self.msg) < 2:
                self.msg += chr(0)
            while (self.msg[-1] != Aqualink.ETX) or (not dleFound) or (len(self.msg) > 128):
                # read until DLE ETX
                try:
                    if (self.port == None):
                        return {'dest': "ff", 'cmd': "ff", 'args': ""}
                    self.msg += self.port.read(1)
                except serial.SerialException:
                    self.msg += chr(0)
                    self._open()
                if debugRaw:
                    self.debugRaw(self.msg[-1])
                if self.msg[-1] == Aqualink.DLE:
                    # \x10 read, tentatively is a DLE
                    dleFound = True
                if (self.msg[-2] == Aqualink.DLE) and (self.msg[-1] == Aqualink.NUL) and dleFound:
                    # skip a NUL following a DLE
                    self.msg = self.msg[:-1]
                    # it wasn't a DLE after all
                    dleFound = False
                    # skip any NULs between messages
            self.msg = self.msg.lstrip(Aqualink.NUL)
            # parse the elements of the message
            dlestx = self.msg[0:2]
            dest = self.msg[2:3]
            cmd = self.msg[3:4]
            args = self.msg[4:-3]
            if cmd.encode("hex") == "04":
                ascii_args = " (" + filter(lambda x: x in string.printable, args) + ")"
            else:
                ascii_args = ""
            checksum = self.msg[-3:-2]
            dleetx = self.msg[-2:]
            self.msg = ""
            debugMsg = "IN dest=" + dest.encode("hex") + " cmd=" + cmd.encode("hex") + " args=" + args.encode(
                "hex") + ascii_args
            # stop reading if a message with a valid checksum is read
            if self.checksum(dlestx + dest + cmd + args) == checksum:
                if debugData:
                    if cmd.encode("hex") != "00" \
                            and cmd.encode("hex") != "01" \
                            and cmd.encode("hex") != "02":
                        if debugAll or dest.encode("hex") == "60":  # only log coms from master and PDA
                            log(debugMsg)
                if args == None:
                    args = ""
                return {'dest': dest.encode("hex"), 'cmd': cmd.encode("hex"), 'args': args}
            else:
                if debugData:
                    log(debugMsg, "*** bad checksum ***")

    def sendMsg(self, (dest, cmd, args)):
        """ Send a message.
        The destination address, command, and arguments are specified as a tuple."""
        msg = Aqualink.DLE + Aqualink.STX + dest + cmd + args
        msg = msg + self.checksum(msg) + Aqualink.DLE + Aqualink.ETX

        if debugData:
            if args.encode("hex") != "4000":  # don't log typical ACKs
                debugMsg = "OUT dest=" + dest.encode("hex") + " cmd=" + \
                           cmd.encode("hex") + " args=" + args.encode("hex")
                log(debugMsg)

        for i in range(2, len(msg) - 2):
            # if a byte in the message has the value \x10 insert a NUL after it
            if msg[i] == Aqualink.DLE:
                msg = msg[0:i + 1] + Aqualink.NUL + msg[i + 1:]
        n = self.port.write(msg)

    def checksum(self, msg):
        """ Compute the checksum of a string of bytes."""
        return struct.pack("!B", reduce(lambda x, y: x + y, map(ord, msg)) % 256)

    def debugRaw(self, byte):
        """ Debug raw serial data."""
        self.debugRawMsg += byte
        if ((len(self.debugRawMsg) == 48) or (byte == Aqualink.ETX)):
            log(self.debugRawMsg.encode("hex"))
            self.debugRawMsg = ""


    def sendAck(self, i):
        """Controller talked to us, send back our last keypress."""
        ackstr = "40" + self.nextAck  # was 8b before, PDA seems to be 400# for keypresses (4001-4006)
        i.sendMsg((chr(0), chr(1), ackstr.decode("hex")))
        self.nextAck = "00"

    def setNextAck(self, nextAck):
        """Set the value we will send on the next ack, but don't send yet."""
        self.nextAck = nextAck

    def sendKey(self, key):
        """Send a key (text) on the next ack."""
        keyToAck = {'up': "06", 'down': "05", 'back': "02", 'select': "04", 'but1': "01", 'but2': "03"}
        if key in keyToAck.keys():
            self.setNextAck(keyToAck[key])

    def processMessage(self, ret, i):
        """Process message from a controller, updating internal state."""
        if ret['cmd'] == "09":  # Clear Screen
            # What do the args mean?  Ignore for now
            if (ord(ret['args'][0:1]) == 0):
                self.cls()
            else:  # May be a partial clear?
                self.cls()
            # print "cls: "+ret['args'].encode("hex")
            self.sendAck(i)
        elif ret['cmd'] == "0f":  # Scroll Screen
            start = ord(ret['args'][:1])
            end = ord(ret['args'][1:2])
            direction = ord(ret['args'][2:3])
            self.scroll(start, end, direction)
            self.sendAck(i)
        elif ret['cmd'] == "04":  # Write a line
            line = ord(ret['args'][:1])
            if line == 64: line = 1  # time (hex=40)
            if line == 130: line = 2  # temp (hex=82)
            offset = 1
            text = ""
            while (ret['args'][offset:offset + 1].encode("hex") != "00") and (offset < len(ret['args'])):
                text += ret['args'][offset:offset + 1]
                offset = offset + 1
            self.writeLine(line, text)
            self.sendAck(i)
        elif ret['cmd'] == "05":  # Initial handshake?
            # ??? After initial turn on get this, rela box responds custom ack
            #            i.sendMsg( (chr(0), chr(1), "0b00".decode("hex")) )
            self.sendAck(i)
        elif ret['cmd'] == "00":  # PROBE
            self.sendAck(i)
        elif ret['cmd'] == "02":  # Status?
            self.setStatus(ret['args'].encode("hex"))
            self.sendAck(i)
        elif ret['cmd'] == "08":  # Invert an entire line
            self.invertLine(ord(ret['args'][:1]))
            self.sendAck(i)
        elif ret['cmd'] == "10":  # Invert just some chars on a line
            self.invertChars(ord(ret['args'][:1]), ord(ret['args'][1:2]), ord(ret['args'][2:3]))
            self.sendAck(i)
        else:
            log("UNKNOWN MESSAGE: cmd=" + ret['cmd'] + " args=" + ret['args'].encode("hex"))
            self.sendAck(i)



    def processMessage(ret, i):
        """Process message from a controller, updating internal state."""
        if ret['cmd'] == "09":  # Clear Screen
            self.sendAck(i)
        elif ret['cmd'] == "0f":  # Scroll Screen
            start = ord(ret['args'][:1])
            end = ord(ret['args'][1:2])
            direction = ord(ret['args'][2:3])
            self.scroll(start, end, direction)
            self.sendAck(i)
        elif ret['cmd'] == "04":  # Write a line
            line = ord(ret['args'][:1])
            if line == 64: line = 1  # time (hex=40)
            if line == 130: line = 2  # temp (hex=82)
            offset = 1
            text = ""
            while (ret['args'][offset:offset + 1].encode("hex") != "00") and (offset < len(ret['args'])):
                text += ret['args'][offset:offset + 1]
                offset = offset + 1
            self.writeLine(line, text)
            self.sendAck(i)
        elif ret['cmd'] == "05":  # Initial handshake?
            # ??? After initial turn on get this, rela box responds custom ack
            #            i.sendMsg( (chr(0), chr(1), "0b00".decode("hex")) )
            self.sendAck(i)
        elif ret['cmd'] == "00":  # PROBE
            self.sendAck(i)
        elif ret['cmd'] == "02":  # Status?
            self.setStatus(ret['args'].encode("hex"))
            self.sendAck(i)
        elif ret['cmd'] == "08":  # Invert an entire line
            self.invertLine(ord(ret['args'][:1]))
            self.sendAck(i)
        elif ret['cmd'] == "10":  # Invert just some chars on a line
            self.invertChars(ord(ret['args'][:1]), ord(ret['args'][1:2]), ord(ret['args'][2:3]))
            self.sendAck(i)
        else:
            log("UNKNOWN MESSAGE: cmd=" + ret['cmd'] + " args=" + ret['args'].encode("hex"))
            self.sendAck(i)

    def log_msg(*args):
        message = "%-16s " % args[0]
        for arg in args[1:]:
            message += arg.__str__() + " "
        logmsg = time.asctime(time.localtime()) + ": " + message
        print(logmsg)
        log.info(logmsg)



