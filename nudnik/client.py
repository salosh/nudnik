#
#    This file is part of Nudnik. <https://github.com/salosh/nudnik.git>
#
#    Nudnik is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Nudnik is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Nudnik.  If not, see <http://www.gnu.org/licenses/>.
#
import time
import os
import sys
import random
if (sys.version_info >= (3, 0)):
    import queue as queue
else:
    import Queue as queue
import threading

import grpc

import nudnik
import nudnik.utils as utils

class ParserClient(object):

    def __init__(self, host, port):
        self.host = host
        self.port = port
# TODO gRPC does not honor values bigger than 4194304
#        max_message_size = (100 * 1024 * 1024)
#        options=[('grpc.max_message_length', -1), ('grpc.max_recieve_message_length', -1), ('grpc.max_send_message_length', -1)]
        options=[]
        self.channel = grpc.insecure_channel('{}:{}'.format(self.host, self.port), options=options)

        # bind the client to the server channel
        self.stub = nudnik.entity_pb2_grpc.ParserStub(self.channel)

    def get_response_for_request(self, request):
        return self.stub.parse(request)

class Stream(threading.Thread):
    def __init__(self, cfg, stream_id, metrics):
        threading.Thread.__init__(self)

        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.gtfo = False
        self.stream_id = stream_id
        self.metrics = metrics
        self.queue = queue.PriorityQueue()
        self.name = '{}-{}'.format(cfg.name, stream_id)
        self.log.debug('Stream {} initiated'.format(self.name))

    def run(self):
        self.log.debug('Stream {} started, sending {} messages per second'.format(self.name, (self.cfg.interval * self.cfg.rate)))

        sequence_id = 0

        for i in range(0, self.cfg.workers):
            sender_name = '{}-{}'.format(self.name, i)
            thread = MessageSender(self.cfg, self.log, sender_name, self.queue, self.metrics)
            thread.daemon = True
            thread.start()

        while not self.gtfo:
            time_start = utils.time_ns()

            for index in range(0, self.cfg.rate):

                message_id = (sequence_id * self.cfg.rate) + index
                if (self.cfg.count > 0) and (message_id >= self.cfg.count):
                    self.exit()
                    return
                request = nudnik.entity_pb2.Request(name=self.name,
                                                    stream_id=self.stream_id,
                                                    sequence_id=sequence_id,
                                                    message_id=message_id,
                                                    ctime=utils.time_ns(),
                                                    load=self.cfg.load_list)
                self.queue.put((index, request))

            if self.cfg.vvv:
                self.log.debug('Active workers/tasks: {}/{}'.format(threading.active_count(), self.queue.qsize()))

            sequence_id += 1

            if self.cfg.chaos > 0 and random.randint(0, self.cfg.cycle_per_hour) <= self.cfg.chaos:
                chaos_exception = utils.ChaosException(self.cfg.chaos_string)
                self.log.fatal(chaos_exception)
                self.exit()
                raise chaos_exception

            elapsed = utils.diff_seconds(time_start, utils.time_ns())
            if elapsed < self.cfg.interval:
                time.sleep(self.cfg.interval - elapsed)

    def exit(self):
        self.gtfo = 1

class MessageSender(threading.Thread):

    def __init__(self, cfg, log, name, queue, metrics):
        threading.Thread.__init__(self)
        self.gtfo = False

        self.cfg = cfg
        self.log = log
        self.queue = queue
        self.metrics = metrics
        self.name = name

    def run(self):
        if self.cfg.vv:
            self.log.debug('MessageSender {} initiated'.format(self.name))

        client = ParserClient(self.cfg.host, self.cfg.port)

        while not self.gtfo:
            time_start = utils.time_ns()
            (index, request) = self.queue.get()
            if self.cfg.vvvvv:
                self.log.debug('Handling message_id {}'.format(request.message_id))

            if 'meta_filepath' in self.cfg and self.cfg.meta_filepath is not None and self.cfg.meta_filepath in ['random', 'urandom', '/dev/random', '/dev/urandom']:
                request.meta = os.urandom(_MAX_MESSAGE_SIZE_GRPC_BUG)

            for load in request.load:
                utils.generate_load(self.log, load)

            retry_count = 0
            try_count = 1 + self.cfg.retry_count
            send_was_successful = False
            while (not send_was_successful and ((self.cfg.retry_count < 0) or (try_count > 0))):
                response = client.get_response_for_request(request)
                recieved_at = utils.time_ns()

                send_was_successful = ((response.status_code == 0) and (self.metrics.get_fail_ratio() >= self.cfg.fail_ratio))

                if send_was_successful:
                    self.metrics.add_success()
                    stat = nudnik.metrics.Stat(request, response, recieved_at)
                    self.metrics.append(stat)
                    self.queue.task_done()
                else:
                    self.metrics.add_failure()
                    try_count -= 1
                    retry_count += 1
                    request.rtime=utils.time_ns()
                    request.rcount = retry_count

            if self.cfg.vv:
                total_rtt = utils.diff_seconds(request.ctime, recieved_at) * self.cfg.rate
                if total_rtt > self.cfg.interval * 1.1:
                    self.log.warn('Predicted total rtt {} for rate {} exceeds interval {}'.format(total_rtt, self.cfg.rate, self.cfg.interval))

    def exit(self):
        self.gtfo = 1

