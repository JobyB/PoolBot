#!/usr/bin/python

"""
Generic interface to read and write data to/from an automation controller.

Currently only Jandy Aqualink is supported but adding a new system should be as easy as copying the aqualink class and
changing the methods to work with the new controller.
"""

from __future__ import (division, print_function)

import logging

from aqualinkClass import Aqualink

class Interface(object):
    """ Generic interface class"""

    supported_interfaces = ['aqualink']

    def __init__(self, iface_type, serial_port):

        self.log = logging.getLogger(self.__class__.__name__)

        if iface_type == 'aqualink':
            self.iface = Aqualink(serial_port)
        else:
            self.log.critical(iface_type + ' not a valid interface')


    def get_temp(self, sensor):
        return self.iface.get_temp(sensor)



