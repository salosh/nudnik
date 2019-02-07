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
import threading

import nudnik.stats
import nudnik.metrics
import nudnik.grpc_server
import nudnik.client
import nudnik.load
import nudnik.utils as utils

if (sys.version_info >= (3, 0)):
    import nudnik.ruok3 as ruok
else:
    import nudnik.ruok2 as ruok

def main():
    args = utils.parse_args()
    cfg = utils.parse_config(args)
    log = utils.get_logger(cfg.debug)

    threads = list()

    if cfg.ruok is True:
        ruokthread = ruok.Ruok(cfg)
        threads.append(ruokthread)
        ruokthread.daemon = True
        ruokthread.start()

    if len(cfg.metrics) > 0:
        metricsthread = nudnik.metrics.Metrics(cfg)
        threads.append(metricsthread)
        metricsthread.daemon = True
        metricsthread.start()

    statsthread = nudnik.stats.Stats(cfg)
    threads.append(statsthread)
    statsthread.daemon = True
    statsthread.start()

    if cfg.server:
        log.debug('Running Nudnik in server mode')
        server = nudnik.grpc_server.ParseService(cfg, statsthread)
        server.start_server()

    else:
        log.debug('Running Nudnik in client mode')
        log.debug('Starting {} streams'.format(cfg.streams))
        for i in range(0, cfg.streams):
            try:
                stream_id = cfg.initial_stream_index + i
                stream = nudnik.client.Stream(cfg, stream_id, statsthread)
                threads.append(stream)
                stream.start()
            except Exception as e:
                log.fatal('Fatal error during stream initialization: {}'.format(e))

        if cfg.streams == 0 and len(cfg.load_list) > 0:
            load_thread = nudnik.load.Load(cfg)
            load_thread.daemon = True
            threads.append(load_thread)
            load_thread.start()

        try:
            while len(threads) > 0:
                for index, stream in enumerate(threads):
                    if stream.gtfo or not stream.is_alive():
                        threads.pop(index)
                    else:
                        stream.join(0.25)
        except KeyboardInterrupt:
            for s in threads:
                s.exit()

    log.debug('You are the weakest link, goodbye!'.format(''))
    return 1

if __name__ == "__main__":
    sys.exit(main())

