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
import os
import sys
import threading
import psutil
import platform

import nudnik.utils as utils
import nudnik.outputs

class Metrics(threading.Thread):

    def __init__(self, cfg):
        threading.Thread.__init__(self)
        self.gtfo = False
        self.event = threading.Event()
        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.workers = list()
        self.node = MetricNode()
        self.log.debug('Metrics thread initiated')

    def run(self):
        self.log.debug('Running {}'.format(self.name))
        mode = 'servermetrics' if self.cfg.server else 'clientmetrics'

        while not self.gtfo:
            time_start = utils.time_ns()

            metric = Metric(self.node)

            if self.cfg.debug:
                for strmetric in _parse_metrics(self.log, mode, [metric], self.cfg.metrics_format_stdout):
                    self.log.debug(strmetric)
            elif 'stdout' in self.cfg.metrics:
                for strmetric in _parse_metrics(self.log, mode, [metric], self.cfg.metrics_format_stdout):
                    self.log.info(strmetric)

            if 'file' in self.cfg.metrics:
                thread = MetricsFileOutput(self.log, self.cfg.metrics_file_path, mode, [metric], self.cfg.metrics_format_file)
                thread.start()
                self.workers.append(thread)
            if 'influxdb' in self.cfg.metrics:
                thread = MetricsInfluxdbOutput(self.log, self.cfg.influxdb_url_metrics, mode, [metric], self.cfg.metrics_format_influxdb)
                thread.start()
                self.workers.append(thread)
            if 'prometheus' in self.cfg.metrics:
                thread = MetricsPrometheusOutput(self.log, self.cfg.prometheus_url_metrics, mode, [metric], self.cfg.metrics_format_prometheus)
                thread.start()
                self.workers.append(thread)

            while len(self.workers) > 0:
                for index, thread in enumerate(self.workers):
                    if thread.is_alive():
                        thread.join(0.25)
                    else:
                        self.workers.pop(index)

            elapsed = utils.diff_seconds(time_start, utils.time_ns())
            if elapsed < self.cfg.metrics_interval:
                self.event.wait(timeout=(self.cfg.metrics_interval - elapsed))

    def exit(self):
        self.gtfo = 1
        self.event.set()

class MetricNode(utils.NudnikObject):

    def __init__(self):
        super(MetricNode, self).__init__()
        self.sysname, self.nodename, self.release, self.version, self.machine = os.uname()
        self.major, self.minor, self.micro, self.releaselevel, self.serial = sys.version_info
        for index, v in enumerate(sys.version.split('\n')):
            setattr(self, 'version_{index}'.format(index=index), v)
        self.dist = ''.join(platform.dist())
        self.distribution = ''.join(platform.linux_distribution())
        self.platform = platform.platform()

class MetricCpu(utils.NudnikObject):

    def __init__(self):
        super(MetricCpu, self).__init__()
        self.count = psutil.cpu_count()
        self.usage = psutil.cpu_percent(interval=None, percpu=False)
        freq = psutil.cpu_freq()
        # None on virtual machines
        if freq is not None:
            freq_dict = freq._asdict()
            for key in freq_dict.keys():
                setattr(self, 'freq_{key}'.format(key=key), freq_dict[key])

        stats = psutil.cpu_stats()._asdict()
        for key in stats.keys():
            setattr(self, 'stats_{key}'.format(key=key), stats[key])

        times = psutil.cpu_times()._asdict()
        for key in times.keys():
            setattr(self, '{key}'.format(key=key), times[key])

        times_percent = psutil.cpu_times_percent(interval=None, percpu=False)._asdict()
        for key in times_percent.keys():
            setattr(self, '{key}_percent'.format(key=key), times_percent[key])

class MetricMemory(utils.NudnikObject):
    def __init__(self):
        super(MetricMemory, self).__init__()

        swap = psutil.swap_memory()._asdict()
        for key in swap.keys():
            setattr(self, 'swap_{key}'.format(key=key), swap[key])

        virtual = psutil.virtual_memory()._asdict()
        for key in virtual.keys():
            setattr(self, '{key}'.format(key=key), virtual[key])

class MetricDisk(utils.NudnikObject):
    def __init__(self):
        super(MetricDisk, self).__init__()
# Waiting for https://github.com/giampaolo/psutil/issues/1354
        pass

class MetricNet(utils.NudnikObject):
    def __init__(self):
        super(MetricNet, self).__init__()
        net = psutil.net_io_counters(pernic=False, nowrap=True)._asdict()
        for key in net.keys():
            setattr(self, '{key}'.format(key=key), net[key])

class Metric(utils.NudnikObject):
    def __init__(self, node):
        super(Metric, self).__init__(timestamp=utils.time_ns())
        self.node = node
        self.cpu = MetricCpu()
        self.mem = MetricMemory()
        self.disk = MetricDisk()
        self.net = MetricNet()

class MetricsFileOutput(nudnik.outputs.FileOutput):

    def parse(self):
        for stat in _parse_metrics(self.log, self.mode, self.data, self.format):
            self.parsed_data.append(stat)

class MetricsInfluxdbOutput(nudnik.outputs.InfluxdbOutput):

    def parse(self):
        for stat in _parse_metrics(self.log, self.mode, self.data, self.format):
            self.parsed_data.append(stat)

class MetricsPrometheusOutput(nudnik.outputs.InfluxdbOutput):

    def parse(self):
        for stat in _parse_metrics(self.log, self.mode, self.data, self.format):
            self.parsed_data.append(stat)

def _parse_metrics(log, mode, metrics, dataformat):
    for metric in metrics:
        try:
            metricstring = dataformat.format(mode=mode,
                                         timestamp=metric.timestamp,
                                         node=metric.node,
                                         cpu=metric.cpu,
                                         mem=metric.mem,
                                         disk=metric.disk,
                                         net=metric.net)
        except Exception as e:
            log.fatal('Fatal error occured while parsing provided format: "{}", {}'.format(dataformat, e))
            break

        yield metricstring

def _minus_h(b):
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y', 'S')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10
    for s in reversed(symbols):
        if b >= prefix[s]:
            value = float(b) / prefix[s]
            return '%.3f%s' % (value, s)
    return '%.3fB' % (b)


