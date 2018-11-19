#!/usr/bin/python3
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
from datetime import datetime
import argparse
import uuid
import sys
import threading
import yaml

from concurrent import futures

import grpc
import entity_pb2
import entity_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

class ParseService(entity_pb2_grpc.ParserServicer):

    def __init__(self):
        super(ParseService, self).__init__()
        self.meta = 0
        self.started_at = datetime.utcnow()
        self.last_report = datetime.utcnow()

    def Parse(self, request, context):
        try:
            delta = datetime.utcnow() - datetime.strptime(request.timestamp, '%Y-%m-%d %H:%M:%S.%f')
        except Exception:
            delta = datetime.utcnow() - datetime.strptime(request.timestamp, '%Y-%m-%d %H:%M:%S')

        print('{} - {} - {} - {}'.format(request.name, request.messageID, request.timestamp, delta))
        result = {'statusCode': 'OK'}

        self.meta += 1
        now = datetime.utcnow()
        if (now - self.last_report).total_seconds() > 5:
            print('**************************')
            print('Handeled {}/sec messages'.format( self.meta / (datetime.utcnow() - self.started_at).total_seconds() ))
            print('**************************')
            self.last_report = now
        return entity_pb2.Response(**result)

    def start_server(self):
        parse_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        entity_pb2_grpc.add_ParserServicer_to_server(ParseService(),parse_server)
        parse_server.add_insecure_port('[::]:{}'.format(cfg.port))
        # Non blocking
        parse_server.start()
        print ('Parser Server binded to port {}'.format(cfg.port))

        try:
            while True:
                time.sleep(_ONE_DAY_IN_SECONDS)
        except KeyboardInterrupt:
            parse_server.stop(0)
            print('Interrupted by user')

class ParserClient(object):

    def __init__(self):
        self.host = cfg.host
        self.port = cfg.port
        self.channel = grpc.insecure_channel('{}:{}'.format(self.host, self.port))

        # bind the client to the server channel
        self.stub = entity_pb2_grpc.ParserStub(self.channel)

    def getParseForMessage(self, name, stream_id, message_id, timestamp, meta):
        req = entity_pb2.Request(name=name, streamID=stream_id, messageID=message_id, timestamp=timestamp, meta=meta)
        return self.stub.Parse(req)

class Stream(threading.Thread):
    def __init__(self, stream_id):
        threading.Thread.__init__(self)

        self.gtfo = False
        self.stream_id = stream_id
        self.name = '{}-{}'.format(cfg.name, stream_id)

    def run(self):
        generator_index = 0
        while not self.gtfo:
            time_start = time.time()
            try:
                fg = MessageGenerator(self.stream_id, generator_index)
                fg.start()
            except Exception as e:
                print(e)
            generator_index += 1
            elapsed = time.time() - time_start
            if elapsed < 1:
                time.sleep(1 - elapsed)

    def exit(self):
        self.gtfo = 1

class MessageGenerator(threading.Thread):

    def __init__(self, stream_id, generator_index):
        threading.Thread.__init__(self)

        self.stream_id = stream_id
        self.generator_index = generator_index
        self.started_at = time.time()
        self.name = '{}-{}-{}'.format(cfg.name, stream_id, generator_index)

    def run(self):

        client = ParserClient()

        for index in range(1, cfg.mps + 1):
            client.getParseForMessage(self.name, self.stream_id, index, str(datetime.utcnow()), 'metadataXXX')
            index += 1
        elapsed = time.time() - self.started_at
        if elapsed > 1:
            print('ERROR: {} - Sending {} took {}, execute scale out!'.format(self.name, cfg.mps, elapsed))

def client():
    streams = list()
    for i in range(1, cfg.streams + 1):
        cam = Stream(i)
        streams.append(cam)

    print('Starting {} streams'.format(len(streams)))
    for cam in streams:
        try:
            cam.start()
            print('Stream {} started'.format(cam))

        except Exception as e:
            print('{}'.format(e))

    while len(streams) > 0:
        for index, cam in enumerate(streams):
            try:
                cam.join(0.25)
            except KeyboardInterrupt:
                for cam in streams:
                    cam.exit()
                    streams.pop(index)
#                sys.exit(1)
            except Exception as e:
                log.error(e)

    print('You are the weakest link, goodbye!'.format(''))

class NudnikConfiguration(dict):
    pass

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Nudnik - gRPC load tester',
        epilog='2018 (C) Salo Shp <SaloShp@Gmail.Com> <https://github.com/salosh/nudnik.git>'
    )
    parser.add_argument('--config-file', type=str, default='config.yml', help='Path to YAML config file')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='host')
    parser.add_argument('--port', type=int, default='5410', help='port')
    parser.add_argument('--server', action='store_true', default=False, help='Operation mode (default: client)')
    parser.add_argument('--name', type=str, default='NAME', help='Parser name')
    parser.add_argument('--streams', type=int, default='1', help='Number of streams (Default: 1)')
    parser.add_argument('--mps', type=int, default='10', help='Number of messages per second (Default: 10)')
    args = parser.parse_args()

    cfg = NudnikConfiguration()

    try:
        with open(args.config_file, 'r') as ymlfile:
            try:
                ymlcfg = yaml.load(ymlfile)
            except yaml.parser.ParserError as e:
                print('Nudnik Configuration error:\n {}'.format(e))
                sys.exit(1)

            if isinstance(ymlcfg, dict):
                for confkey in ymlcfg.keys():
                    if ymlcfg[confkey] is not None:
                        setattr(cfg, confkey, ymlcfg[confkey])
                    else:
                        setattr(cfg, confkey, "")

    except FileNotFoundError:
        print('Could not open config file {}, using defaults'.format(cfg.config_file))
        pass

    for key in args.__dict__:
        # TODO fix overriding precedence
        if getattr(cfg, key, None): continue
        value = args.__dict__[key]
        setattr(cfg, key, value)

    if cfg.server:
        server = ParseService()
        server.start_server()

    else:
        client()

