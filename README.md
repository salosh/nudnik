Nudnik
======

Goals
-----

Allow easy testing of load-balancing and failures in gRPC and REST based service-mesh

Features
--------

 - Rate limiting
 - Fake IO load from either client or server side
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
  * `name-sid-idx=foobar` - The clients name flag (e.g. foobar), concateneted with the stream number and iteration index.
  * `2` - stream id (out of n streams)
  * `6` - the iteration-index of the stream
  * `mid=1` - message id (from 1 to `rate`)
  * `ts=2018-11-20 00:52:11.557882` - request timestamp
  * `delta=0:00:00.008537` - represents the server time when recieving the request minus the request creation time ~((rtt-load_time)/2). note that HW time differences between client and server might have critical impact on this calculation.


Under The Hood
--------------
The server binds to the host:port that were specified, and listens to incoming gRPC messages.
Every message consists of several fields:
 - name: The name of the client, arbitrary string
 - stream_id: The stream id, the streams are numbered from `0` to whatever was configureed via the `streams` arg.
 - message_id: At every `interval`, the client sends `rate` messages, this id is an autoincrement index for that message.
 - timestamp: The timestamp at which the request was created
 - meta: Just another string field that does nothing, you may send additional arbitrary data to increase message size
 - load: This field may be repeated several times, it instructs the server to create fake load of some sort before replying.
 
 Upon recieveing a message, the server will:
  - parse the `load` field
  - perform the required load
  - print a log message
  - reply an `OK` to the client
 
Local Development
-----------------
As a rule of thumb wed'e recommend using virtualenv.
Requirement are Python 3.7 + requirements.txt file

 * Clone and initialize Nudnik:
```sh
# Install python requirements
pip install grpcio grpcio-tools

# Clone and configure the repository
git clone https://github.com/salosh/nudnik.git
git config --global push.default matching
git config --global user.name "Your Name"
git config --global user.email your.email@salosh.org

# Clone and configure the repository            
cd nudnik
python -m grpc_tools.protoc --proto_path=. ./entity.proto --python_out=. --grpc_python_out=.
```

Configure
--------

## Via `Nudnik` Command line args:
```shell
python3 ./nudnik.py -h
usage: nudnik.py [-h] [--config-file CONFIG_FILE] [--host HOST] [--port PORT]
                 [--server] [--name NAME] [--meta META] [--streams STREAMS]
                 [--interval INTERVAL] [--rate RATE]
                 [--load load_type load_value] [--retry-count RETRY_COUNT]
                 [--fail-ratio FAIL_RATIO]

Nudnik - gRPC load tester

optional arguments:
  -h, --help            show this help message and exit
  --config-file CONFIG_FILE
                        Path to YAML config file
  --host HOST           host
  --port PORT           port
  --server              Operation mode (default: client)
  --name NAME           Parser name
  --meta META           Send this extra data with every request
  --streams STREAMS     Number of streams (Default: 1)
  --interval INTERVAL   Number of seconds per stream message cycle (Default:
                        1)
  --rate RATE           Number of messages per interval (Default: 10)
  --load load_type load_value
                        Add artificial load [rtt, rttr, cpu, mem] (Default:
                        None)
  --retry-count RETRY_COUNT
                        Number of times to re-send failed messages (Default:
                        -1)
  --fail-ratio FAIL_RATIO
                        Percent of requests to intentionally fail (Default: 0)

2018 (C) Salo Shp <SaloShp@Gmail.Com> <https://github.com/salosh/nudnik.git>
```

## Via config file:
```shell  
nano ./config.yml     
```

 * Run example Server:
```shell
./nudnik.py --server
```

 * Run example Server that fails `14%` of all incoming requests:
```shell
./nudnik.py --server --fail-ratio 14
```

 * Run a client that identifies itself as `foobar`, fork to `20` threads, each sending `5` gRPC messages every `3` seconds.
```shell
./nudnik.py --name foobar --streams 20 --interval 3 --rate 5
```


 * Run a client that identifies itself as `FakeFixedLatnecy`, fork to `3` threads, each sending `1` gRPC messages every `10` seconds, and also make the server wait for `0.01` seconds before replying.
```shell
./nudnik.py --name FakeFixedLatnecy --streams 3 --interval 10 --rate 1 --load rtt 0.01
```

 * Run a client that identifies itself as `FakeRandomLatnecy`, fork to `3` threads, each sending `1` gRPC messages every `10` seconds, and also make the server wait for a random value between `0` and `0.5` seconds before replying.
```shell
./nudnik.py --name FakeRandomLatnecy --streams 3 --interval 10 --rate 1 --load rttr 0.5
```


 * Run a client that identifies itself as `FakeLatnecyAndCPU`, fork to `1` threads, each sending `100` gRPC messages every `1` seconds, and also make the server wait for `2ms` and fake-load the CPU for `0.5` seconds before replying.
```shell
./nudnik.py --name FakeLatnecyAndCPU --streams 1 --interval 1 --rate 100 --load rtt 0.002 --load cpu 0.5
```


* * *
Visit our website at https://salosh.org
