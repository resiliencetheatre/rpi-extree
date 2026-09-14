#!/usr/bin/env python3
import time
import subprocess
import gpiod

GPIOCHIP = "/dev/gpiochip0"
BUTTON = 17  # Whisplay button: BCM GPIO17 / physical pin 11

PTT_SOCKET = "/tmp/udpptt.sock"

CMD_DOWN = [
    "ptt_helper",
    "--socket", PTT_SOCKET,
    "--ptt_down",
]

CMD_UP = [
    "ptt_helper",
    "--socket", PTT_SOCKET,
    "--ptt_up",
]

POLL_INTERVAL = 0.01      # 10 ms
DEBOUNCE_TIME = 0.05      # 50 ms


_GPIOD_V2 = hasattr(gpiod, "LineSettings")

if _GPIOD_V2:
    from gpiod.line import Direction, Bias, Value


class GPIOInput:
    def __init__(self, chip, offset):
        self.offset = offset
        self.v2_req = None
        self.v1_line = None

        if _GPIOD_V2:
            settings = gpiod.LineSettings(
                direction=Direction.INPUT,
                bias=Bias.DISABLED,
            )
            self.v2_req = chip.request_lines(
                consumer="whisplay-ptt-button",
                config={offset: settings},
            )
        else:
            self.v1_line = chip.get_line(offset)
            try:
                self.v1_line.request(
                    consumer="whisplay-ptt-button",
                    type=gpiod.LINE_REQ_DIR_IN,
                    flags=gpiod.LINE_REQ_FLAG_BIAS_DISABLE,
                )
            except Exception:
                self.v1_line.request(
                    consumer="whisplay-ptt-button",
                    type=gpiod.LINE_REQ_DIR_IN,
                )

    def get(self):
        if self.v2_req is not None:
            v = self.v2_req.get_value(self.offset)
            return 1 if v == Value.ACTIVE else 0

        return self.v1_line.get_value()

    def release(self):
        try:
            if self.v2_req is not None:
                self.v2_req.release()
            elif self.v1_line is not None:
                self.v1_line.release()
        except Exception:
            pass


def run_cmd(cmd):
    try:
        subprocess.run(
            cmd,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print("ERROR: command not found:", cmd[0])
    except Exception as e:
        print("ERROR running command:", e)


def wait_stable(button, wanted_state):
    start = time.monotonic()

    while time.monotonic() - start < DEBOUNCE_TIME:
        if button.get() != wanted_state:
            return False
        time.sleep(POLL_INTERVAL)

    return True


def main():
    chip = gpiod.Chip(GPIOCHIP)
    button = GPIOInput(chip, BUTTON)

    last_state = button.get()

    print("Whisplay PTT button watcher")
    print("GPIO17: released=0, pressed=1")

    try:
        while True:
            state = button.get()

            if state != last_state:
                if wait_stable(button, state):
                    last_state = state

                    if state == 1:
                        print("PTT down")
                        run_cmd(CMD_DOWN)
                    else:
                        print("PTT up")
                        run_cmd(CMD_UP)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        pass
    finally:
        # Safety: on exit, always release PTT.
        run_cmd(CMD_UP)

        button.release()
        try:
            chip.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
