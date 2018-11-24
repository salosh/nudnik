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
from datetime import datetime

import nudnik

_BILLION = 10**9

class NudnikConfiguration(dict):
    pass

def parse_args():
    parser = argparse.ArgumentParser(
        description='Nudnik - gRPC load tester',
        epilog='2018 (C) Salo Shp <https://github.com/salosh/nudnik.git>'
    )
    parser.add_argument('--config-file',
                        type=str,
                        help='Path to YAML config file')
    parser.add_argument('--host',
                        type=str,
                        help='host')
    parser.add_argument('--port',
                        type=int,
                        help='port')
    parser.add_argument('--server',
                        action='store_true',
                        help='Operation mode (default: client)')
    parser.add_argument('--name',
                        type=str,
                        help='Parser name')
    parser.add_argument('--name-mismatch-error',
                        action='store_true',
                        help='Fail request on name mismatch (default: False)')
    parser.add_argument('--meta',
                        type=str,
                        help='Send this extra data with every request')
    parser.add_argument('--streams',
                        type=int,
                        help='Number of streams (Default: 1)')
    parser.add_argument('--interval',
                        type=int,
                        help='Number of seconds per stream message cycle (Default: 1)')
    parser.add_argument('--rate',
                        type=int,
                        help='Number of messages per interval (Default: 10)')
    parser.add_argument('--load',
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
                        type=int,
                        help='Percent of requests to intentionally fail (Default: 0)')
    parser.add_argument('--metrics-socket-path',
                        type=str,
                        help='Full path to metrics Unix socket (Default: /var/run/influxdb/influxdb.sock)')
    parser.add_argument('--metrics-db-name',
                        type=str,
                        help='Metrics database name (Default: nudnikmetrics)')
    parser.add_argument('--debug',
                        action='store_true',
                        help='Debug mode (default: False)')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Verbose mode (default: False)')
    parser.add_argument('--version',
                        action='store_true',
                        help='Display Nudnik version (default: False)')

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
      'name_mismatch_error': False,
      'meta': None,
      'streams': 1,
      'interval': 1,
      'rate': 1,
      'load': [],
      'retry_count': -1,
      'fail_ratio': 0,
      'metrics_socket_path': '/var/run/influxdb/influxdb.sock',
      'metrics_db_name': 'nudnikmetrics',
      'debug': False,
      'verbose': False,
      'version': False
    }

    for key in DEFAULTS:
        env_key_name = 'NUDNIK_{key_name}'.format(key_name=key.upper())
        if key in args.__dict__ and vars(args)[key]:
            value = vars(args)[key]
        elif env_key_name in os.environ:
            value = os.environ[env_key_name]
            if isinstance(DEFAULTS[key], int):
                value = int(value)
            elif isinstance(DEFAULTS[key], str):
                value = str(value)
            else:
                value = value
        else:
            value = DEFAULTS[key]

        setattr(cfg, key, value)

    if cfg.version:
        print('Nudnik v{version}'.format(version=nudnik.__version__))
        sys.exit(0)

    try:
        with open(cfg.config_file, 'r') as ymlfile:
            ymlcfg = yaml.load(ymlfile)

            if not isinstance(ymlcfg, dict):
                raise FileNotFoundError

            for confkey in DEFAULTS:
                if ymlcfg[confkey] is not None and not getattr(cfg, confkey, None):
                    setattr(cfg, confkey, ymlcfg[confkey])

    except yaml.parser.ParserError as e:
        print('Nudnik Configuration error: {}'.format(e))
        sys.exit(1)
    except FileNotFoundError:
        print('Could not open config file {}'.format(cfg.config_file))
        pass

    if cfg.verbose:
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
        for i in range(0, os.cpu_count()):
            cpu_load_thread = FakeLoadCpu(time_load).start()
    elif load.load_type == 3:
        amount_in_mb = load.value
        logger.debug('Loading {} MB to RAM'.format(amount_in_mb))
        mem_load_thread = FakeLoadMem(amount_in_mb)
        mem_load_thread.start()

def diff_nanoseconds(before, after):
    return (after - before)

def diff_seconds(before, after):
    return ((after - before) / _BILLION)

def time_to_date(timestamp):
    return datetime.fromtimestamp( timestamp / _BILLION )
