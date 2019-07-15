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
from datetime import datetime
import threading
import random

import nudnik
import nudnik.utils as utils

class Server(threading.Thread):
    event = threading.Event()

    def __init__(self, cfg, stats):
        threading.Thread.__init__(self)
        self.gtfo = False
        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.stats = stats
        self.host_resolved_at = 0

    def run(self):
        utils.set_etcd_client(self, True)
        self.log.info('Parser server "{}" binded to queue on "{}:{}"'.format(self.cfg.name, self.cfg.host, self.cfg.port))

        request_prefix = self.cfg.etcd_format_key_request.format(name=self.cfg.name)
        response_prefix = self.cfg.etcd_format_key_response.format(name=self.cfg.name)

        while not self.gtfo:
            time_start = utils.time_ns()
            utils.set_etcd_client(self, False)
            messages = self.client.get_prefix(request_prefix)
            for message in messages:
                timestamp = utils.time_ns()
                request = nudnik.entity_pb2.Request()
                request.ParseFromString(message[0])
                response = utils.parse_request(self, request, timestamp)
                grpc_response = nudnik.entity_pb2.Response(**response)

                request_key = message[1].key
                response_key = request_key.replace(request_prefix, response_prefix, 1)
                stat = nudnik.stats.Stat(request, grpc_response, timestamp)
                self.stats.append(stat)
                self.client.put(response_key, grpc_response.SerializeToString())
                self.client.delete(request_key)



            elapsed = utils.diff_seconds(time_start, utils.time_ns())
            if elapsed < self.cfg.interval:
                self.event.wait(timeout=(self.cfg.interval - elapsed))

    def exit(self):
        self.gtfo = 1
        self.event.set()
