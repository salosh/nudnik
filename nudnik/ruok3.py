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

import http.server
import socketserver

class Ruok(threading.Thread):
    def __init__(self, cfg):
        threading.Thread.__init__(self)
        self.gtfo = False
        self.cfg = cfg

        self.Handler = NudnikHttpRequestHandler
        setattr(self.Handler, 'cfg', cfg)
        server_address = ('0.0.0.0', cfg.ruok_port)
        self.httpd = socketserver.TCPServer(server_address, self.Handler)

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

    def do_GET(self):
        if self.path == self.cfg.ruok_path:
            self.protocol_version='HTTP/1.1'
            self.send_response(200, 'OK')
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            response = {'status_code': 200, 'timestamp': str(datetime.utcnow()) }
            self.wfile.write(bytes(str(response), 'utf-8'))
        else:
            self.protocol_version='HTTP/1.1'
            self.send_response(404)
            self.end_headers()

        return
