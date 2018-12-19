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
import threading
import requests_unixsocket

import nudnik.utils as utils

class Stats(threading.Thread):

    def __init__(self, cfg):
        threading.Thread.__init__(self)
        self.gtfo = False
        self.lock = threading.Lock()
        self.stats = list()
        self.successful_requests = 0
        self.failed_requests = 0
        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.workers = list()

        if 'file' in self.cfg.stats:
            self.file_path = cfg.file_path
        if 'influxdb' in self.cfg.stats:
            if cfg.influxdb_protocol == 'http+unix':
                self.influxdb_host = cfg.influxdb_socket_path.replace('/', '%2F')
            else:
                self.influxdb_host = cfg.influxdb_host

            create_influxdb_database(self, self.log, cfg.influxdb_protocol, self.influxdb_host, cfg.influxdb_database_name)
            self.influxdb_url = cfg.influxdb_url.format(influxdb_protocol=cfg.influxdb_protocol,
                                                        influxdb_host=self.influxdb_host,
                                                        influxdb_database_name=cfg.influxdb_database_name)

        self.log.debug('Stats thread initiated')

    def run(self):
        self.log.debug('Running {}'.format(self.name))
        while not self.gtfo:
            time_start = utils.time_ns()

            current_report = list(self.stats)
            current_report_length = len(current_report)
            if current_report_length > 0:
                if self.cfg.vvv:
                    self.log.debug('Reporting {}/{} items'.format(current_report_length, len(self.stats)))

                if self.cfg.debug:
                    for stat in _parse_stats(current_report, self.cfg.out_format, self.cfg.out_retransmit_format):
                        self.log.debug(stat)
                elif 'stdout' in self.cfg.stats:
                    for stat in _parse_stats(current_report, self.cfg.out_format, self.cfg.out_retransmit_format):
                        self.log.info(stat)

                if 'file' in self.cfg.stats:
                    thread = FileStats(self.log, self.file_path, current_report, self.cfg.out_format, self.cfg.out_retransmit_format)
                    thread.start()
                    self.workers.append(thread)
                if 'influxdb' in self.cfg.stats:
                    thread = InfluxdbStats(self.log, self.influxdb_url, current_report, self.cfg.influxdb_format, self.cfg.influxdb_retransmit_format)
                    thread.start()
                    self.workers.append(thread)
                if 'prometheus' in self.cfg.stats:
                    thread = PrometheusStats(self.log, self.cfg.prometheus_url, current_report, self.cfg.prometheus_format, self.cfg.prometheus_retransmit_format)
                    thread.start()
                    self.workers.append(thread)

                for i in range(0, current_report_length):
                    if self.cfg.vvvvv:
                        self.log.debug('Popping {}/{} items'.format(i, current_report_length))
                    self.stats.pop(0)

                while len(self.workers) > 0:
                    for index, thread in enumerate(self.workers):
                        if thread.is_alive():
                            thread.join(0.25)
                        else:
                            self.workers.pop(index)

            elif self.cfg.vvvv:
                self.log.debug('Nothing to report')

            elapsed = utils.diff_seconds(time_start, utils.time_ns())
            if elapsed < self.cfg.stats_interval:
                time.sleep(self.cfg.stats_interval - elapsed)

    def add_success(self):
        with self.lock:
            self.successful_requests += 1

    def add_failure(self):
        with self.lock:
            self.failed_requests += 1

    def get_fail_ratio(self):
        total = self.failed_requests + self.successful_requests
        try:
            current_fail_ratio = float((self.failed_requests / total) * 100)
        except ZeroDivisionError:
            current_fail_ratio = 100.0

        if self.cfg.vvvvv:
            logformat = 'failed={},success={},current_fail_ratio={},conf_fail_ratio={}'
            self.log.debug(logformat.format(self.failed_requests,
                                            self.successful_requests,
                                            current_fail_ratio,
                                            self.cfg.fail_ratio))
        return current_fail_ratio

    def append(self, stat):
        self.stats.append(stat)

    def exit(self):
        self.gtfo = 1

class FileStats(threading.Thread):
    def __init__(self, log, path, data, format, retransmit_format):
        threading.Thread.__init__(self)
        self.log = log
        self.path = path
        self.data = data
        self.format = format
        self.retransmit_format = retransmit_format

    def run(self):
        data = list()
        for stat in _parse_stats(self.data, self.format, self.retransmit_format):
            data.append(stat)
        self.log.debug('Writing {} items to {}'.format(len(data), self.path))
        with open(self.path, 'a') as statsfile:
            statsfile.write('\n'.join(data))
            statsfile.write('\n')
        return True

class InfluxdbStats(threading.Thread):
    def __init__(self, log, url, data, format, retransmit_format):
        threading.Thread.__init__(self)
        self.log = log
        self.session = requests_unixsocket.Session()
        self.url = url
        self.data = data
        self.format = format
        self.retransmit_format = retransmit_format

    def run(self):
        data = list()
        for stat in _parse_stats(self.data, self.format, self.retransmit_format):
            data.append(stat)

        self.log.debug('Writing {} items to InfluxDB'.format(len(data)))
        session = requests_unixsocket.Session()
        res = session.post(self.url, data='\n'.join(data))
        session.close()
        if res.status_code != 204:
            self.log.error('Response: "{}"'.format(res.text))
            return False
        return True

def create_influxdb_database(self, log, protocol, host, database_name):
    # https://docs.influxdata.com/influxdb/v1.7/tools/api/
    # https://docs.influxdata.com/influxdb/v1.7/query_language/database_management/#create-database
    query ='q=CREATE DATABASE "{}"'.format(database_name)
    session = requests_unixsocket.Session()
    res = session.post('{}://{}/query?{}'.format(protocol, host, query))
    session.close()
    if res.status_code == 200:
        log.debug('Response to {}: "{}"'.format(query, res.text))
    else:
        log.error('Response to {}: "{}"'.format(query, res.text))
        raise RuntimeException(res.text)

class PrometheusStats(threading.Thread):
    def __init__(self, log, url, data, format, retransmit_format):
        threading.Thread.__init__(self)
        self.log = log
        self.session = requests_unixsocket.Session()
        self.url = url
        self.data = data
        self.format = format
        self.retransmit_format = retransmit_format

    def run(self):
        session = requests_unixsocket.Session()
        # TODO handle PUT
        for stat in _parse_stats(self.data, self.format, self.retransmit_format):
            self.log.warn('Writing {} to Prometheus {}'.format(stat, self.url))
            res = session.post(self.url, stat)
            if res.status_code != 202:
                self.log.error('Response: "{}"'.format(res.text))
            return False

        session.close()
        return True

class Stat(object):
    def __init__(self, request, response, recieved_at):
        self.request = request
        self.response = response
        self.recieved_at = recieved_at

def _parse_stats(stats, format, retransmit_format):
    for stat in stats:
        if stat.request.rcount == 0:
            dataformat = format
        else:
            dataformat = retransmit_format

        statstring = dataformat.format(recieved_at_str=str(stat.recieved_at),
                                       recieved_at=stat.recieved_at,
                                       status_code=stat.response.status_code,
                                       req=stat.request,
                                       cdelta=utils.diff_nanoseconds(stat.request.ctime, stat.request.stime),
                                       rdelta=utils.diff_nanoseconds(stat.request.rtime, stat.request.stime),
                                       sdelta=utils.diff_nanoseconds(stat.request.stime, stat.response.ctime),
                                       pdelta=utils.diff_nanoseconds(stat.response.ctime, stat.response.stime),
                                       bdelta=utils.diff_nanoseconds(stat.response.stime, stat.recieved_at),
                                       rtt=utils.diff_nanoseconds(stat.request.ctime, stat.recieved_at))
        yield statstring

