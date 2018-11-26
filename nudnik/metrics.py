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

class MetricsThread(threading.Thread):
    def __init__(self, cfg):
        threading.Thread.__init__(self)
        self.gtfo = False

        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.report_count = max(1, (self.cfg.streams * self.cfg.interval * self.cfg.rate) - 1)

    def run(self):
        pass

    def _report(self, metrics):
        pass

    def exit(self):
        self.gtfo = 1

class FileMetrics(threading.Thread):
    def __init__(self, cfg, path, data):
        MetricsThread.__init__(self, cfg)
        self.log = utils.get_logger(cfg.debug)
        self.metrics_url = path
        self.data = data
        self.name = '{}-file-metrics'.format(cfg.name)
        self.log.debug('Metrics {} initiated in file mode'.format(self.name))

    def run(self):
        self.log.debug('Running {}'.format(self.name))

        while not self.gtfo:
            time_start = time.time_ns()

            if len(self.data) > self.report_count:
                self.log.debug('Reporting {}/{} items'.format(len(self.data[:self.report_count]),len(self.data)))
                self._report(self.data[:self.report_count])
                for i in range(0, self.report_count):
                    self.data.pop(0)

            elapsed = utils.diff_seconds(time_start, time.time_ns())
            if elapsed < self.cfg.interval:
                time.sleep(self.cfg.interval - elapsed)

    def _report(self, metrics):
        self.log.debug('Writing {} items to file'.format(len(metrics)))
        with open(self.metrics_url, 'a') as metricsfile:
            metricsfile.write('\n'.join(metrics))
            metricsfile.write('\n')

class InfluxdbMetrics(threading.Thread):
    def __init__(self, cfg, data):
        MetricsThread.__init__(self, cfg)
        self.log = utils.get_logger(cfg.debug)
        self.session = requests_unixsocket.Session()
        self.metrics_url = 'http+unix://{}/write?db={}&precision=ns'.format(cfg.influxdb_socket_path.replace('/', '%2F'), cfg.influxdb_database_name)
        self.data = data
        self.name = '{}-influxb-metrics'.format(cfg.name)
        self.log.debug('Metrics {} initiated in Influxdb mode'.format(self.name))

    def run(self):
        self.log.debug('Running {}'.format(self.name))

        while not self.gtfo:
            time_start = time.time_ns()

            if len(self.data) > self.report_count:
                self.log.debug('Reporting {}/{} items'.format(len(self.data[:self.report_count]),len(self.data)))
                self._report(self.data[:self.report_count])
                for i in range(0, self.report_count):
                    self.data.pop(0)

            elapsed = utils.diff_seconds(time_start, time.time_ns())
            if elapsed < self.cfg.interval:
                time.sleep(self.cfg.interval - elapsed)

    def _report(self, metrics):
        self.log.debug('Writing {} items to socket'.format(len(metrics)))
        res = self.session.post(self.metrics_url, data='\n'.join(metrics))
        if res.status_code != 204:
            self.log.error('Response: "{}"'.format(r.text))

