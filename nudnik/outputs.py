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

class Output(threading.Thread):
    def __init__(self, log, data, format):
        threading.Thread.__init__(self)
        self.log = log
        self.data = data
        self.parsed_data = []
        self.format = format

    def run(self):
        self.parse()
        self.out()

    def parse(self):
        pass

    def out(self):
        pass

class PrintOutput(Output):

    def out(self):
        print(self.format.format(self.data))

class FileOutput(Output):
    def __init__(self, log, path, mode, data, format):
        super(FileOutput, self).__init__(log, data, format)
        self.mode = mode
        self.path = path

    def out(self):
        self.log.debug('Writing {} items to {}'.format(len(self.parsed_data), self.path))
        with open(self.path, 'a') as statsfile:
            statsfile.write('\n'.join(self.parsed_data))
            statsfile.write('\n')

class InfluxdbOutput(Output):
    def __init__(self, log, url, mode, data, format):
        super(InfluxdbOutput, self).__init__(log, data, format)
        self.mode = mode
        self.url = url

    def out(self):
        self.log.debug('Writing {} items to InfluxDB'.format(len(self.parsed_data)))
        session = requests_unixsocket.Session()
        res = session.post(self.url, data='\n'.join(self.parsed_data))
        session.close()
        if res.status_code != 204:
            self.log.error('InfluxDB response: "{}"'.format(res.text))

class PrometheusOutput(Output):
    def __init__(self, log, url, mode, data, format):
        super(PrometheusOutput, self).__init__(log, data, format)
        self.mode = mode
        self.url = url

    def out(self):
        self.log.debug('Writing {} to Prometheus {}'.format(len(self.parsed_data), self.url))
        session = requests_unixsocket.Session()
        # TODO handle PUT
        for stat in self.parsed_data:
            res = session.post(self.url, stat)
            if res.status_code != 202:
                self.log.error('Response: "{}"'.format(res.text))
            return False

        session.close()
        return True

def create_influxdb_database(protocol, host, database_name):
    # https://docs.influxdata.com/influxdb/v1.7/tools/api/
    # https://docs.influxdata.com/influxdb/v1.7/query_language/database_management/#create-database
    query ='q=CREATE DATABASE "{}"'.format(database_name)
    session = requests_unixsocket.Session()
    res = session.post('{}://{}/query?{}'.format(protocol, host, query))
    session.close()
    if res.status_code == 200:
        print('Response to {}: "{}"'.format(query, res.text))
    else:
        print('Response to {}: "{}"'.format(query, res.text))
        raise RuntimeException(res.text)

