Nudnik
======

Goals
-----

Allow easy testing of load-balancing and failures in gRPC and REST based service-mesh

Features
--------

 - Rate limiting
 -

Docker - Quick Start
--------------------

* Running on your local/remote docker daemon using docker-compose:
  `docker-compose up`
  should yield an example scenario with output similar to the following:

  ```sh
  name-sid-idx=foobar-2-6,mid=1,ts=2018-11-20 00:52:11.557882,delta=0:00:00.008537
  name-sid-idx=foobar-3-6,mid=1,ts=2018-11-20 00:52:11.559378,delta=0:00:00.007551
  name-sid-idx=foobar-1-6,mid=2,ts=2018-11-20 00:52:11.564696,delta=0:00:00.002975
  name-sid-idx=foobar-1-6,mid=3,ts=2018-11-20 00:52:11.568250,delta=0:00:00.001183
  name-sid-idx=foobar-2-6,mid=2,ts=2018-11-20 00:52:11.568753,delta=0:00:00.002804
  name-sid-idx=foobar-3-6,mid=2,ts=2018-11-20 00:52:11.569651,delta=0:00:00.002318
  ```

  The log format consists of the following structure (might change ...):
  ```sh
  name-sid-idx=foobar-2-6,mid=1,ts=2018-11-20 00:52:11.557882,delta=0:00:00.008537
  ```
  * `name-sid-idx=foobar` - Usually the clients name flag (e.g. foobar)
  * `2` - stream id (out of n streams)
  * `6` - the iteration number of the stream
  * `mid=1` - message id
  * `ts=2018-11-20 00:52:11.557882` - request timestamp
  * `delta=0:00:00.008537` - represents roundtrip time divided by 2

`Nudnik` Command line args
------------------------
```
python3 ./nudnik.py -h
usage: nudnik.py [-h] [--config-file CONFIG_FILE] [--host HOST] [--port PORT]
                 [--server] [--name NAME] [--streams STREAMS]
                 [--interval INTERVAL] [--rate RATE]
                 [--load load_type load_value]

Nudnik - gRPC load tester

optional arguments:
  -h, --help            show this help message and exit
  --config-file CONFIG_FILE
                        Path to YAML config file
  --host HOST           host
  --port PORT           port
  --server              Operation mode (default: client)
  --name NAME           Parser name
  --streams STREAMS     Number of streams (Default: 1)
  --interval INTERVAL   Number of seconds per stream message cycle (Default:
                        1)
  --rate RATE           Number of messages per interval (Default: 10)
  --load load_type load_value
                        Add artificial load [rtt, rttr, cpu, mem] (Default:
                        None)

2018 (C) Salo Shp <SaloShp@Gmail.Com> <https://github.com/salosh/nudnik.git>
```


Local Development
-----------------
As a rule of thumb wed'e recommend using virtualenv.
Requirement are Python 3.7 + requirements.txt file



 * Clone and initialize Nudnik:
```sh
pip install grpcio grpcio-tools                          
git clone https://github.com/salosh/nudnik.git
git config --global push.default matching
git config --global user.name "Your Name"
git config --global user.email your.email@salosh.org
cd nudnik
python -m grpc_tools.protoc --proto_path=. ./entity.proto --python_out=. --grpc_python_out=.
```

 * Configure:
Via flags:
```shell
./nudnik.py -h
```
Via config file:
```shell  
nano ./config.yml     
```

 * Run example Server:
```shell
./nudnik.py --server
```

 * Run example Client:
```shell
./nudnik.py --name foobar --streams 20 --interval 3 --rate 5
```
In this example there would be `20` streams triggering `5` gRPC messages every `3` seconds.



* * *
Visit our website at https://salosh.org
