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
import os
import requests_unixsocket
from concurrent import futures
import time
import threading

import grpc

import nudnik
import nudnik.utils as utils

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

class ParseService(nudnik.entity_pb2_grpc.ParserServicer):

    def __init__(self, cfg, metrics):
        super(ParseService, self).__init__()
        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.successful_requests = 0
        self.failed_requests = 0
        self.metrics = metrics

    def parse(self, request, context):

        recieved_at = time.time_ns()

        # Generate fake load for incoming request
        for load in self.cfg.load_list:
            utils.generate_load(self.log, load)

        cdelta = utils.diff_nanoseconds(request.ctime, recieved_at)

        # Calculate retransimt-delta
        if request.rtime != 0:
            rdelta = utils.diff_nanoseconds(request.rtime, recieved_at)
        else:
            rdelta = 0

        if self.cfg.name_mismatch_error is True and not request.name.startswith(self.cfg.name):
            raise NameMismatchException('Client name "{}" does not match server prefix "{}"'.format(request.name, self.cfg.name))

        total = self.failed_requests + self.successful_requests
        try:
            current_fail_ratio = float((self.failed_requests / total) * 100)
        except ZeroDivisionError:
            current_fail_ratio = 100

        if current_fail_ratio >= self.cfg.fail_ratio:
            self.successful_requests += 1
            status_code = 'OK'
        else:
            self.log.debug('failed={},success={},current_fail_ratio={},conf_fail_ratio={}'.format(self.failed_requests, self.successful_requests, current_fail_ratio, self.cfg.fail_ratio))
            self.failed_requests += 1
            status_code = 'SERVER_ERROR'

        tostring = '{},name={},mid={},ctime={},rtime={},cdelta={},rdelta={},rcount={}'.format(status_code, request.name, request.message_id, request.ctime, request.rtime, cdelta, rdelta, request.rcount)
        self.log.debug(tostring)
        result = {'status_code': status_code}

        if request.rtime > 0:
            data='request,status={},name={},mid={} ctime={},rtime={},cdelta={},rdelta={},rcount={} {}'.format(status_code, request.name, request.message_id, request.ctime, request.rtime, cdelta, rdelta, request.rcount, str(recieved_at))
        else:
            data='request,status={},name={},mid={} ctime={},cdelta={} {}'.format(status_code, request.name, request.message_id, request.ctime, cdelta, str(recieved_at))

        self.metrics.append(data)

        return nudnik.entity_pb2.Response(**result)

    def start_server(self):
        max_workers = max(1, (os.cpu_count() - 1))
#        max_workers = os.cpu_count() * 2
        parse_server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
        nudnik.entity_pb2_grpc.add_ParserServicer_to_server(ParseService(self.cfg, self.metrics),parse_server)
        parse_server.add_insecure_port('[::]:{}'.format(self.cfg.port))
        # Non blocking
        parse_server.start()
        self.log.info('Parser Server binded to port {}'.format(self.cfg.port))

        try:
            while True:
                time.sleep(_ONE_DAY_IN_SECONDS)
        except KeyboardInterrupt:
            parse_server.stop(0)
            self.log.warn('Interrupted by user')


class Metrics(threading.Thread):
    def __init__(self, cfg, metrics):
        threading.Thread.__init__(self)
        self.gtfo = False

        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.session = requests_unixsocket.Session()
        self.metrics_url = 'http+unix://{}/write?db={}&precision=ns'.format(self.cfg.metrics_socket_path.replace('/', '%2F'), self.cfg.metrics_db_name)
        self.metrics = metrics
        self.name = '{}-metrics'.format(cfg.name)
        self.log.debug('Metrics {} initiated'.format(self.name))

    def run(self):
        report_count = (self.cfg.streams * self.cfg.interval * self.cfg.rate) - 1
        while not self.gtfo:
            time_start = time.time_ns()

            if len(self.metrics) > report_count:
                r = self.session.post(self.metrics_url, data='\n'.join(self.metrics[:report_count]))
                if r.status_code == 204:
                    for i in range(0, report_count):
                        self.metrics.pop(0)
                else:
                    self.log.error('Response: "{}"'.format(r.text))

            elapsed = utils.diff_seconds(time_start, time.time_ns())
            if elapsed < self.cfg.interval:
                time.sleep(self.cfg.interval - elapsed)


    def exit(self):
        self.gtfo = 1

