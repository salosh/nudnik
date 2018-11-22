#!/usr/bin/env python3
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
import random
from datetime import datetime
import argparse
import uuid
import os
import sys
import threading
import yaml

from concurrent import futures

import grpc
import entity_pb2
import entity_pb2_grpc
import requests_unixsocket

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

class ParseService(entity_pb2_grpc.ParserServicer):

    def __init__(self):
        super(ParseService, self).__init__()
        self.successful_requests = 0
        self.failed_requests = 0
        self.started_at = datetime.utcnow()
        self.last_report = datetime.utcnow()
        self.session = requests_unixsocket.Session()

    def Parse(self, request, context):

        for load in cfg.load_list:
            generate_load(load)

        try:
            request_ctime = datetime.strptime(request.ctime, '%Y-%m-%d %H:%M:%S.%f')
        except Exception:
            request_ctime = datetime.strptime(request.ctime, '%Y-%m-%d %H:%M:%S')
        cdelta = (datetime.utcnow() - request_ctime).total_seconds()

        if request.rtime != '':
            try:
                request_rtime = datetime.strptime(request.rtime, '%Y-%m-%d %H:%M:%S.%f')
            except Exception:
                request_rtime = datetime.strptime(request.rtime, '%Y-%m-%d %H:%M:%S')
            rdelta = (datetime.utcnow() - request_ctime).total_seconds()
        else:
            request_rtime = None
            rdelta = 0

        total = self.failed_requests + self.successful_requests
        try:
            current_fail_ratio = float((self.failed_requests / total) * 100)
        except ZeroDivisionError:
            current_fail_ratio = 100

        if current_fail_ratio >= cfg.fail_ratio:
            self.successful_requests += 1
            status_code = 'OK'
        else:
            print('failed={},success={},current_fail_ratio={},conf_fail_ratio={}'.format(self.failed_requests, self.successful_requests, current_fail_ratio, cfg.fail_ratio))
            self.failed_requests += 1
            status_code = 'SERVER_ERROR'

        tostring = '{},name-sid-seq={},mid={},ctime={},rtime={},cdelta={},rdelta={}'.format(status_code, request.name, request.message_id, request.ctime, request.rtime, cdelta, rdelta)
        print(tostring)
        result = {'status_code': status_code}
        if request_rtime is not None:
            data='request,status={},name={} mid={},ctime={},rtime={},cdelta={},rdelta={} {}'.format(status_code, request.name, request.message_id, request_ctime.strftime('%s'), request_rtime.strftime('%s'), cdelta, rdelta, datetime.utcnow().strftime('%s'))
        else:
            data='request,status={},name={} mid={},ctime={},cdelta={} {}'.format(status_code, request.name, request.message_id, request_ctime.strftime('%s'), cdelta, datetime.utcnow().strftime('%s'))

        r = self.session.post('http+unix://%2Fvar%2Frun%2Finfluxdb%2Finfluxdb.sock/write?db=metrics&precision=s', data=data)
#        print('Response: "{}"'.format(r.text))

#        stat = {'name': request.name, 'message_id': request.message_id, 'ctime': request.ctime, 'rtime': request.rtime, 'cdelta': cdelta, 'rdelta': rdelta}
#        self.stats.append(stat)
#        if len(self.stats) > 10000:
#            self.stats = self.stats[1000:]

        return entity_pb2.Response(**result)

    def start_server(self):
        parse_server = grpc.server(futures.ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() - 1))))
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
# TODO gRPC does not honor values bigger than 4194304
#        max_message_size = (100 * 1024 * 1024)
#        options=[('grpc.max_message_length', -1), ('grpc.max_recieve_message_length', -1), ('grpc.max_send_message_length', -1)]
        options=[]
        self.channel = grpc.insecure_channel('{}:{}'.format(self.host, self.port), options=options)

        # bind the client to the server channel
        self.stub = entity_pb2_grpc.ParserStub(self.channel)

    def get_response_for_request(self, request):
        return self.stub.Parse(request)

class Stream(threading.Thread):
    def __init__(self, stream_id):
        threading.Thread.__init__(self)

        self.gtfo = False
        self.stream_id = stream_id
        self.name = '{}-{}'.format(cfg.name, stream_id)

    def run(self):
        generator_sequence_number = 0
        while not self.gtfo:
            time_start = time.time()
            try:
                fg = MessageGenerator(self.stream_id, generator_sequence_number)
                fg.start()
            except Exception as e:
                print(e)
            generator_sequence_number += 1
            elapsed = time.time() - time_start
            if elapsed < cfg.interval:
                time.sleep(cfg.interval - elapsed)

    def exit(self):
        self.gtfo = 1

class MessageGenerator(threading.Thread):

    def __init__(self, stream_id, generator_sequence_number):
        threading.Thread.__init__(self)

        self.stream_id = stream_id
        self.generator_sequence_number = generator_sequence_number
        self.started_at = time.time()
        self.name = '{}-{}'.format(cfg.name, stream_id)

    def run(self):

        client = ParserClient()

        for index in range(1, cfg.rate + 1):
            if 'meta_filepath' in cfg and cfg.meta_filepath is not None and cfg.meta_filepath in ['random', 'urandom', '/dev/random', '/dev/urandom']:
                cfg.meta = os.urandom(_MAX_MESSAGE_SIZE_GRPC_BUG)

            request = entity_pb2.Request(name=self.name,
                                     stream_id=self.stream_id,
                                     sequence_id=self.generator_sequence_number,
                                     message_id=index,
                                     ctime=str(datetime.utcnow()),
                                     meta=cfg.meta,
                                     load=cfg.load_list)

            for load in request.load:
                generate_load(load)

            try_count = 1 + cfg.retry_count
            send_was_successful = False
            while (not send_was_successful and ((cfg.retry_count < 0) or (try_count > 0))):
                response = client.get_response_for_request(request)
                send_was_successful = (response.status_code == 0)
                try_count -= 1
                if not send_was_successful:
                    request.rtime=str(datetime.utcnow())

        elapsed = time.time() - self.started_at
        if elapsed > cfg.interval:
            print('ERROR: {} - Sending {} took {}, which is more than the interval {}, execute scale out!'.format(self.name, cfg.rate, elapsed, cfg.interval))

def client():
    streams = list()
    for i in range(1, cfg.streams + 1):
        stream = Stream(i)
        streams.append(stream)

    print('Starting {} streams'.format(len(streams)))
    for stream in streams:
        try:
            stream.start()
            print('Stream {} started'.format(stream))

        except Exception as e:
            print('{}'.format(e))

    while len(streams) > 0:
        for index, stream in enumerate(streams):
            try:
                stream.join(0.25)
            except KeyboardInterrupt:
                for stream in streams:
                    stream.exit()
                    streams.pop(index)
#                sys.exit(1)
            except Exception as e:
                log.error(e)

    print('You are the weakest link, goodbye!'.format(''))

class NudnikConfiguration(dict):
    pass

class FakeLoadCpu(threading.Thread):
    def __init__(self, time_load):
        threading.Thread.__init__(self)
        self.time_load = float(time_load)

    def run(self):
        started_at = time.time()
        while ((time.time() - started_at) < self.time_load):
            pass


class FakeLoadMem(threading.Thread):
    def __init__(self, amount_in_mb):
        threading.Thread.__init__(self)
        self.amount_in_mb = int(amount_in_mb) * 1024 * 1024

    def run(self):
        urandom = os.urandom(self.amount_in_mb)

def generate_load(load):
    if load.load_type == 0:
        time_sleep = float(load.value)
        print('Sleeping for {}'.format(time_sleep))
        time.sleep(time_sleep)
    elif load.load_type == 1:
        time_sleep = random.uniform(0.0, float(load.value))
        print('Sleeping for random value {}'.format(time_sleep))
        time.sleep(time_sleep)
    elif load.load_type == 2:
        time_load = load.value
        print('CPU loading for {} seconds'.format(time_load))
        for i in range(0, os.cpu_count()):
            cpu_load_thread = FakeLoadCpu(time_load).start()
    elif load.load_type == 3:
        amount_in_mb = load.value
        print('Loading {} MB to RAM'.format(amount_in_mb))
        mem_load_thread = FakeLoadMem(amount_in_mb)
        mem_load_thread.start()

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
    parser.add_argument('--meta', type=str, default=None, help='Send this extra data with every request')
    parser.add_argument('--streams', type=int, default='1', help='Number of streams (Default: 1)')
    parser.add_argument('--interval', type=int, default='1', help='Number of seconds per stream message cycle (Default: 1)')
    parser.add_argument('--rate', type=int, default='10', help='Number of messages per interval (Default: 10)')
    parser.add_argument('--load', nargs=2, action='append', type=str, metavar=('load_type', 'load_value'), dest='load',
                        help='Add artificial load [rtt, rttr, cpu, mem] (Default: None)')
    parser.add_argument('--retry-count', type=int, default='-1', help='Number of times to re-send failed messages (Default: -1)')
    parser.add_argument('--fail-ratio', type=int, default='0', help='Percent of requests to intentionally fail (Default: 0)')

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
        try:
            value = os.environ['NUDNIK_' + key.upper()]

            if isinstance(vars(args)[key], int):
                value = int(value)
            else:
                value = str(value)
        except KeyError:
            # TODO fix overriding precedence
            if getattr(cfg, key, None): continue
            value = args.__dict__[key]
        finally:
            setattr(cfg, key, value)


    _MAX_MESSAGE_SIZE_GRPC_BUG = 4194304 - 48
    if cfg.meta is not None and cfg.meta != '' and cfg.meta[0] == '@':
        cfg.meta_filepath = cfg.meta[1:]

        try:
            with open(cfg.meta_filepath, 'rb') as f:
                cfg.meta = f.read(_MAX_MESSAGE_SIZE_GRPC_BUG)

        except Exception as e:
            print('Could not open meta file "{}", {}'.format(cfg.meta_filepath, str(e)))
            cfg.meta = None
            pass

    load_list = list()
    if cfg.load is not None:
        for load in cfg.load:
            load = entity_pb2.Load(load_type=load[0], value=load[1])
            load_list.append(load)
    cfg.load_list = load_list

    if cfg.server:
        server = ParseService()
        server.start_server()

    else:
        client()

