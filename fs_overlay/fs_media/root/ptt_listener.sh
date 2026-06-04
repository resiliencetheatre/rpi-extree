#!/bin/sh
# Listens for KEY_UP / KEY_DOWN on evdev and controls Codec Zero LEDs.
#
# KEY_DOWN -> red LED
# KEY_UP   -> green LED
#
# Usage:
#   ./ptt-key-led-listener.sh [/dev/input/event0] [gpiochip0]

DEVICE="${1:-/dev/input/event0}"
GPIOCHIP="${2:-gpiochip0}"

GREEN_GPIO=23
RED_GPIO=24

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

cleanup()
{
    red_off
    green_off
    exit 0
}

trap cleanup INT TERM EXIT

# Start with LEDs off.
red_off
green_off

if command -v stdbuf >/dev/null 2>&1; then
    EVT_CMD="stdbuf -oL evtest \"$DEVICE\""
else
    EVT_CMD="evtest \"$DEVICE\""
fi

echo "Listening on $DEVICE"
echo "KEY_DOWN controls RED GPIO$RED_GPIO"
echo "KEY_UP controls GREEN GPIO$GREEN_GPIO"

sh -c "$EVT_CMD" | while IFS= read -r line; do
    case "$line" in
        *"type 1 (EV_KEY),"*"code 108 (KEY_DOWN),"*)
            value="${line##*value }"

            case "$value" in
                1)
                    echo "KEY_DOWN pressed -> RED on"
                    red_on
                    ;;
                0)
                    echo "KEY_DOWN released -> RED off"
                    red_off
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
                    echo "KEY_UP pressed -> GREEN on"
                    green_on
                    ;;
                0)
                    echo "KEY_UP released -> GREEN off"
                    green_off
                    ;;
                2)
                    # Ignore autorepeat.
                    ;;
            esac
            ;;
    esac
done
