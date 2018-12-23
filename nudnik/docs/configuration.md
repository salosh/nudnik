Nudnik configuration
====================

Variables
-------------------

variable name | default | description
-------- | ------- | -----------
config_file | None | Specify a profile configuration file path
host | 127.0.0.1 | On server mode, controls the ip that should be binded, on client mode, specifies the server hostname or ip you wish to connect
port | 5410 | On server mode, controls the port that should be binded, on client mode, specifies the server port you wish to connect
server | False | If specified, initiate in `server` mode, otherwise default to `client` mode
name | NAME | On server mode, used for reporting purposes and rejecting messages if `name_mismatch_error` is specified. On client mode, used for reporting purposes and for tagging outgoing messages using the `name` field. 
name_mismatch_error | None | Specifies incoming messages *rejection_by* filter for server mode, avilable values are {`prefix`, `suffix`, `exact`}
meta | None | Specifies a string that should be sent with every request/response. if the first char is a '@' - try to read the file and send its contents, for example *@/root/metafile.txt* or *@random*
meta_size | 4194304 | Specifies the maximum size of `meta` that should be sent, the current default is the current maximum gRPC limitation
workers | Count of CPU cores on this node / container | Specifies the number of workers that should be forked to handle incoming / outgoing messages
streams | 1 | On Client mode, specifies the number of streams that should send messages, on server mode used for `chaos` calculations and reporting purposes
initial_stream_index | 0 | On client mode, specifies the initial `stream_id` number, this value will be incremented by 1 for any additional stream 
interval | 1 | On client mode, specifies the number of seconds for a message generation cycle, on server mode used for `chaos` calculations and reporting purposes
rate | 1 | On client mode, specifies the numebr of messages that should be generated on every message generation cycle, on server mode used for `chaos` calculations and reporting purposes
count | 0 | Specifies the number of messages that should be handeled before exiting, the default 0 value means unlimited messages
chaos | 0 | Specifies a statistical number of times per hour that this node should fail and exit, On client mode checked on every `interval`, on server mode checked with every incoming message 
load | None | Specifies an artificial load that should be performed with every incoming / outgoing message, avilable values are {`rtt`, `rttr`, `cpu`, `mem`, `cmd`, `fcmd`}
retry_count | -1 | On client mode, specifies the number of times that a failed message should be re-sent. default value of `-1` means infinite retries
fail_ratio | 0 | Specifies the percent of messages that should be marked as failed
ruok | False | Enables *Are you OK?* mode, using the configured `ruok_port` and `ruok_path`.
ruok_port | 80 | Specifies the port that should be binded for `ruok` HTTP requests
ruok_path | /ruok | Specifies the path that should return a `200 OK` response for the `ruok` backend.
metrics | None | Enables metrics backend, available modes are {`stdout`, `file`, `influxdb`, `prometheus`}
metrics_interval | 1 | Specifies `metrics` backend cycle-length in seconds
metrics_file_path | nudnikmetrics.out | Path to a `metrics` file backend, if enabled
metrics_format_stdout | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
metrics_format_file | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
metrics_format_influxdb | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
metrics_format_prometheus | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
stats | None | Enables statistics backend, available modes are {`stdout`, `file`, `influxdb`, `prometheus`}
stats_interval | 1 | Specifies `stats` backend cycle-length in seconds
stats_file_path | nudnikstats.out | Path to a `stats` file backend, if enabled
stats_format_stdout | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
stats_format_retransmit_stdout | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
stats_format_file | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
stats_format_retransmit_file | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
stats_format_influxdb | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
stats_format_retransmit_influxdb | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
stats_format_prometheus | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
stats_format_retransmit_prometheus | See [Formatting](/docs/formatting.md) documentation | See [Formatting](/docs/formatting.md) documentation
influxdb_socket_path | /var/run/influxdb/influxdb.sock | Specifies path to an InfluxDB socket for both `stats` and `metrics` backends if enabled 
influxdb_protocol | http+unix | Specifies protocol to InfluxDB connection for both `stats` and `metrics` backends if enabled
influxdb_host | 127.0.0.1 | Specifies host:port to InfluxDB connection for both `stats` and `metrics` backends if enabled
influxdb_port | 8086 | Specifies host:port to InfluxDB connection for both `stats` and `metrics` backends if enabled
influxdb_database_prefix | nudnik | Specifies database name prefix for InfluxDB backend, the final name would be concatenated with `stats` or `metrics` if enabled
prometheus_protocol | http | Specifies protocol to Prometheus pushgateway connection for both `stats` and `metrics` backends if enabled
prometheus_host | 127.0.0.1 | Specifies host to Prometheus pushgateway connection for both `stats` and `metrics` backends if enabled
prometheus_port | 9091 | Specifies port to Prometheus pushgateway connection for both `stats` and `metrics` backends if enabled
debug | False | Decreases log level to debug.
verbose | 0 | Enables extra verbosity, via command line specify multiple time (<6) for extra verbosity (e.g. `nudnik -vvvvvv`), via config file or environment variable specify a number (e.g. `export NUDNIK_VERBOSE=6`)

