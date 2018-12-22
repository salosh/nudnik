Nudnik
======

Goals
-----

Allow easy testing of load-balancing and failures in gRPC and REST based service-mesh

Features
--------

 - Rate limiting
 - Fake IO load from either client or server side
 - Export timing metrics to a file or InfluxDB with any custom formatting
 - 

Quick Start
--------------------

 * Install Nudnik:
```sh
# Install package
pip install nudnik
```

 * Run example Server:
```shell
nudnik --server
```

 * Run a client that identifies itself as `barbaz`, fork to `2` threads, each sending `5` gRPC messages every `3` seconds.
```shell
nudnik --name barbaz --streams 2 --interval 3 --rate 5
```

Docker - Quick Start
--------------------

* Running on your local/remote docker daemon using docker-compose:
  `docker-compose up`

Under The Hood
--------------
The server binds to the host:port that were specified, and listens to incoming gRPC messages.
Every message consists of several fields:
 - name: The name of the client, arbitrary string
 - stream_id: The stream id, the streams are numbered from `0` to whatever was configureed via the `streams` arg.
 - message_id: At every `interval`, the client sends `rate` messages, this id is an autoincrement index for that message.
 - ctime: The timestamp at which the request was created
 - rtime: The timestamp at which the request was retransmitted (0 if not applicapble)
 - rcount: The amount of times this message was retransmitted (0 if not applicapble)
 - meta: Just another string field that does nothing, you may send additional arbitrary data to increase message size or specify `random` to generate random data with every request
 - load: This field may be repeated several times, it instructs the server to create fake load of some sort before replying.
 
 Upon recieveing a message, the server will:
  - parse the `load` field
  - perform the required load
  - print a log message using the configured `out_format`
  - reply an `OK` to the client, also add the field `ptime`, which represents the time at which the request was parsed at the server,
    this allows the client to calculate exact RTT, even if NTP is not synchronized.
 
Local Development
-----------------
As a rule of thumb wed'e recommend using virtualenv.
Requirement are Python 3.7 + requirements.txt file

 * Clone and initialize Nudnik:
```sh
# Install python requirements
pip install grpcio grpcio-tools requests-unixsocket

# Clone and configure the repository
git clone https://github.com/salosh/nudnik.git
git config --global push.default matching
git config --global user.name "Your Name"
git config --global user.email your.email@salosh.org

# "Compile" the entity protobuf
cd nudnik
python -m grpc_tools.protoc --proto_path=./nudnik/ --python_out=./nudnik/ --grpc_python_out=./nudnik/ ./entity.proto
```

Configure
--------

[Configuration](/nudnik/docs/configuration.md) documentation

[Formatting](/nudnik/docs/formatting.md) documentation

## Via `Nudnik` Command line args:
```sh
nudnik -h
usage: nudnik [-h] [--config-file CONFIG_FILE] [--host HOST] [--port PORT]
              [--server] [--name NAME]
              [--name-mismatch-error {prefix,suffix,exact}] [--meta META]
              [--workers WORKERS] [--streams STREAMS]
              [--initial-stream-index INITIAL_STREAM_INDEX]
              [--interval INTERVAL] [--rate RATE] [--count COUNT]
              [--chaos CHAOS] [--load load_type load_value]
              [--retry-count RETRY_COUNT] [--fail-ratio FAIL_RATIO] [--ruok]
              [--metrics {stdout,file,influxdb,prometheus}]
              [--stats {stdout,file,influxdb,prometheus}] [--extra EXTRA]
              [--debug] [--verbose] [--version]

Nudnik - gRPC load tester

optional arguments:
  -h, --help            show this help message and exit
  --config-file CONFIG_FILE, -f CONFIG_FILE
                        Path to YAML config file
  --host HOST, -H HOST  host
  --port PORT, -p PORT  port
  --server, -S          Operation mode (default: client)
  --name NAME, -n NAME  Parser name
  --name-mismatch-error {prefix,suffix,exact}
                        Fail request on name mismatch (default: None)
  --meta META, -M META  Send this extra data with every request
  --workers WORKERS, -w WORKERS
                        Number of workers (Default: Count of CPU cores)
  --streams STREAMS, -s STREAMS
                        Number of streams (Default: 1)
  --initial-stream-index INITIAL_STREAM_INDEX
                        Calculate stream ID from this initial index (Default:
                        0)
  --interval INTERVAL, -i INTERVAL
                        Number of seconds per stream message cycle (Default:
                        1)
  --rate RATE, -r RATE  Number of messages per interval (Default: 10)
  --count COUNT, -C COUNT
                        Count of total messages that should be sent (Default:
                        0 == unlimited)
  --chaos CHAOS, -c CHAOS
                        Compute statistical process level random crashes [0,
                        3600/interval] (Default: 0)
  --load load_type load_value, -l load_type load_value
                        Add artificial load [rtt, rttr, cpu, mem, cmd, fcmd]
                        (Default: None)
  --retry-count RETRY_COUNT
                        Number of times to re-send failed messages (Default:
                        -1, which means infinite times)
  --fail-ratio FAIL_RATIO
                        Percent of requests to intentionally fail (Default: 0)
  --ruok, -R            Enable "Are You OK?" HTTP/1.1 API (default: False)
  --metrics {stdout,file,influxdb,prometheus}, -m {stdout,file,influxdb,prometheus}
                        Enable metrics outputs (Default: None)
  --stats {stdout,file,influxdb,prometheus}, -t {stdout,file,influxdb,prometheus}
                        Enable stats outputs (Default: None)
  --extra EXTRA, -e EXTRA
                        Extra args (Default: None)
  --debug, -d           Debug mode (default: False)
  --verbose, -v         Verbose mode, specify multiple times for extra
                        verbosity (default: None)
  --version, -V         Display Nudnik version

2018 (C) Salo Shp <https://github.com/salosh/nudnik.git>
```

## Via config file:
```sh  
nano ./config.yml     
```

# Getting started
Please refer to our [examples repository](https://github.com/salosh/nudnik-examples) for multiple guides and usage examples

* * *
Visit our website at https://salosh.org
