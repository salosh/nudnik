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
import time
import re
from datetime import datetime
import random

if sys.version_info < (3, 0):
    from exceptions import IOError as FileNotFoundError

import nudnik

_BILLION = 10**9

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
    parser.add_argument('--chaos', '-c',
                        type=int,
                        help='Compute statistical process level random crashes [0, 3600/interval] (Default: 0)')
    parser.add_argument('--load', '-l',
                        type=str,
                        nargs=2,
                        action='append',
                        metavar=('load_type', 'load_value'),
                        dest='load',
                        help='Add artificial load [rtt, rttr, cpu, mem] (Default: None)')
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
    parser.add_argument('--metrics', '-m',
                        type=str,
                        action='append',
                        choices=['stdout', 'file', 'influxdb'],
                        help='Enable metrics outputs (Default: None)')
    parser.add_argument('--file-path', '-F',
                        type=str,
                        help='Path to exported metrics file (Default: ./nudnikmetrics.out)')
    parser.add_argument('--influxdb-socket-path',
                        type=str,
                        help='Absolute path to InfluxDB Unix socket (Default: /var/run/influxdb/influxdb.sock)')
    parser.add_argument('--influxdb-database-name',
                        type=str,
                        help='InfluxDB database name (Default: nudnikmetrics)')
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
      'config_file': 'config.yml',
      'host': '127.0.0.1',
      'port': 5410,
      'server': False,
      'name': 'NAME',
      'name_mismatch_error': None,
      'meta': None,
      'streams': 1,
      'initial_stream_index': 0,
      'interval': 1,
      'rate': 1,
      'chaos': 0,
      'chaos_string': 'In all chaos there is a cosmos, in all disorder a secret order. #Carl_Jung_FTW',
      'load': [],
      'retry_count': -1,
      'fail_ratio': 0,
      'ruok': False,
      'ruok_port': 80,
      'ruok_path': '/ruok',
      'metrics': [],
      'file_path': './nudnikmetrics.out',
      'out_format': '{recieved_at_str},{status_code},{req.name},{req.message_id},{req.ctime},{cdelta},rtt={rtt}',
      'out_retransmit_format': '{recieved_at_str},{status_code},{req.name},{req.message_id},{req.ctime},{req.rtime},{cdelta},{rdelta},{req.rcount},rtt={rtt}',
      'influxdb_socket_path': '/var/run/influxdb/influxdb.sock',
      'influxdb_protocol': 'http+unix',
      'influxdb_host': '127.0.0.1:8086',
      'influxdb_database_name': 'nudnikmetrics',
      'influxdb_url': '{influxdb_protocol}://{influxdb_host}/write?db={influxdb_database_name}&precision=ns',
      # First field for InfluxDB is measurment name
      'influxdb_format': 'request,status={status_code},name={req.name} mid={req.message_id},ctime={req.ctime},cdelta={cdelta},rtt={rtt} {recieved_at}',
      'influxdb_retransmit_format': 'request,status={status_code},name={req.name} mid={req.message_id},ctime={req.ctime},rtime={req.rtime},cdelta={cdelta},rdelta={rdelta},rcount={req.rcount},rtt={rtt} {recieved_at}',
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
                if ymlcfg[confkey] is not None and not getattr(cfg, confkey, None) is None:
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
            load = nudnik.entity_pb2.Load(load_type=load[0], value=load[1])
            load_list.append(load)
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
            cpu_load_thread = FakeLoadCpu(time_load).start()
    elif load.load_type == 3:
        amount_in_mb = load.value
        logger.debug('Loading {} MB to RAM'.format(amount_in_mb))
        mem_load_thread = FakeLoadMem(amount_in_mb)
        mem_load_thread.start()

def time_ns():
    # Python < 3.7 doesn't support time.time_ns(), this function unifies metrics measurments
    return int(("%.9f" % time.time()).replace('.',''))

def diff_nanoseconds(before, after):
    return (after - before)

def diff_seconds(before, after):
    return ((after - before) / _BILLION)

def time_to_date(timestamp):
    return datetime.fromtimestamp( timestamp / _BILLION )

class ChaosException(Exception): pass
