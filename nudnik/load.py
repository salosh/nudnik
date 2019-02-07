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

import nudnik
import nudnik.utils as utils

class Load(threading.Thread):
    def __init__(self, cfg):
        threading.Thread.__init__(self)
        self.gtfo = False
        self.event = threading.Event()

        self.cfg = cfg
        self.log = utils.get_logger(cfg.debug)
        self.name = '{}'.format(cfg.name)
        self.log.debug('Load thread {} initiated'.format(self.name))

    def run(self):
        self.log.debug('Load thread {} started'.format(self.name))


        while not self.gtfo:
            time_start = utils.time_ns()

            for load in self.cfg.load_list:
                utils.generate_load(self.log, load, self.cfg.meta)

            elapsed = utils.diff_seconds(time_start, utils.time_ns())
            if elapsed < self.cfg.interval:
                self.event.wait(timeout=(self.cfg.interval - elapsed))

    def exit(self):
        self.gtfo = 1
        self.event.set()

