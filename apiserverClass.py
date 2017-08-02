# !/usr/bin/python

"""
Creates a simple interface to send and receive API messages from AWS
"""

import logging
import datetime
from time import sleep

import boto3

class ApiServer:
    """
    Creates a AWS SQS class with a read and write queue to allow bi directions messaging from Lambda and our app
    """

    region = 'us-east-1'

    def __str__(self):
        return self.__class__.__name__ + ' Controller'

    def __init__(self, read_q_name, write_q_name):

        self.log = logging.getLogger(self.__class__.__name__)
        self.log.info('Init')

        if not read_q_name.endswith('.fifo'):
            self.log.critical('SQS read queue name must end with .fifo')

        if not write_q_name.endswith('.fifo'):
            self.log.critical('SQS write queue name must end with .fifo')

        # Get the service resource
        self.sqs = boto3.client('sqs', region_name=ApiServer.region)

        # Set up our queues, the data will be stored in the read_q and write_q dicts
        self.read_q = self.get_queue(read_q_name)
        self.write_q = self.get_queue(write_q_name)

    def get_queue(self, q_name):

        q_data = {'name': q_name}

        # Get a list of all the current queues
        data = self.sqs.list_queues()

        if data['ResponseMetadata']['HTTPStatusCode'] != 200:
            self.log.error('Falied to get list of sqs queues')
            self.log.critical(data)

        all_queues = data['QueueUrls']

        self.log.debug(all_queues)

        resource = boto3.resource('sqs', region_name=ApiServer.region)

        found = False
        for q in all_queues:
            if q_data['name'] in q:
                found = True
                break

        if found:
            self.log.info('Queue ' + q_data['name'] + ' already exits, purging queue and returning instance')
            # Get the queue. This returns an SQS.Queue instance
            q_data['q'] = resource.get_queue_by_name(QueueName=q_data['name'])
            q_data['q'].purge()
            # AWS states that a purge can take up to 60 seconds, but we use less
            sleep(10)
        else:
            self.log.info('Queue ' + q_data['name'] + ' does not exits creating instance')
            # Create the queue. This returns an SQS.Queue instance
            attributes = {'DelaySeconds': '0',
                          'MessageRetentionPeriod': '60',
                          'VisibilityTimeout': '30',
                          'FifoQueue': 'true',
                          'ContentBasedDeduplication' : 'true'
                          }
            resp = self.sqs.create_queue(QueueName=q_data['name'], Attributes=attributes)
            self.log.debug(resp)
            q_data['q'] = resource.get_queue_by_name(QueueName=q_data['name'])

        self.log.debug(q_data)

        return q_data

    def send_msg(self, message):

        # Send message to SQS queue
        response = self.write_q['q'].send_message(
            {
                'MessageAttributes': {
                    'Timestamp': {
                        'DataType': 'String',
                        'StringValue': '{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())
                    }
                },
                'MessageGroupId': self.write_q['name'],
                'MessageBody': message
            }
        )

        print(response['MessageId'])

    def recieve_msg(self):

        message = ''

        # Receive message from SQS queue
        response = self.read_q['q'].receive_messages(
                AttributeNames=['All'],
                MaxNumberOfMessages=1,
                MessageAttributeNames=['All'],
                VisibilityTimeout=0,
                WaitTimeSeconds=0
        )

        self.log.info(response)

        if response:
            message = response['Messages']
            receipt_handle = message['ReceiptHandle']

            # Delete received message from queue
            self.sqs.delete_message(
                    QueueUrl=self.read_q['q'].url,
                    ReceiptHandle=receipt_handle
            )
            self.log.info('Received and deleted message: %s' % message)

        return message

    def process_msg(self):
        while True:
            msg = self.recieve_msg()
            if msg:
                self.log.info('Recieved msg:' + msg)
            else:
                self.log.debug('No message recieved')

            sleep(30)