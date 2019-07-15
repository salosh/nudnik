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
        response = utils.parse_request(self, request, timestamp)
        grpc_response = nudnik.entity_pb2.Response(**response)

        stat = nudnik.stats.Stat(request, grpc_response, timestamp)
        self.stats.append(stat)

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
