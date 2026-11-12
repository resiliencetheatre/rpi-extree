import pygmc
import os
import sys
import time

#
# Configuration
#
FIFO_PATH = "/tmp/msgincoming"    # For Meshtastic/alerts
STATUS_FIFO = "/tmp/statusin"     # For Web UI status updates

HIGH_THRESHOLD = 50               # Trigger/repeat alarms at or above this CPM
CLEAR_THRESHOLD = 45              # Send "back to normal" at or below this CPM (must be < HIGH_THRESHOLD)
SAMPLE_PERIOD_SEC = 60            # Sensor read + WebUI update period
ALARM_REPEAT_EVERY_SEC = 180      # How often to re-send alarm while exceeded

#
# Helper function to send messages to FIFO
#
def send_fifo_message(message, fifo_path=FIFO_PATH):
    """Write a string message to FIFO (creates it if missing)."""
    try:
        if not os.path.exists(fifo_path):
            os.mkfifo(fifo_path)
        with open(fifo_path, "w") as fifo:
            fifo.write(message + "\n")
            fifo.flush()
    except Exception as e:
        print(f"FIFO write error ({fifo_path}): {e}")
        sys.stdout.flush()

def write_status(message, fifo_path=STATUS_FIFO):
    """Write a status line to the Web UI FIFO."""
    try:
        with open(fifo_path, "w") as fifo:
            fifo.write(message + "\n")
            fifo.flush()
    except Exception as e:
        print(f"Error writing to {fifo_path}: {e}")
        sys.stdout.flush()


#
# Startup delay
#
time.sleep(5)


#
# Connect radiation sensor
#
gc = pygmc.connect('/dev/radsensor')
ver = gc.get_version()
serial = gc.get_serial()
print(f"Connected to GMC device version {ver}, serial {serial}")
sys.stdout.flush()

# Sanity check for thresholds
if CLEAR_THRESHOLD >= HIGH_THRESHOLD:
    print(f"WARNING: CLEAR_THRESHOLD ({CLEAR_THRESHOLD}) should be < HIGH_THRESHOLD ({HIGH_THRESHOLD}).")
    sys.stdout.flush()

#
# Main loop with hysteresis + repeating alarms while exceeded
#
alarm_active = False
last_alarm_sent_ts = None  # monotonic timestamp of last alarm send

try:
    while True:
        cpm = gc.get_cpm()
        now = time.monotonic()
        print(f"Measured CPM: {cpm}")
        sys.stdout.flush()

        # Always send the periodic update to Web UI
        write_status(f"uilog,Radiation: {cpm} CPM")

        # Threshold logic
        if cpm >= HIGH_THRESHOLD:
            # Entering alarm state
            if not alarm_active:
                alarm_active = True
                last_alarm_sent_ts = now
                send_fifo_message(f"ALARM|Radiation high! {cpm} CPM (>= {HIGH_THRESHOLD})")
            else:
                # Already in alarm: send repeats every ALARM_REPEAT_EVERY_SEC
                if last_alarm_sent_ts is None or (now - last_alarm_sent_ts) >= ALARM_REPEAT_EVERY_SEC:
                    last_alarm_sent_ts = now
                    send_fifo_message(f"ALARM|Radiation still high: {cpm} CPM (>= {HIGH_THRESHOLD})")

        elif alarm_active and cpm <= CLEAR_THRESHOLD:
            # Clear alarm only once when safely below the clear threshold
            alarm_active = False
            last_alarm_sent_ts = None
            send_fifo_message(f"RESOLVED|Radiation back to normal: {cpm} CPM (<= {CLEAR_THRESHOLD})")

        # If CPM is in the hysteresis band (CLEAR < CPM < HIGH):
        # - Remain in current state
        # - Do not send repeating alarms unless CPM >= HIGH again

        time.sleep(SAMPLE_PERIOD_SEC)

except Exception as e:
    print(f"Exception caught: {e}")
    sys.stdout.flush()
    os._exit(0)
