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

        # Generate fake load for incoming request
        for load in self.cfg.load_list:
            utils.generate_load(self.log, load)

        recieved_at = time.time_ns()

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


        response = {'status_code': status_code, 'ptime': time.time_ns()}
        grpc_response = nudnik.entity_pb2.Response(**response)
        if self.metrics is not None:
            stat = nudnik.metrics.Stat(request, grpc_response, recieved_at)
            self.metrics.append(stat)

        return grpc_response

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
