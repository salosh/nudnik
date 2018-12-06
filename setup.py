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
from setuptools import setup

import setuptools

import re

def version():
    INITFILE="nudnik/__init__.py"
    initstring = open('nudnik/__init__.py', "rt").read()
    version = re.search(r"^__version__ = '(.*)'", initstring, re.M).group(1)
    return version

with open("README.md", "r") as f:
    long_description = f.read()

with open('requirements.txt') as f:
     install_reqs = f.read().splitlines()

setuptools.setup(
     name='nudnik',
     version=version(),
     url="https://github.com/salosh/nudnik.git",
     scripts=['nudnik/bin/nudnik'],
     author="Salo Shp",
     author_email="support@salosh.org",
     license='GPLv3',
     description="gRPC load-balancing testing tool",
     long_description=long_description,
     long_description_content_type="text/markdown",
     packages=setuptools.find_packages(),
     install_requires=install_reqs,
     classifiers=[
         "Environment :: Console",
         "Intended Audience :: System Administrators",
         "Programming Language :: Python",
         "Topic :: System :: Distributed Computing",
         "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
         "Natural Language :: English",
         "Operating System :: OS Independent",
     ],
     zip_safe=False,
)
