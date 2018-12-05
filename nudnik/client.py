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
import threading
import os
import random

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
        self.name = '{}-{}'.format(cfg.name, stream_id)
        self.log.debug('Stream {} initiated'.format(self.name))

    def run(self):
        self.log.debug('Stream {} started, sending {} messages per second'.format(self.name, (self.cfg.interval * self.cfg.rate)))

        generator_sequence_number = 0

        while not self.gtfo:
            time_start = utils.time_ns()

            if (self.cfg.count > 0) and (generator_sequence_number * self.cfg.rate >= self.cfg.count):
                self.exit()
                return

            try:
                fg = MessageGenerator(self.cfg, self.log, self.name, self.stream_id, generator_sequence_number, self.metrics)
                fg.start()
            except Exception as e:
                self.log.fatal(e)
                self.exit()

            generator_sequence_number += 1

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

class MessageGenerator(threading.Thread):

    def __init__(self, cfg, log, name, stream_id, generator_sequence_number, metrics):
        threading.Thread.__init__(self)

        self.cfg = cfg
        self.log = log
        self.stream_id = stream_id
        self.generator_sequence_number = generator_sequence_number
        self.metrics = metrics
        self.started_at = utils.time_ns()
        self.name = name

    def run(self):
        if self.cfg.vv:
            self.log.debug('MessageGenerator {} initiated, sending {} messages'.format(self.name, self.cfg.rate))
        time_start = utils.time_ns()

        client = ParserClient(self.cfg.host, self.cfg.port)

        for index in range(1, self.cfg.rate + 1):
            if 'meta_filepath' in self.cfg and self.cfg.meta_filepath is not None and self.cfg.meta_filepath in ['random', 'urandom', '/dev/random', '/dev/urandom']:
                self.cfg.meta = os.urandom(_MAX_MESSAGE_SIZE_GRPC_BUG)

            message_id = (self.generator_sequence_number * self.cfg.rate) + index
            request = nudnik.entity_pb2.Request(name=self.name,
                                     stream_id=self.stream_id,
#                                     sequence_id=self.generator_sequence_number,
                                     message_id=message_id,
                                     ctime=utils.time_ns(),
                                     meta=self.cfg.meta,
                                     load=self.cfg.load_list)

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
                else:
                    self.metrics.add_failure()
                    try_count -= 1
                    retry_count += 1
                    request.rtime=utils.time_ns()
                    request.rcount = retry_count

        elapsed = utils.diff_seconds(time_start, utils.time_ns())
        if elapsed > self.cfg.interval:
            self.log.warn('cdelta {} for rate {} exceeds interval {}'.format(elapsed, self.cfg.rate, self.cfg.interval))

