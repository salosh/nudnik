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
import sys
from datetime import datetime
import threading
import json

import http.server
import socketserver

from nudnik import __version__
import nudnik.utils as utils

class Ruok(threading.Thread):
    def __init__(self, cfg):
        threading.Thread.__init__(self)
        self.gtfo = False
        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)

        self.Handler = NudnikHttpRequestHandler
        setattr(self.Handler, 'cfg', cfg)
        server_address = (cfg.ruok_host, cfg.ruok_port)
        self.httpd = socketserver.TCPServer(server_address, self.Handler)
        self.log.info('RUOK Server binded to "{}:{}"'.format(cfg.ruok_host, cfg.ruok_port))

    def run(self):

        while not self.gtfo:
            self.httpd.serve_forever(poll_interval=0.5)

        self.exit()

    def exit(self):
        self.gtfo = 1
        self.httpd.server_close()
        self.httpd.shutdown()

class NudnikHttpRequestHandler(http.server.BaseHTTPRequestHandler):

    def __init__(self, request, client_address, server):
        http.server.BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    def version_string(self):
        return 'Nudnik v{}'.format(__version__)

    def do_GET(self):
        if self.path == self.cfg.ruok_path:
            self.protocol_version='HTTP/1.1'
            self.send_response(200, 'OK')
            for header in self.cfg.ruok_headers:
                self.send_header(header[0], header[1])
            self.end_headers()

            response = json.dumps(json.loads(self.cfg.ruok_response_format.format(date=str(datetime.utcnow()))))
            self.wfile.write(bytes(response))
        elif self.path == '/config':
            self.protocol_version='HTTP/1.1'
            self.send_response(200, 'OK')
            if 'Accept' in self.headers and self.headers['Accept'] == 'application/x-yaml':
                self.send_header('Content-type', 'application/x-yaml')
                response = self.cfg.yaml()
            else:
                self.send_header('Content-type', 'application/json')
                response = self.cfg.json()

            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
        else:
            self.protocol_version='HTTP/1.1'
            self.send_response(404)
            self.end_headers()

        return
