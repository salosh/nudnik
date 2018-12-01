# -*- coding: utf-8 -*-
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
import sys

import nudnik.metrics
import nudnik.server
import nudnik.client
import nudnik.utils as utils

def main():
    args = utils.parse_args()
    cfg = utils.parse_config(args)
    log = utils.get_logger(cfg.debug)

    metricsthread = nudnik.metrics.Metrics(cfg)
    metricsthread.start()

    if cfg.server:
        log.debug('Running Nudnik in server mode')
        server = nudnik.server.ParseService(cfg, metricsthread)
        server.start_server()
    else:
        log.debug('Running Nudnik in client mode')
        streams = list()
        log.debug('Starting {} streams'.format(cfg.streams))
        for i in range(1, cfg.streams + 1):
            stream = nudnik.client.Stream(cfg, i, metricsthread)
            streams.append(stream)
            stream.start()

        while len(streams) > 0:
            for index, stream in enumerate(streams):
                try:
                    if stream.gtfo:
                        streams.pop(index)
                    else:
                        stream.join(0.25)
                except KeyboardInterrupt:
                    for stream in streams:
                        stream.exit()
                        streams.pop(index)

    metricsthread.exit()
    log.debug('You are the weakest link, goodbye!'.format(''))
    return 1

if __name__ == "__main__":
    sys.exit(main())

