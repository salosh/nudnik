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
import logging
import argparse
import yaml
import os
import sys
import threading
import subprocess
import time
import re
from datetime import datetime
import random

if sys.version_info < (3, 0):
    from exceptions import IOError as FileNotFoundError

import nudnik

_BILLION = float(10**9)
_MAX_MESSAGE_SIZE_GRPC_BUG = 4194304 - 48

class NudnikConfiguration(dict):
    pass

def parse_args():
    parser = argparse.ArgumentParser(
        description='Nudnik - gRPC load tester',
        epilog='2018 (C) Salo Shp <https://github.com/salosh/nudnik.git>'
    )
    parser.add_argument('--config-file', '-f',
                        type=str,
                        help='Path to YAML config file')
    parser.add_argument('--host', '-H',
                        type=str,
                        help='host')
    parser.add_argument('--port', '-p',
                        type=int,
                        help='port')
    parser.add_argument('--server', '-S',
                        action='store_true',
                        help='Operation mode (default: client)')
    parser.add_argument('--name', '-n',
                        type=str,
                        help='Parser name')
    parser.add_argument('--name-mismatch-error',
                        type=str,
                        choices=['prefix', 'suffix', 'exact'],
                        help='Fail request on name mismatch (default: None)')
    parser.add_argument('--meta', '-M',
                        type=str,
                        help='Send this extra data with every request')
    parser.add_argument('--workers', '-w',
                        type=int,
                        help='Number of workers (Default: Count of CPU cores)')
    parser.add_argument('--streams', '-s',
                        type=int,
                        help='Number of streams (Default: 1)')
    parser.add_argument('--initial-stream-index',
                        type=int,
                        help='Calculate stream ID from this initial index (Default: 0)')
    parser.add_argument('--interval', '-i',
                        type=int,
                        help='Number of seconds per stream message cycle (Default: 1)')
    parser.add_argument('--rate', '-r',
                        type=int,
                        help='Number of messages per interval (Default: 10)')
    parser.add_argument('--count', '-C',
                        type=int,
                        help='Count of total messages that should be sent (Default: 0 == unlimited)')
    parser.add_argument('--chaos', '-c',
                        type=int,
                        help='Compute statistical process level random crashes [0, 3600/interval] (Default: 0)')
    parser.add_argument('--load', '-l',
                        type=str,
                        nargs=2,
                        action='append',
                        metavar=('load_type', 'load_value'),
                        dest='load',
                        help='Add artificial load [rtt, rttr, cpu, mem, cmd, fcmd] (Default: None)')
    parser.add_argument('--retry-count',
                        type=int,
                        help='Number of times to re-send failed messages (Default: -1, which means infinite times)')
    parser.add_argument('--fail-ratio',
                        type=str,
                        help='Percent of requests to intentionally fail (Default: 0)')
    parser.add_argument('--ruok', '-R',
                        action='store_true',
                        help='Enable "Are You OK?" HTTP/1.1 API (default: False)')
    parser.add_argument('--ruok-port',
                        type=int,
                        help='"Are You OK?" HTTP/1.1 API port (default: 80)')
    parser.add_argument('--ruok-path',
                        type=str,
                        help='"Are You OK?" HTTP/1.1 API path (Default: /ruok)')
    parser.add_argument('--stats', '-m',
                        type=str,
                        action='append',
                        choices=['stdout', 'file', 'influxdb', 'prometheus'],
                        help='Enable stats outputs (Default: None)')
    parser.add_argument('--stats-interval',
                        type=int,
                        help='Number of seconds per stats cycle (Default: 1)')
    parser.add_argument('--file-path', '-F',
                        type=str,
                        help='Path to exported stats file (Default: ./nudnikstats.out)')
    parser.add_argument('--influxdb-socket-path',
                        type=str,
                        help='Absolute path to InfluxDB Unix socket (Default: /var/run/influxdb/influxdb.sock)')
    parser.add_argument('--influxdb-database-name',
                        type=str,
                        help='InfluxDB database name (Default: nudnik)')
    parser.add_argument('--debug', '-d',
                        action='store_true',
                        help='Debug mode (default: False)')
    parser.add_argument('--verbose', '-v',
                        action='count',
                        help='Verbose mode, specify multiple times for extra verbosity (default: None)')
    parser.add_argument('--version', '-V',
                        action='version',
                        version='Nudnik v{} - 2018 (C) Salo Shp <https://github.com/salosh/nudnik.git>'.format(nudnik.__version__),
                        help='Display Nudnik version')

    args = parser.parse_args()
    return args

def parse_config(args):
    cfg = NudnikConfiguration()

    DEFAULTS = {
      'config_file': '/etc/nudnik/config.yml',
      'host': '127.0.0.1',
      'port': 5410,
      'server': False,
      'name': 'NAME',
      'name_mismatch_error': None,
      'meta': None,
      'workers': os.sysconf('SC_NPROCESSORS_ONLN'),
      'streams': 1,
      'initial_stream_index': 0,
      'interval': 1,
      'rate': 1,
      'count': 0,
      'chaos': 0,
      'chaos_string': 'In all chaos there is a cosmos, in all disorder a secret order. #Carl_Jung_FTW',
      'load': [],
      'retry_count': -1,
      'fail_ratio': 0,
      'ruok': False,
      'ruok_port': 80,
      'ruok_path': '/ruok',
      'stats': [],
      'stats_interval': 1,
      'file_path': './nudnikstats.out',
      'out_format': '{recieved_at_str},{status_code},{req.name},{req.message_id},{req.ctime},{cdelta},rtt={rtt}',
      'out_retransmit_format': '{recieved_at_str},{status_code},{req.name},{req.message_id},{req.ctime},{req.rtime},{cdelta},{rdelta},{req.rcount},rtt={rtt}',
      'influxdb_socket_path': '/var/run/influxdb/influxdb.sock',
      'influxdb_protocol': 'http+unix',
      'influxdb_host': '127.0.0.1:8086',
      'influxdb_database_name': 'nudnik',
      'influxdb_url': '{influxdb_protocol}://{influxdb_host}/write?db={influxdb_database_name}&precision=ns',
      'influxdb_format': 'status={status_code},name={req.name},sid={req.stream_id},wid={req.worker_id},qid={req.sequence_id} sid={req.stream_id},wid={req.worker_id},mid={req.message_id},ctime={req.ctime},cdelta={cdelta},sdelta={sdelta},pdelta={pdelta},bdelta={bdelta},rtt={rtt} {recieved_at}',
      'influxdb_retransmit_format': 'status={status_code},name={req.name},sid={req.stream_id},wid={req.worker_id},qid={req.sequence_id} sid={req.stream_id},wid={req.worker_id},mid={req.message_id},ctime={req.ctime},rtime={req.rtime},cdelta={cdelta},sdelta={sdelta},pdelta={pdelta},bdelta={bdelta},rdelta={rdelta},rcount={req.rcount},rtt={rtt} {recieved_at}',
      'prometheus_protocol': 'http',
      'prometheus_host': '127.0.0.1:9091',
      'prometheus_url': '{prometheus_protocol}://{prometheus_host}/metrics/job/{job_name}/{label_name}/{label_value}',
      'prometheus_format': '# TYPE nudnik_message summary\nnudnik_message{{ctime="{req.ctime}",message_id="{req.message_id}", rtt="{rtt}", name="{req.name}"}} {recieved_at}\n',
      'prometheus_retransmit_format': '# TYPE nudnik_message summary\nnudnik_message{{ctime="{req.ctime}",message_id="{req.message_id}", rtt="{rtt}", name="{req.name}"}} {recieved_at}\n',
      'debug': False,
      'verbose': 0,
    }

    setattr(cfg, 'config_file', DEFAULTS['config_file'])

    for key in DEFAULTS:
        env_key_name = 'NUDNIK_{key_name}'.format(key_name=key.upper())
        value = None
        if key in args.__dict__ and vars(args)[key]:
            value = vars(args)[key]
        elif env_key_name in os.environ:
            value = os.environ[env_key_name]
            if type(DEFAULTS[key]) is bool:
                if value in [True, 'TRUE', 'True', 'true', 'YES', 'Yes', 'yes', '1', 1]:
                    value = True
                elif value in [False, 'FALSE', 'False', 'false', 'NO', 'No', 'no', '0', 0]:
                    value = False
            elif isinstance(DEFAULTS[key], int):
                value = int(value)
            elif isinstance(DEFAULTS[key], str):
                value = str(value)
            else:
                value = value

        if value is not None:
            setattr(cfg, key, value)

    try:
        with open(cfg.config_file, 'r') as ymlfile:
            ymlcfg = yaml.load(ymlfile)

            if not isinstance(ymlcfg, dict):
                raise FileNotFoundError

            for confkey in DEFAULTS:
                if confkey in ymlcfg and ymlcfg[confkey] is not None and getattr(cfg, confkey, None) is None:
                    setattr(cfg, confkey, ymlcfg[confkey])

    except yaml.parser.ParserError as e:
        print('Nudnik Configuration error: {}'.format(e))
        sys.exit(1)
    except FileNotFoundError:
        print('Configuration file "{}" was not found, ignoring.'.format(cfg.config_file))
        pass

    for key in DEFAULTS:
        if getattr(cfg, key, None) is None:
            setattr(cfg, key, DEFAULTS[key])

    cfg.influxdb_measurement_name = 'server' if cfg.server else 'client'
    cfg.influxdb_format = '{},hostname={},{}'.format(cfg.influxdb_measurement_name, os.uname()[1], cfg.influxdb_format)
    cfg.influxdb_retransmit_format = '{},hostname={},{}'.format(cfg.influxdb_measurement_name, os.uname()[1], cfg.influxdb_retransmit_format)

    cfg.prometheus_job_name = 'server' if cfg.server else 'client'
    cfg.prometheus_url = cfg.prometheus_url.format(prometheus_protocol=cfg.prometheus_protocol,
                                                   prometheus_host=cfg.prometheus_host,
                                                   job_name=cfg.prometheus_job_name,
                                                   label_name='instance',
                                                   label_value=os.uname()[1])

    cfg.cycle_per_hour = int( 3600 / cfg.interval )

    # Clear '%' sign if provided
    fail_ratio = (re.match(r"(([0-9])*(\.)*([0-9])*)", str(cfg.fail_ratio))).groups()[0]
    cfg.fail_ratio = float(fail_ratio) if (fail_ratio != '') else 0.0

    for i in range(1, 6):
        attr = 'v'*i
        setattr(cfg, attr, cfg.verbose >= i)

    if cfg.v:
        cfg.debug = True

    if cfg.vvvvv:
        print('Python version: {}'.format(sys.version_info))
        print('Effective configuration values:')
        for key in DEFAULTS:
            print('{} - {}'.format(key, getattr(cfg, key)))

    load_list = list()
    if cfg.load is not None:
        for load in cfg.load:
            try:
                load = nudnik.entity_pb2.Load(load_type=load[0], value=load[1])
                load_list.append(load)
            except ValueError as e:
                print('{} - "{}"'.format(e, load[0]))
                sys.exit(1)
    cfg.load_list = load_list
    return cfg

def get_logger(debug=False):
  ''' Initialize logging configuration '''
  format = '%(asctime)-15s %(levelname).5s %(process)d %(threadName)s [%(module)s] [%(funcName)s:%(lineno)d] - %(message)s'
  logging.basicConfig(format=format)
  logger = logging.getLogger(__name__)

  if debug:
      logger.setLevel(logging.DEBUG)
#      logger.debug('Debug-mode logging enabled')
  else:
      logger.setLevel(logging.INFO)

  return logger

def generate_load(logger, load):
    if load.load_type == 0:
        time_sleep = float(load.value)
        logger.debug('Sleeping for {}'.format(time_sleep))
        time.sleep(time_sleep)
    elif load.load_type == 1:
        time_sleep = random.uniform(0.0, float(load.value))
        logger.debug('Sleeping for random value {}'.format(time_sleep))
        time.sleep(time_sleep)
    elif load.load_type == 2:
        time_load = load.value
        logger.debug('CPU loading for {} seconds'.format(time_load))
        for i in range(0, os.sysconf('SC_NPROCESSORS_ONLN')):
            load_thread = threading.Thread(target=generate_load_cpu, args=(time_load,));
            load_thread.daemon = True
            load_thread.start()
    elif load.load_type == 3:
        amount_in_mb = load.value
        logger.debug('Loading {} MB to RAM'.format(amount_in_mb))
        load_thread = threading.Thread(target=generate_load_mem, args=(amount_in_mb,));
        load_thread.daemon = True
        load_thread.start()
    elif load.load_type == 4:
        args = load.value
        logger.debug('Executing process {}'.format(args.split()))
        load_thread = threading.Thread(target=generate_load_cmd, args=(args,));
        load_thread.daemon = True
        load_thread.start()
        load_thread.join()
    elif load.load_type == 5:
        args = load.value
        logger.debug('Background executing process {}'.format(args.split()))
        load_thread = threading.Thread(target=generate_load_cmd, args=(args,));
        load_thread.daemon = True
        load_thread.start()

def generate_load_cpu(time_load):
    started_at = time.time()
    while ((time.time() - started_at) < int(time_load)):
        pass

def generate_load_mem(amount_in_mb):
    urandom = os.urandom(int(amount_in_mb) * 1024 * 1024)

def generate_load_cmd(args):
    p = subprocess.Popen(args.split(),
                         shell=False,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)

    return p.communicate()

def get_meta(cfg):

    if cfg.meta is not None and cfg.meta != '':
        if cfg.meta[0] == '@':
            meta_filepath = cfg.meta[1:]
            if meta_filepath in ['random', 'urandom', '/dev/random', '/dev/urandom']:
                return os.urandom(_MAX_MESSAGE_SIZE_GRPC_BUG)
            with open(cfg.meta[1:], 'rb') as f:
                return f.read(_MAX_MESSAGE_SIZE_GRPC_BUG)
        else:
            return cfg.meta

    return ""

def time_ns():
    # Python < 3.7 doesn't support time.time_ns(), this function unifies stats measurments
    return int(("%.9f" % time.time()).replace('.',''))

def diff_nanoseconds(before, after):
    return (after - before)

def diff_seconds(before, after):
    return ((after - before) / _BILLION)

def time_to_date(timestamp):
    return datetime.fromtimestamp( timestamp / _BILLION )

class ChaosException(Exception): pass
