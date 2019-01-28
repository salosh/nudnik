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
import json
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
from nudnik.entity_pb2 import Load
import nudnik.outputs

_BILLION = float(10**9)

DEFAULTS = {
    'config_file': '',
    'host': '127.0.0.1',
    'port': 5410,
    'dns_ttl': 10,
    'server': False,
    'name': 'NAME',
    'name_mismatch_error': None,
    'meta': None,
    'meta_size': (4194304 - 48),
    'workers': os.sysconf('SC_NPROCESSORS_ONLN'),
    'streams': 1,
    'initial_stream_index': 0,
    'interval': 1,
    'rate': 1,
    'timeout': 1,
    'count': 0,
    'chaos': 0,
    'chaos_string': 'In all chaos there is a cosmos, in all disorder a secret order. #Carl_Jung_FTW',
    'load': [],
    'retry_count': -1,
    'fail_ratio': 0,
    'ruok': False,
    'ruok_host': '127.0.0.1',
    'ruok_port': 5310,
    'ruok_path': '/ruok',
    'metrics': [],
    'metrics_interval': 1,
    'metrics_file_path': './nudnikmetrics.out',
    'metrics_format_stdout': '{timestamp},{node.platform},{cpu.usage},{mem.percent}',
    'metrics_format_file': '{timestamp},{node.platform},{cpu.usage},{mem.percent}',
    'metrics_format_influxdb': 'cpu,hostname={node.nodename} {cpu._csv} {timestamp}\nmem,hostname={node.nodename} {mem._csv} {timestamp}\nnet,hostname={node.nodename} {net._csv} {timestamp}',
    'metrics_format_prometheus': '# TYPE nudnik_metrics summary\nnudnik_metrics{{distro="{node.platform}",cpu_usage="{cpu.usage}", percent="{mem.percent}"}} {timestamp}\n',
    'stats': [],
    'stats_interval': 1,
    'stats_file_path': './nudnikstats.out',
    'stats_format_stdout': '{timestamp_str},{res.status_code},{req.name},{req.message_id},{req.ctime},{cdelta},rtt={rtt}',
    'stats_format_retransmit_stdout': '{timestamp_str},{res.status_code},{req.name},{req.message_id},{req.ctime},{req.rtime},{cdelta},{rdelta},{req.rcount},rtt={rtt}',
    'stats_format_file': '{timestamp_str},{res.status_code},{req.name},{req.message_id},{req.ctime},{cdelta},rtt={rtt}',
    'stats_format_retransmit_file': '{timestamp_str},{res.status_code},{req.name},{req.message_id},{req.ctime},{req.rtime},{cdelta},{rdelta},{req.rcount},rtt={rtt}',
    'stats_format_influxdb': '{mode},hostname={node.nodename},status={res.status_code},name={req.name},sid={req.stream_id},wid={req.worker_id},qid={req.sequence_id} sid={req.stream_id},wid={req.worker_id},mid={req.message_id},ctime={req.ctime},cdelta={cdelta},sdelta={sdelta},pdelta={pdelta},bdelta={bdelta},rtt={rtt} {timestamp}',
    'stats_format_retransmit_influxdb': '{mode},hostname={node.nodename},status={res.status_code},name={req.name},sid={req.stream_id},wid={req.worker_id},qid={req.sequence_id} sid={req.stream_id},wid={req.worker_id},mid={req.message_id},ctime={req.ctime},rtime={req.rtime},cdelta={cdelta},sdelta={sdelta},pdelta={pdelta},bdelta={bdelta},rdelta={rdelta},rcount={req.rcount},rtt={rtt} {timestamp}',
    'stats_format_prometheus': '# TYPE nudnik_message summary\nnudnik_message{{ctime="{req.ctime}",message_id="{req.message_id}", rtt="{rtt}", name="{req.name}"}} {timestamp}\n',
    'stats_format_retransmit_prometheus': '# TYPE nudnik_message summary\nnudnik_message{{ctime="{req.ctime}",message_id="{req.message_id}", rtt="{rtt}", name="{req.name}"}} {timestamp}\n',
    'influxdb_socket_path': '/var/run/influxdb/influxdb.sock',
    'influxdb_protocol': 'http+unix',
    'influxdb_host': '127.0.0.1',
    'influxdb_port': '8086',
    'influxdb_database_prefix': 'nudnik',
    'influxdb_url': '{influxdb_protocol}://{influxdb_host}/write?db={influxdb_database_name}&precision=ns',
    'prometheus_protocol': 'http',
    'prometheus_host': '127.0.0.1',
    'prometheus_port': '9091',
    'prometheus_url': '{prometheus_protocol}://{prometheus_host}:{prometheus_port}/{type}/job/{job_name}/{label_name}/{label_value}',
    'extra': [],
    'debug': False,
    'verbose': 0,
}

class NudnikConfiguration(object):

    def __init__(self):
        self._fields = list()

    def get(self, key, default=None):
        return getattr(self, key, default)

    def set(self, key, value):
        setattr(self, key, value)

    def __iter__(self):
        i = 0
        while i < len(self._fields):
            yield self[i]
            i += 1

    def __len__(self):
        return len(self._fields)

    def __getitem__(self, index):
        return self._fields[index]

    def __setitem__(self, key, value):
        self.set(key, value)

    def __setattr__(self, key, value):
        super(NudnikConfiguration, self).__setattr__(key, value)
        if not key.startswith('_'):
            self._fields.append(key)

    def dict(self):
        d = dict()
        for k in self:
            d.update({k: self.get(k)})
        return d

    def json(self):
        return json.dumps(self.dict())

    def yaml(self):
        return yaml.dump(self.dict())

    def read_config_file(self, file_path, fail_if_missing):
        try:
            with open(file_path, 'r') as ymlfile:
                ymlcfg = yaml.load(ymlfile)

                if not isinstance(ymlcfg, dict):
                    raise FileNotFoundError

                for confkey in DEFAULTS:
                    if confkey in ymlcfg and ymlcfg[confkey] is not None and getattr(self, confkey, None) is None:
                        value = cast_arg_by_type(confkey, ymlcfg[confkey])
                        self.set(confkey, value)

        except yaml.parser.ParserError as e:
            print('Nudnik Configuration error: {}'.format(e))
            sys.exit(1)
        except FileNotFoundError as e:
            print('Unable to read optional configuration file "{}"'.format(file_path))
            if fail_if_missing:
                raise e

def parse_args():
    parser = argparse.ArgumentParser(
        description='Nudnik - gRPC load tester',
        epilog='2019 (C) Salo Shp <https://github.com/salosh/nudnik.git>'
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
    parser.add_argument('--dns-ttl',
                        type=int,
                        help='Number of seconds before forcing "host" name lookup (Default: 10)')
    parser.add_argument('--server', '-S',
                        action='store_true',
                        default=None,
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
    parser.add_argument('--timeout',
                        type=int,
                        help='Maximum number of seconds before failing a request (Default: 1)')
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
                        help='Add artificial load [rtt, rttr, cpu, mem, bcmd, fcmd] (Default: None)')
    parser.add_argument('--retry-count',
                        type=int,
                        help='Number of times to re-send failed messages (Default: -1, which means infinite times)')
    parser.add_argument('--fail-ratio',
                        type=str,
                        help='Percent of requests to intentionally fail (Default: 0)')
    parser.add_argument('--ruok', '-R',
                        action='store_true',
                        default=None,
                        help='Enable "Are You OK?" HTTP/1.1 API (default: False)')
    parser.add_argument('--metrics', '-m',
                        type=str,
                        action='append',
                        choices=['stdout', 'file', 'influxdb', 'prometheus'],
                        help='Enable metrics outputs (Default: None)')
    parser.add_argument('--stats', '-t',
                        type=str,
                        action='append',
                        choices=['stdout', 'file', 'influxdb', 'prometheus'],
                        help='Enable stats outputs (Default: None)')
    parser.add_argument('--extra', '-e',
                        type=str,
                        action='append',
                        default=[],
                        help='Extra args (Default: None)')
    parser.add_argument('--debug', '-d',
                        action='store_true',
                        default=None,
                        help='Debug mode (default: False)')
    parser.add_argument('--verbose', '-v',
                        action='count',
                        help='Verbose mode, specify multiple times for extra verbosity (default: None)')
    parser.add_argument('--version', '-V',
                        action='version',
                        version='Nudnik v{} - 2019 (C) Salo Shp <https://github.com/salosh/nudnik.git>'.format(nudnik.__version__),
                        help='Display Nudnik version')

    args = parser.parse_args()
    return args

def parse_config(args):
    cfg = NudnikConfiguration()

    cfg.config_file = DEFAULTS['config_file']

    extra_args = dict()
    for mkv in args.extra:
        arg = mkv.split('=', 1)
        extra_args[arg[0]] = arg[1]

    for key in DEFAULTS:
        env_key_name = 'NUDNIK_{key_name}'.format(key_name=key.upper())
        value = None
        if key in args.__dict__ and vars(args)[key] is not None:
            value = vars(args)[key]
        elif key in extra_args and extra_args[key] is not None:
            value = cast_arg_by_type(key, extra_args[key])
        elif env_key_name in os.environ:
            value = cast_arg_by_type(key, os.environ[env_key_name])

        if value is not None:
            cfg.set(key, value)

    if cfg.config_file != '':
        cfg.read_config_file(cfg.config_file, True)
    else:
        cfg.read_config_file('{}/.nudnikrc'.format(os.environ['HOME']), False)
        cfg.read_config_file('/etc/nudnik/config.yml', False)

    for key in DEFAULTS:
        if cfg.get(key) is None:
            cfg.set(key, DEFAULTS[key])

    if 'influxdb' in cfg.stats or 'influxdb' in cfg.metrics:
        if cfg.influxdb_protocol == 'http+unix':
            cfg.influxdb_host_port = cfg.influxdb_socket_path.replace('/', '%2F')
        else:
            cfg.influxdb_host_port = '{}:{}'.format(cfg.influxdb_host, cfg.influxdb_port)

        database_name_stats = '{}stats'.format(cfg.influxdb_database_prefix)
        database_name_metrics = '{}metrics'.format(cfg.influxdb_database_prefix)

        cfg.influxdb_url_stats = cfg.influxdb_url.format(influxdb_protocol=cfg.influxdb_protocol,
                                               influxdb_host=cfg.influxdb_host_port,
                                               influxdb_database_name=database_name_stats)
        cfg.influxdb_url_metrics = cfg.influxdb_url.format(influxdb_protocol=cfg.influxdb_protocol,
                                               influxdb_host=cfg.influxdb_host_port,
                                               influxdb_database_name=database_name_metrics)

        nudnik.outputs.create_influxdb_database(cfg.influxdb_protocol, cfg.influxdb_host_port, database_name_stats)
        nudnik.outputs.create_influxdb_database(cfg.influxdb_protocol, cfg.influxdb_host_port, database_name_metrics)

    if 'prometheus' in cfg.stats or 'prometheus' in cfg.metrics:
        cfg.prometheus_job_name = 'server' if cfg.server else 'client'
        cfg.prometheus_url_stats = cfg.prometheus_url.format(prometheus_protocol=cfg.prometheus_protocol,
                                                         prometheus_host=cfg.prometheus_host,
                                                         prometheus_port=cfg.prometheus_port,
                                                         type='stats',
                                                         job_name=cfg.prometheus_job_name,
                                                         label_name='instance',
                                                         label_value=os.uname()[1])
        cfg.prometheus_url_metrics = cfg.prometheus_url.format(prometheus_protocol=cfg.prometheus_protocol,
                                                         prometheus_host=cfg.prometheus_host,
                                                         prometheus_port=cfg.prometheus_port,
                                                         type='metrics',
                                                         job_name=cfg.prometheus_job_name,
                                                         label_name='instance',
                                                         label_value=os.uname()[1])

    cfg.cycle_per_hour = int( 3600 / cfg.interval )

    # Clear '%' sign if provided
    fail_ratio = (re.match(r"(([0-9])*(\.)*([0-9])*)", str(cfg.fail_ratio))).groups()[0]
    cfg.fail_ratio = float(fail_ratio) if (fail_ratio != '') else 0.0

    for i in range(1, 6):
        attr = 'v'*i
        cfg.set(attr, cfg.verbose >= i)

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
                load = Load(load_type=load[0], value=load[1])
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

def cast_arg_by_type(key, value):
    if type(DEFAULTS[key]) is bool:
        if value in [True, 'TRUE', 'True', 'true', 'YES', 'Yes', 'yes', '1', 1]:
            return True
        elif value in [False, 'FALSE', 'False', 'false', 'NO', 'No', 'no', '0', 0]:
            return False
    elif isinstance(DEFAULTS[key], int):
        return int(value)
    elif isinstance(DEFAULTS[key], str):
        return str(value)

    return value

def generate_load(logger, load, meta):
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
    elif load.load_type in [4, 5]:
        if load.value == 'meta':
            args = str(meta)
        else:
            args = load.value
        logger.debug('Executing process {}'.format(args.split()))
        load_thread = threading.Thread(target=generate_load_cmd, args=(args,));
        load_thread.daemon = True
        load_thread.start()
        if load.load_type == 5:
            load_thread.join()

def generate_load_cpu(time_load):
    started_at = time.time()
    while ((time.time() - started_at) < float(time_load)):
        pass

def generate_load_mem(amount_in_mb):
    urandom = os.urandom(int(amount_in_mb) * 1024 * 1024)

def generate_load_cmd(args):
    p = subprocess.Popen(args.split(),
                         shell=False,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)

    return p.communicate()

def get_meta(meta, size=0):

    if meta is not None and meta != '':
        if meta[0] == '@':
            meta_filepath = meta[1:]
            if meta_filepath in ['random', 'urandom', '/dev/random', '/dev/urandom']:
                return os.urandom(size)
            with open(meta[1:], 'rb') as f:
                return f.read(size)
        else:
            return meta.encode()

    return ''.encode()

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

class NudnikObject(object):

    def __init__(self, timestamp=time_ns()):
        self.timestamp = timestamp

    @property
    def _csv(self):
        csv = []
        for key in self.__dict__:
            if not key.startswith('_'):
                csv.append('{k}={v}'.format(k=key, v=getattr(self, key)))
        return ','.join(csv)

    @property
    def _qcsv(self):
        csv = []
        for key in self.__dict__:
            if not key.startswith('_'):
                csv.append('{k}="{v}"'.format(k=key, v=getattr(self, key)))
        return ','.join(csv)
