#!/usr/bin/python


# Small utils for helping with the logging
# Not meant to be run as a standalone module

from __future__ import (division, print_function)
import os
import sys
import yaml
import time
import logging
import logging.config
import logging.handlers


# Find our current dir and set our base dir
base_dir = os.path.dirname(os.path.abspath(__file__))

# Defile the location to find logs
loggingPath = os.path.join(base_dir, 'logs')

# Define the available log levels
valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


# Create a custom handler for files
class MyFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=0, maxBytes=2097152, backupCount=5):
        if not os.path.exists(loggingPath):
            os.makedirs(loggingPath)
        fullpath = os.path.join(loggingPath, filename)
        logging.handlers.RotatingFileHandler.__init__(self, fullpath, mode=mode, encoding=encoding, delay=delay, maxBytes=maxBytes, backupCount=backupCount)


# Create a custom handler so critical level logs call sys.exit(1)
class ShutdownHandler(logging.StreamHandler):
    def emit(self, record):
        self.format(record)
        logging.shutdown()
        sys.exit(1)


def log_setup(logger_name, logging_level):

    logging_data = yaml.safe_load(open(os.path.join(base_dir, 'conf', 'logging.yaml')))

    # Update the console handler from cmd line if required
    if logging_level != '':
        if logging_level.upper() in valid_log_levels:
            if logging_level.upper() != logging_data['handlers']['console']['level']:
                print('Setting logging level from cmd line to: ' + str(logging_level.upper()))
                logging_data['handlers']['console']['level'] = logging_level.upper()
        else:
            print('ERROR: ' + logging_level + ' is not a valid log level')
            print('ERROR: Valid log levels: ' + str(valid_log_levels))
            sys.exit(1)

    # Load our logging config into the logger
    logging.config.dictConfig(logging_data)

    # Create an instance of our logger
    log = logging.getLogger(logger_name)

    log.info('')
    log.info('#####################################')
    log.info('System Init ' + str(time.strftime("%Y-%m-%d %H:%M:%S")))
    log.info('#####################################')

    return log


def shutdown_logging():
    logging.shutdown()

# execute as standalone program
if __name__ == '__main__':
    print('This is a Python module, not designed to be run as a standalone program')
