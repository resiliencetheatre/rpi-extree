#!/bin/sh
dest_name="$1"
dest_addr="$2"
alarm_flag="$3"
latency_avg="$4"
loss_avg="$5"

echo "Dest: $1 Address: $2 Alarm flag: $3 Latency:$4 Loss: $5"

if [ "$alarm_flag" -eq 1 ]
then
        # alarm set
	# my_alarm_cmd "$dest_addr" "$latency_avg" "$loss_avg"
        # systemctl stop otp-tunnel-client
	echo "alarm set: $alarm_flag"
fi

if [ "$alarm_flag" -eq 0 ]
then
        # alarm clear
	# my_clear_cmd "$dest_addr" "$latency_avg" "$loss_avg"
        # systemctl start otp-tunnel-client
	echo "alarm cleared: $alarm_flag"
fi
