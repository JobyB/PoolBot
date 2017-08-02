#!/usr/bin/python

# Author: Joby Bett (joby@bett.me.uk)

"""
Creates a server that reads data from a pool automation system and writes it to a database. Also accepts commands to
control the system.
"""

from __future__ import (division, print_function)

import sys
import os
import getopt
import threading

from time import sleep

from loggingUtils import log_setup, shutdown_logging
from interfaceClass import Interface
from apiserverClass import ApiServer

# Configuration

# Find our current dir and set our base dir
script_name = os.path.basename(__file__)
base_dir = os.path.dirname(os.path.abspath(__file__))

# Init our cmd line args
controller = ''
port = ''
loggingLevel = ''

# Base name of the project
baseName = 'poolbot'

# Every 10 mins we want to wake up and get the current data from the system
sleep_time = 600


# Usage method
def usage():
    print('Usage: ./' + script_name + ' -c <controller> -p <port> [-d debug level]')
    print('Example: ./' + script_name + ' -c aqualink -p /dev/ttyUSB0')
    sys.exit(2)

# Parse command line arguments and set default values for some
opts = []
args = []

try:
    opts, args = getopt.getopt(sys.argv[1:], 'c:p:d:h', ['controller=', 'port=', 'debug=', 'help'])
except getopt.GetoptError:
    usage()

for opt, arg in opts:
    if opt in ('-h', '--help'):
        usage()
    elif opt in ('-c', '--controller'):
        controller = arg
    elif opt in ('-p', '--port'):
        port = arg
    elif opt in ('-d', '--debug'):
        loggingLevel = arg
    else:
        usage()

# Verify labName and flavor is provided
if controller == '':
    print('ERROR: Controller must be provided', file=sys.stderr)
    usage()

if port == '':
    print('ERROR: Port must be provided', file=sys.stderr)
    usage()

# Set up our logger
log = log_setup('main', loggingLevel)

def main():

    log.info('Creating ' + controller + ' interface on port ' + port)
    iface = Interface(controller, port)

    log.info('Creating listening server')
    api_server = ApiServer(baseName + 'rq.fifo', baseName + 'wq.fifo')

    server = threading.Thread(target=api_server.process_msg(), args=())
    server.start()

    log.debug('Entering main loop')
    while True:
        data = {}
        data['air_temp'] = iface.get_temp('air')
        data['pool_temp'] = iface.get_temp('pool')
        data['spa_temp'] = iface.get_temp('spa')

        log.info('Sending current pool data')
        api_server.send_msg(data)

        log.debug('Waiting for next cycle')
        sleep(sleep_time)


    shutdown_logging()
    # the end

# Execute as standalone program
if __name__ == '__main__':
    try:
        main()
    except:
        log.exception('Exception')
        raise