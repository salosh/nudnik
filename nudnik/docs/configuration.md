Nudnik configuration
====================

Variables
-------------------

variable name | default | description
-------- | ------- | -----------
config_file | None | Specify a profile configuration file path
protocol | grpc | Specifies the message protocol, use 'http' for REST probes, available options are {'grpc', 'etcd', 'http'}
host | 127.0.0.1 | In server mode, controls the ip that should be binded, in client mode, specifies the server hostname or ip you wish to connect
port | 5410 | In server mode, controls the port that should be binded, in client mode, specifies the server port you wish to connect
path | / | In client mode, specifies the path of a REST probe request
method | GET | In client mode, specifies the method of a REST probe request
headers | [['Content-type', 'application/json']] | In client mode, specifies the headers of a REST probe request
request_format | {{"request": "ping", "timestamp": "{ctime}" }} | In client mode, specifies the body formatting of a REST probe request
response_format | {{"status": 200, "response": "pong", "timestamp": "{ctime}" }} | WIP
dns_ttl | 10 | Number of seconds before forcing "host" name lookup
server | False | If specified, initiate in `server` mode, otherwise default to `client` mode
name | NAME | In server mode, used for reporting purposes and rejecting messages if `name_mismatch_error` is specified. In client mode, used for reporting purposes and for tagging outgoing messages using the `name` field.
name_mismatch_error | None | Specifies incoming messages *rejection_by* filter for server mode, avilable values are {`prefix`, `suffix`, `exact`}
meta | None | Specifies a string that should be sent with every request/response. if the first char is a '@' - try to read the file and send its contents, for example *@/root/metafile.txt* or *@random*
meta_size | 4194304 | Specifies the maximum size of `meta` that should be sent, the current default is the current maximum gRPC limitation
workers | Count of CPU cores on this node / container | Specifies the number of workers that should be forked to handle incoming / outgoing messages
streams | 1 | On Client mode, specifies the number of streams that should send messages, in server mode used for `chaos` calculations and reporting purposes
initial_stream_index | 0 | In client mode, specifies the initial `stream_id` number, this value will be incremented by 1 for any additional stream 
interval | 1 | In client mode, specifies the number of seconds for a message generation cycle, in server mode used for `chaos` calculations and reporting purposes
rate | 1 | In client mode, specifies the numebr of messages that should be generated on every message generation cycle, in server mode used for `chaos` calculations and reporting purposes
timeout | 1 | Maximum number of seconds before failing a request
count | 0 | Specifies the number of messages that should be handeled before exiting, the default 0 value means unlimited messages
chaos | 0 | Specifies a statistical number of times per hour that this node should fail and exit, In client mode checked on every `interval`, in server mode checked with every incoming message
load | None | Specifies an artificial load that should be performed with every incoming / outgoing message, avilable values are {`rtt`, `rttr`, `cpu`, `mem`, `bcmd`, `fcmd`}
retry_count | -1 | In client mode, specifies the number of times that a failed message should be re-sent. default value of `-1` means infinite retries
fail_ratio | 0 | Specifies the percent of messages that should be marked as failed
ruok | False | Enables *Are you OK?* mode, using the configured `ruok_port` and `ruok_path`.
ruok_host | 127.0.0.1 | Specifies the local ip address that should be binded for `ruok` HTTP requests
ruok_port | 5310 | Specifies the port that should be binded for `ruok` HTTP requests
ruok_path | /ruok | Specifies the path that should return a `200 OK` response for the `ruok` backend.
ruok_headers | [['Content-type', 'application/json']] | Specifies the headers that should be returned with every RUOK request
ruok_response_format | '{{"status": 200, "timestamp": "{date}" }}' | Specifies the body format that should be returned with every RUOK request
metrics | None | Enables metrics backend, available modes are {`stdout`, `file`, `influxdb`, `prometheus`}
metrics_interval | 1 | Specifies `metrics` backend cycle-length in seconds
metrics_file_path | nudnikmetrics.out | Path to a `metrics` file backend, if enabled
metrics_format_stdout | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
metrics_format_file | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
metrics_format_influxdb | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
metrics_format_prometheus | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
stats | None | Enables statistics backend, available modes are {`stdout`, `file`, `influxdb`, `prometheus`}
stats_interval | 1 | Specifies `stats` backend cycle-length in seconds
stats_file_path | nudnikstats.out | Path to a `stats` file backend, if enabled
stats_format_stdout | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
stats_format_retransmit_stdout | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
stats_format_file | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
stats_format_retransmit_file | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
stats_format_influxdb | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
stats_format_retransmit_influxdb | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
stats_format_prometheus | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
stats_format_retransmit_prometheus | See [Formatting](/nudnik/docs/formatting.md) documentation | See [Formatting](/nudnik/docs/formatting.md) documentation
influxdb_socket_path | /var/run/influxdb/influxdb.sock | Specifies path to an InfluxDB socket for both `stats` and `metrics` backends if enabled 
influxdb_protocol | http+unix | Specifies protocol to InfluxDB connection for both `stats` and `metrics` backends if enabled
influxdb_host | 127.0.0.1 | Specifies host of InfluxDB connection for both `stats` and `metrics` backends (if enabled)
influxdb_port | 8086 | Specifies port of InfluxDB connection for both `stats` and `metrics` backends (if enabled)
influxdb_database_prefix | nudnik | Specifies database name prefix for InfluxDB backend, the final name would be concatenated with `stats` or `metrics` if enabled
prometheus_protocol | http | Specifies protocol to Prometheus pushgateway connection for both `stats` and `metrics` backends if enabled
prometheus_host | 127.0.0.1 | Specifies host to Prometheus pushgateway connection for both `stats` and `metrics` backends if enabled
prometheus_port | 9091 | Specifies port to Prometheus pushgateway connection for both `stats` and `metrics` backends if enabled
unset_http_proxy | True | Unset HTTP proxy related environment variables for this process, prevents issues with most organizational proxies, which do not handle gRPC calls correctly
debug | False | Decreases log level to debug.
verbose | 0 | Enables extra verbosity, via command line specify multiple time (<6) for extra verbosity (e.g. `nudnik -vvvvvv`), via config file or environment variable specify a number (e.g. `export NUDNIK_VERBOSE=6`)

