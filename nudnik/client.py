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
import sys
import random
if (sys.version_info >= (3, 0)):
    import queue as queue
else:
    import Queue as queue
import threading
import socket
import requests
import grpc

import nudnik
import nudnik.utils as utils

class ParserClient(object):

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
# TODO gRPC does not honor values bigger than 4194304
#        max_message_size = (100 * 1024 * 1024)
#        options=[('grpc.max_message_length', -1), ('grpc.max_recieve_message_length', -1), ('grpc.max_send_message_length', -1)]
        options=[]
        self.channel = grpc.insecure_channel('{}:{}'.format(self.host, self.port), options=options)

        # bind the client to the server channel
        self.stub = nudnik.entity_pb2_grpc.ParserStub(self.channel)

    def get_response_for_request(self, request):
        return self.stub.parse(request, timeout=self.timeout)

class Stream(threading.Thread):
    def __init__(self, cfg, stream_id, stats):
        threading.Thread.__init__(self)
        self.gtfo = False
        self.event = threading.Event()

        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.stream_id = stream_id
        self.stats = stats
        self.queue = queue.Queue()
        self.name = '{}-{}'.format(cfg.name, stream_id)
        self.log.debug('Stream {} initiated'.format(self.name))

    def run(self):
        self.log.debug('Stream {} started, sending {} messages per second'.format(self.name, (self.cfg.rate / float(self.cfg.interval))))

        sequence_id = 0

        active_workers = threading.Semaphore(self.cfg.workers)
        for worker_id in range(0, self.cfg.workers):
            active_workers.acquire()
            thread = MessageSender(self.cfg, self.log, self.stream_id, worker_id, active_workers, self.queue, self.stats)
            thread.daemon = True
            thread.start()

        # Wait for all workers to initialize clients
        for worker_id in range(0, self.cfg.workers):
            active_workers.acquire()

        while not self.gtfo:
            time_start = utils.time_ns()

            for index in range(0, self.cfg.rate):

                message_id = (sequence_id * self.cfg.rate) + index
                if (self.cfg.count > 0) and (message_id >= self.cfg.count):
                    self.exit()
                    return

                if self.cfg.protocol == 'grpc':
                    request = nudnik.entity_pb2.Request(name=self.cfg.name,
                                                        stream_id=self.stream_id,
                                                        sequence_id=sequence_id,
                                                        message_id=message_id,
                                                        ctime=utils.time_ns(),
                                                        load=self.cfg.load_list)
                else:
                    headers = dict()
                    for header in self.cfg.headers:
                        headers.update({str(header[0]): str(header[1])})
                    data = self.cfg.request_format.format(name=self.cfg.name,
                                                          stream_id=self.stream_id,
                                                          sequence_id=sequence_id,
                                                          message_id=message_id,
                                                          ctime=utils.time_ns(),
                                                          load=self.cfg.load_list)

                    req = requests.Request(self.cfg.method, 'http://place_holder', data=data, headers=headers)
                    request = req.prepare()
                    request.name = self.cfg.name
                    request.stream_id=self.stream_id
                    request.sequence_id=sequence_id
                    request.message_id=message_id
                    request.ctime=utils.time_ns()
                    request.load=self.cfg.load_list

                self.queue.put(request)

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
                self.event.wait(timeout=(self.cfg.interval - elapsed))

    def exit(self):
        self.gtfo = 1
        self.event.set()

class MessageSender(threading.Thread):

    def __init__(self, cfg, log, stream_id, worker_id, active_workers, queue, stats):
        threading.Thread.__init__(self)
        self.gtfo = False
        self.event = threading.Event()
        self.active_workers = active_workers
        self.cfg = cfg
        self.log = log
        self.client = None
        self.host_address = None
        self.host_resolved_at = 0
        self.session = requests.Session()
        self.queue = queue
        self.stats = stats
        self.worker_id = worker_id
        self.name = '{}-{}-{}'.format(cfg.name, stream_id, worker_id)

    def run(self):
        if self.cfg.protocol == 'grpc':
            self.set_client(True)
        self.active_workers.release()

        if self.cfg.vv:
            self.log.debug('MessageSender {} initiated'.format(self.name))

        while not self.gtfo:
            if self.cfg.protocol == 'grpc':
                self.set_client(False)
            else:
                self.resolv_host(False)

            request = self.queue.get()
            request.worker_id = self.worker_id

            if self.cfg.vvvvv:
                self.log.debug('Handling message_id {}'.format(request.message_id))

            retry_count = 0
            try_count = 1 + self.cfg.retry_count
            send_was_successful = False
            while (not send_was_successful and ((self.cfg.retry_count < 0) or (try_count > 0))):
                request.stime=utils.time_ns()

                meta = self.cfg.meta.format(req=request, node=nudnik.metrics.MetricNode()) if self.cfg.meta is not None else None
                request.meta = utils.get_meta(meta, self.cfg.meta_size)

                if getattr(request, 'load', None) is not None:
                    for load in request.load:
                        utils.generate_load(self.log, load, meta)

                response = None
                if self.cfg.protocol == 'grpc':
                    try:
                        response = self.client.get_response_for_request(request)
                    except grpc._channel._Rendezvous as e:
                        resp = {'status_code': 500}
                        response = nudnik.entity_pb2.Response(**resp)
                        self.log.warn('Reinitializing client due to {}'.format(e))
                        self.set_client(True)
                else:
                    try:
                        request.url = '{}://{}:{}{}'.format(self.cfg.protocol, self.host_address, self.cfg.port, self.cfg.path)
                        response = self.session.send(request)
                        if response.status_code >= 200 and response.status_code < 300:
                           response.status_code = 0
                    except Exception as e:
                        response = None
                        self.log.warn('Resending request due to {}'.format(e))
                        self.resolv_host(True)

                if self.cfg.vvvvv:
                    self.log.debug(response)

                timestamp = utils.time_ns()

                send_was_successful = ( (response is not None) and (response.status_code == 0) and (self.stats.get_fail_ratio() >= self.cfg.fail_ratio))

                if send_was_successful:
                    if self.cfg.vvvvv:
                        self.log.debug('Request was successful')
                    self.stats.add_success()
                    stat = nudnik.stats.Stat(request, response, timestamp)
                    self.stats.append(stat)
                else:
                    self.log.warn('Request was not successful')
                    self.stats.add_failure()
                    try_count -= 1
                    retry_count += 1
                    request.rtime=utils.time_ns()
                    request.rcount = retry_count

            if self.cfg.vv:
                total_rtt = utils.diff_seconds(request.ctime, timestamp) * self.cfg.rate
                if total_rtt > self.cfg.interval:
                    self.log.warn('Predicted total rtt {} for rate {} exceeds interval {}'.format(total_rtt, self.cfg.rate, self.cfg.interval))

    def set_client(self, force):
        resolved_elapsed = utils.diff_seconds(self.host_resolved_at, utils.time_ns())
        if resolved_elapsed < self.cfg.dns_ttl and force is False:
            return

        self.resolv_host(True)
        self.client = None
        index = 0
        while self.client is None:
            try:
                self.client = ParserClient(host_address, self.cfg.port, self.cfg.timeout)
            except Exception as e:
                self.log.warn('Reinitializing client due to {}'.format(e))
                self.event.wait(timeout=((index * 100)/1000))
                index += 1

        if self.cfg.vvv:
            self.log.debug('Client to {} initialized'.format(host_address))

    def resolv_host(self, force):
        resolved_elapsed = utils.diff_seconds(self.host_resolved_at, utils.time_ns())
        if resolved_elapsed < self.cfg.dns_ttl and force is False:
            return

        ipv4=True
        ipv6=False
        if ipv6 is True:
            if ipv4 is True:
                family = 0
            else:
                family = 10
        else:
            family = 2

        addresses = []
        index = 0
        while len(addresses) < 1:
            addresses = socket.getaddrinfo(self.cfg.host, 0, family, 1)
            self.event.wait(timeout=((index * 100)/1000))
            index += 1

        self.host_address = addresses[random.randint(0, (len(addresses) - 1))][-1][0]
        self.host_resolved_at = utils.time_ns()
        if self.cfg.vvv:
            self.log.debug('Host {} resolved as {}'.format(self.cfg.host, self.host_address))

    def exit(self):
        self.gtfo = 1
        self.event.set()

