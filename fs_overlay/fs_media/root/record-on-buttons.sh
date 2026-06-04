#!/bin/sh
#
# record-on-buttons.sh
#
# KEY_DOWN pressed -> start Opus recording, RED LED on
# KEY_UP pressed   -> stop recording, finalize file, RED LED off
#
# Filename format:
#   DDMMYY-HHMMSS_LENGTH_IN_SECONDS.opus
#
# Example:
#   040626-105042_6.opus
#
# Usage:
#   ./record-on-buttons.sh [/dev/input/event0] [/root/recordings] [gpiochip0]
#
# Optional:
#   ALSA_DEVICE=plughw:0,0 ./record-on-buttons.sh
#

DEVICE="${1:-/dev/input/event0}"
OUTDIR="${2:-/root/recordings}"
GPIOCHIP="${3:-gpiochip0}"

ALSA_DEVICE="${ALSA_DEVICE:-default}"

# Codec Zero LEDs
GREEN_GPIO=23
RED_GPIO=24

GST_PID=""
EVTEST_PID=""
REC_TMP=""
REC_START_EPOCH=""
REC_START_NAME=""

if [ ! -e "$DEVICE" ]; then
    echo "Device not found: $DEVICE" >&2
    exit 1
fi

if ! command -v evtest >/dev/null 2>&1; then
    echo "evtest not found in PATH" >&2
    exit 1
fi

if ! command -v gpioset >/dev/null 2>&1; then
    echo "gpioset not found in PATH" >&2
    exit 1
fi

if ! command -v gst-launch-1.0 >/dev/null 2>&1; then
    echo "gst-launch-1.0 not found in PATH" >&2
    exit 1
fi

mkdir -p "$OUTDIR"

led_set()
{
    gpio="$1"
    value="$2"

    gpioset "$GPIOCHIP" "$gpio=$value"
}

green_on()  { led_set "$GREEN_GPIO" 1; }
green_off() { led_set "$GREEN_GPIO" 0; }
red_on()    { led_set "$RED_GPIO" 1; }
red_off()   { led_set "$RED_GPIO" 0; }

start_recording()
{
    if [ -n "$GST_PID" ] && kill -0 "$GST_PID" 2>/dev/null; then
        echo "Already recording, ignoring KEY_DOWN"
        return
    fi

    REC_START_EPOCH="$(date +%s)"
    REC_START_NAME="$(date +%d%m%y-%H%M%S)"
    REC_TMP="$OUTDIR/.rec-${REC_START_NAME}.tmp.opus"

    echo "Starting recording: $REC_TMP"

    red_on

    gst-launch-1.0 -e \
        alsasrc device="$ALSA_DEVICE" \
        ! audio/x-raw,format=S16LE,rate=48000,channels=1 \
        ! audioconvert \
        ! audioresample \
        ! opusenc bitrate=24000 audio-type=voice frame-size=20 \
        ! oggmux \
        ! filesink location="$REC_TMP" &

    GST_PID="$!"
}

stop_recording()
{
    if [ -z "$GST_PID" ]; then
        echo "Not recording, ignoring KEY_UP"
        red_off
        return
    fi

    if kill -0 "$GST_PID" 2>/dev/null; then
        echo "Stopping recording..."
        kill -INT "$GST_PID" 2>/dev/null || true
        wait "$GST_PID" 2>/dev/null || true
    fi

    REC_END_EPOCH="$(date +%s)"
    LEN="$((REC_END_EPOCH - REC_START_EPOCH))"

    if [ "$LEN" -lt 0 ]; then
        LEN=0
    fi

    FINAL="$OUTDIR/${REC_START_NAME}_${LEN}.opus"

    if [ -f "$REC_TMP" ]; then
        mv "$REC_TMP" "$FINAL"
        echo "Recording complete: $FINAL"
    else
        echo "Recording stopped, but temp file missing: $REC_TMP"
    fi

    GST_PID=""
    REC_TMP=""
    REC_START_EPOCH=""
    REC_START_NAME=""

    red_off
}

cleanup()
{
    echo "Cleaning up..."

    if [ -n "$GST_PID" ] && kill -0 "$GST_PID" 2>/dev/null; then
        stop_recording
    fi

    if [ -n "$EVTEST_PID" ] && kill -0 "$EVTEST_PID" 2>/dev/null; then
        kill "$EVTEST_PID" 2>/dev/null || true
    fi

    red_off
    green_off

    rm -f "$FIFO"

    exit 0
}

FIFO="/tmp/record-on-buttons.$$"

trap cleanup INT TERM EXIT

rm -f "$FIFO"
mkfifo "$FIFO" || exit 1

# Start with LEDs off.
red_off
green_off

echo "Listening on: $DEVICE"
echo "Output dir:   $OUTDIR"
echo "ALSA device:  $ALSA_DEVICE"
echo "GPIO chip:    $GPIOCHIP"
echo
echo "KEY_DOWN starts recording and turns RED on"
echo "KEY_UP stops recording and turns RED off"
echo

if command -v stdbuf >/dev/null 2>&1; then
    sh -c "stdbuf -oL evtest \"$DEVICE\" > \"$FIFO\"" &
else
    sh -c "evtest \"$DEVICE\" > \"$FIFO\"" &
fi

EVTEST_PID="$!"

while IFS= read -r line; do
    case "$line" in
        *"type 1 (EV_KEY),"*"code 108 (KEY_DOWN),"*)
            value="${line##*value }"

            case "$value" in
                1)
                    echo "KEY_DOWN pressed -> start recording"
                    start_recording
                    ;;
                0)
                    # Ignore release of KEY_DOWN.
                    ;;
                2)
                    # Ignore autorepeat.
                    ;;
            esac
            ;;

        *"type 1 (EV_KEY),"*"code 103 (KEY_UP),"*)
            value="${line##*value }"

            case "$value" in
                1)
                    echo "KEY_UP pressed -> stop recording"
                    stop_recording
                    ;;
                0)
                    # Ignore release of KEY_UP.
                    ;;
                2)
                    # Ignore autorepeat.
                    ;;
            esac
            ;;
    esac
done < "$FIFO"

cleanup
