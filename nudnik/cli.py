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

import nudnik.stats
import nudnik.server
import nudnik.client
import nudnik.utils as utils

if (sys.version_info >= (3, 0)):
    import nudnik.ruok3 as ruok
else:
    import nudnik.ruok2 as ruok

def main():
    args = utils.parse_args()
    cfg = utils.parse_config(args)
    log = utils.get_logger(cfg.debug)

    if cfg.ruok is True:
        ruokthread = ruok.Ruok(cfg)
        ruokthread.daemon = True
        ruokthread.start()

    statsthread = nudnik.stats.Stats(cfg)
    statsthread.daemon = True
    statsthread.start()

    if cfg.server:
        log.debug('Running Nudnik in server mode')
        server = nudnik.server.ParseService(cfg, statsthread)
        server.start_server()

    else:
        log.debug('Running Nudnik in client mode')
        log.debug('Starting {} streams'.format(cfg.streams))
        streams = list()
        for i in range(0, cfg.streams):
            try:
                stream_id = cfg.initial_stream_index + i
                stream = nudnik.client.Stream(cfg, stream_id, statsthread)
                streams.append(stream)
                stream.start()
            except Exception as e:
                log.fatal('Fatal error during stream initialization: {}'.format(e))

        try:
            while len(streams) > 0:
                for index, stream in enumerate(streams):
                    if stream.gtfo or not stream.is_alive():
                        streams.pop(index)
                    else:
                        stream.join(0.25)
        except KeyboardInterrupt:
            for s in streams:
                s.exit()

    log.debug('You are the weakest link, goodbye!'.format(''))
    return 1

if __name__ == "__main__":
    sys.exit(main())

