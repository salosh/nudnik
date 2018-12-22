Nudnik configuration
====================

Indented fields must be concatenated with ther parents,
for example if you wish to output the `stream_id` and `rtt` values to the `stdout` backend, 
configure the `stats_format_stdout` to `"Caclculated RTT '{rtt}' for stream ID '{req.stream_id}'"`

> Warning:
> The fields for `stats` may not be all available,
> their availability is determined by the configuration you provided to `nudnik` at run-time,
> `rtime` for example, is only calculated for failed messages

Formatting the `stats` backend
--------------------------------
* timestamp
* timestamp_str
* req
  * name
  * stream_id
  * worker_id
  * sequence_id
  * message_id
  * ctime
  * stime
  * rtime
  * rcount
* res
  * status_code
  * ctime
  * stime
* cdelta
* rdelta
* sdelta
* pdelta
* bdelta
* rtt

> Warning:
> The fields for `metrics` may not be all available,
> their availability is determined by the configuration you provided for the `metrics_format_*` variables
> and also by your `psutil` version

Formatting the `metrics` backend
--------------------------------
* timestamp
* node
  * sysname
  * major
  * minor
  * dist
  * nodename
  * version_0
  * releaselevel
  * machine
  * micro
  * version
  * platform
  * release
  * serial
  * distribution
* cpu
  * count
  * usage
  * idle
  * idle_percent
  * guest_nice
  * guest_nice_percent
  * guest
  * guest_percent
  * softirq
  * softirq_percent
  * system
  * system_percent
  * user
  * user_percent
  * irq
  * irq_percent
  * nice
  * nice_percent
  * iowait
  * iowait_percent
  * steal
  * steal_percent
  * freq_current
  * freq_min
  * freq_max
  * stats_soft_interrupts
  * stats_interrupts
  * stats_ctx_switches
  * stats_syscalls
* mem
  * buffers
  * shared
  * free
  * total
  * inactive
  * available
  * active
  * used
  * slab
  * percent
  * cached
  * swap_used
  * swap_free
  * swap_total
  * swap_sin
  * swap_sout
  * swap_percent
* net
  * packets_sent
  * packets_recv
  * bytes_sent
  * bytes_recv
  * dropin
  * dropout
  * errin
  * errout

