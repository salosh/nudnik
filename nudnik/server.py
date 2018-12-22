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
from concurrent import futures
import time
import threading
import random

import grpc

import nudnik
import nudnik.utils as utils

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

class ParseService(nudnik.entity_pb2_grpc.ParserServicer):
    event = threading.Event()

    def __init__(self, cfg, stats):
        super(ParseService, self).__init__()
        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.stats = stats

    def parse(self, request, context):

        timestamp = utils.time_ns()

        if self.cfg.vvvvv:
            self.log.debug(request)

        # Generate fake load for incoming request
        for load in self.cfg.load_list:
            utils.generate_load(self.log, load)

        cdelta = utils.diff_nanoseconds(request.ctime, timestamp)

        # Calculate retransimt-delta
        if request.rtime != 0:
            rdelta = utils.diff_nanoseconds(request.rtime, timestamp)
        else:
            rdelta = 0

        if self.cfg.name_mismatch_error == 'prefix':
            if not request.name.startswith(self.cfg.name):
                self.exit()
                raise NameMismatchException('Client name "{}" must match server prefix "{}"'.format(request.name, self.cfg.name))
        elif self.cfg.name_mismatch_error == 'suffix':
            if not request.name.endswith(self.cfg.name):
                self.exit()
                raise NameMismatchException('Client name "{}" must match server suffix "{}"'.format(request.name, self.cfg.name))
        elif self.cfg.name_mismatch_error == 'exact':
            if not request.name == self.cfg.name:
                self.exit()
                raise NameMismatchException('Client name "{}" must exactly match server name "{}"'.format(request.name, self.cfg.name))

        if (self.stats.get_fail_ratio() >= self.cfg.fail_ratio):
            self.stats.add_success()
            status_code = 'OK'
        else:
            self.stats.add_failure()
            status_code = 'SERVER_ERROR'

        response = {'status_code': status_code, 'ctime': timestamp, 'stime': utils.time_ns(), 'meta': utils.get_meta(self.cfg)}
        grpc_response = nudnik.entity_pb2.Response(**response)

        stat = nudnik.stats.Stat(request, grpc_response, timestamp)
        self.stats.append(stat)

        if self.cfg.chaos > 0 and random.randint(0, self.cfg.cycle_per_hour) <= self.cfg.chaos:
            chaos_exception = utils.ChaosException(self.cfg.chaos_string)
            self.log.fatal(chaos_exception)
            self.exit()
            raise chaos_exception

        return grpc_response

    def start_server(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=self.cfg.workers))
        nudnik.entity_pb2_grpc.add_ParserServicer_to_server(ParseService(self.cfg, self.stats), server)
        bind_host = self.cfg.host if self.cfg.host != '0.0.0.0' else '[::]'
        server.add_insecure_port('{}:{}'.format(bind_host, self.cfg.port))
        # Non blocking
        server.start()
        self.log.info('Parser Server "{}" binded to "{}:{}"'.format(self.cfg.name, bind_host, self.cfg.port))

        try:
            while not self.event.is_set():
                self.event.wait(self.cfg.interval)
            self.log.info('Goodbye')
            server.stop(0)
        except KeyboardInterrupt:
            self.exit()
            server.stop(0)
            self.log.warn('Interrupted by user')

    def exit(self):
        self.event.set()

class NameMismatchException(Exception): pass
