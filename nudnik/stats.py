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
import threading
import requests_unixsocket

import nudnik.utils as utils
import nudnik.outputs

class Stats(threading.Thread):

    def __init__(self, cfg):
        threading.Thread.__init__(self)
        self.gtfo = False
        self.event = threading.Event()
        self.lock = threading.Lock()
        self.stats = list()
        self.successful_requests = 0
        self.failed_requests = 0
        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.workers = list()

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
                    for stat in _parse_stats(self.log, current_report, self.cfg.stats_format_stdout, self.cfg.stats_format_retransmit_stdout):
                        self.log.debug(stat)
                elif 'stdout' in self.cfg.stats:
                    for stat in _parse_stats(self.log, current_report, self.cfg.stats_format_stdout, self.cfg.stats_format_retransmit_stdout):
                        self.log.info(stat)

                if 'file' in self.cfg.stats:
                    thread = FileStats(self.log, self.cfg.stats_file_path, current_report, self.cfg.stats_format_file, self.cfg.stats_format_retransmit_file)
                    thread.start()
                    self.workers.append(thread)
                if 'influxdb' in self.cfg.stats:
                    thread = InfluxdbStats(self.log, self.cfg.influxdb_url_stats, current_report, self.cfg.stats_format_influxdb, self.cfg.stats_format_retransmit_influxdb)
                    thread.start()
                    self.workers.append(thread)
                if 'prometheus' in self.cfg.stats:
                    thread = PrometheusStats(self.log, self.cfg.prometheus_url_stats, current_report, self.cfg.stats_format_prometheus, self.cfg.stats_format_retransmit_prometheus)
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
                self.event.wait(timeout=(self.cfg.stats_interval - elapsed))

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
        self.event.set()

class FileStats(nudnik.outputs.FileOutput):
    def __init__(self, log, path, data, format, retransmit_format):
        super(FileStats, self).__init__(log, path, data, format)
        self.retransmit_format = retransmit_format

    def parse(self):
        for stat in _parse_stats(self.log, self.data, self.format, self.retransmit_format):
            self.parsed_data.append(stat)

class InfluxdbStats(nudnik.outputs.FileOutput):
    def __init__(self, log, url, data, format, retransmit_format):
        super(FileStats, self).__init__(log, url, data, format)
        self.retransmit_format = retransmit_format

    def parse(self):
        for stat in _parse_stats(self.log, self.data, self.format, self.retransmit_format):
            self.parsed_data.append(stat)

class PrometheusStats(nudnik.outputs.FileOutput):
    def __init__(self, log, url, data, format, retransmit_format):
        super(FileStats, self).__init__(log, url, data, format)
        self.retransmit_format = retransmit_format

    def parse(self):
        for stat in _parse_stats(self.log, self.data, self.format, self.retransmit_format):
            self.parsed_data.append(stat)

class Stat(utils.NudnikObject):
    def __init__(self, request, response, timestamp):
        super(Stat, self).__init__(timestamp)
        self.request = request
        self.response = response

def _parse_stats(log, stats, format, retransmit_format):
    for stat in stats:
        if stat.request.rcount == 0:
            dataformat = format
        else:
            dataformat = retransmit_format

        try:
            statstring = dataformat.format(timestamp_str=str(stat.timestamp),
                                           timestamp=stat.timestamp,
                                           req=stat.request,
                                           res=stat.response,
                                           cdelta=utils.diff_nanoseconds(stat.request.ctime, stat.request.stime),
                                           rdelta=utils.diff_nanoseconds(stat.request.rtime, stat.request.stime),
                                           sdelta=utils.diff_nanoseconds(stat.request.stime, stat.response.ctime),
                                           pdelta=utils.diff_nanoseconds(stat.response.ctime, stat.response.stime),
                                           bdelta=utils.diff_nanoseconds(stat.response.stime, stat.timestamp),
                                           rtt=utils.diff_nanoseconds(stat.request.ctime, stat.timestamp))
        except Exception as e:
            log.fatal('Fatal error occured while parsing provided format"{}", {}'.format(dataformat, str(e)))
            break

        yield statstring

