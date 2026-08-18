#!/usr/bin/env python3
import time
import datetime
import spidev
import gpiod

GPIOCHIP = "/dev/gpiochip0"

PIN_DC = 27
PIN_RST = 4
PIN_BL = 22      # active-low on Whisplay

SPI_BUS = 0
SPI_CS = 0
SPI_SPEED = 50_000_000

LCD_W = 240
LCD_H = 280
Y_OFFSET = 20

BLACK  = 0x0000
WHITE  = 0xFFFF
GREEN  = 0x07E0
YELLOW = 0xFFE0
BLUE   = 0x001F
RED    = 0xF800


# ---------- gpiod v1/v2 compatibility ----------

_GPIOD_V2 = hasattr(gpiod, "LineSettings")

if _GPIOD_V2:
    from gpiod.line import Direction, Value


class GPIOOut:
    def __init__(self, chip, offset, initial=0):
        self.offset = offset
        self.v2_req = None
        self.v1_line = None

        if _GPIOD_V2:
            settings = gpiod.LineSettings(
                direction=Direction.OUTPUT,
                output_value=Value.ACTIVE if initial else Value.INACTIVE,
            )
            self.v2_req = chip.request_lines(
                consumer="whisplay-clock",
                config={offset: settings},
            )
        else:
            self.v1_line = chip.get_line(offset)
            self.v1_line.request(
                consumer="whisplay-clock",
                type=gpiod.LINE_REQ_DIR_OUT,
                default_val=initial,
            )

    def set(self, value):
        value = 1 if value else 0
        if self.v2_req is not None:
            self.v2_req.set_value(
                self.offset,
                Value.ACTIVE if value else Value.INACTIVE,
            )
        else:
            self.v1_line.set_value(value)

    def release(self):
        try:
            if self.v2_req is not None:
                self.v2_req.release()
            elif self.v1_line is not None:
                self.v1_line.release()
        except Exception:
            pass


# ---------- 5x7 font ----------

FONT = {
    " ": [0x00,0x00,0x00,0x00,0x00],
    ":": [0x00,0x36,0x36,0x00,0x00],
    "-": [0x08,0x08,0x08,0x08,0x08],
    ".": [0x00,0x60,0x60,0x00,0x00],
    "/": [0x20,0x10,0x08,0x04,0x02],

    "0": [0x3E,0x51,0x49,0x45,0x3E],
    "1": [0x00,0x42,0x7F,0x40,0x00],
    "2": [0x42,0x61,0x51,0x49,0x46],
    "3": [0x21,0x41,0x45,0x4B,0x31],
    "4": [0x18,0x14,0x12,0x7F,0x10],
    "5": [0x27,0x45,0x45,0x45,0x39],
    "6": [0x3C,0x4A,0x49,0x49,0x30],
    "7": [0x01,0x71,0x09,0x05,0x03],
    "8": [0x36,0x49,0x49,0x49,0x36],
    "9": [0x06,0x49,0x49,0x29,0x1E],

    "A": [0x7E,0x11,0x11,0x11,0x7E],
    "B": [0x7F,0x49,0x49,0x49,0x36],
    "C": [0x3E,0x41,0x41,0x41,0x22],
    "D": [0x7F,0x41,0x41,0x22,0x1C],
    "E": [0x7F,0x49,0x49,0x49,0x41],
    "F": [0x7F,0x09,0x09,0x09,0x01],
    "G": [0x3E,0x41,0x49,0x49,0x7A],
    "H": [0x7F,0x08,0x08,0x08,0x7F],
    "I": [0x00,0x41,0x7F,0x41,0x00],
    "J": [0x20,0x40,0x41,0x3F,0x01],
    "K": [0x7F,0x08,0x14,0x22,0x41],
    "L": [0x7F,0x40,0x40,0x40,0x40],
    "M": [0x7F,0x02,0x0C,0x02,0x7F],
    "N": [0x7F,0x04,0x08,0x10,0x7F],
    "O": [0x3E,0x41,0x41,0x41,0x3E],
    "P": [0x7F,0x09,0x09,0x09,0x06],
    "Q": [0x3E,0x41,0x51,0x21,0x5E],
    "R": [0x7F,0x09,0x19,0x29,0x46],
    "S": [0x46,0x49,0x49,0x49,0x31],
    "T": [0x01,0x01,0x7F,0x01,0x01],
    "U": [0x3F,0x40,0x40,0x40,0x3F],
    "V": [0x1F,0x20,0x40,0x20,0x1F],
    "W": [0x7F,0x20,0x18,0x20,0x7F],
    "X": [0x63,0x14,0x08,0x14,0x63],
    "Y": [0x07,0x08,0x70,0x08,0x07],
    "Z": [0x61,0x51,0x49,0x45,0x43],
}


# ---------- LCD driver ----------

class WhisplayLCD:
    def __init__(self):
        self.chip = gpiod.Chip(GPIOCHIP)

        self.dc = GPIOOut(self.chip, PIN_DC, 0)
        self.rst = GPIOOut(self.chip, PIN_RST, 1)
        self.bl = GPIOOut(self.chip, PIN_BL, 1)

        self.spi = spidev.SpiDev()
        self.spi.open(SPI_BUS, SPI_CS)
        self.spi.max_speed_hz = SPI_SPEED
        self.spi.mode = 0

        self.backlight(True)
        self.reset()
        self.init_lcd()

    def backlight(self, on):
        # GPIO22 is active-low
        self.bl.set(0 if on else 1)

    def reset(self):
        self.rst.set(1)
        time.sleep(0.05)
        self.rst.set(0)
        time.sleep(0.05)
        self.rst.set(1)
        time.sleep(0.12)

    def write_data(self, data):
        self.dc.set(1)
        if hasattr(self.spi, "writebytes2"):
            self.spi.writebytes2(data)
        else:
            for i in range(0, len(data), 4096):
                self.spi.writebytes(data[i:i + 4096])

    def cmd(self, c, *args):
        self.dc.set(0)
        self.spi.xfer2([c])
        if args:
            self.write_data(list(args))

    def init_lcd(self):
        self.cmd(0x11)
        time.sleep(0.12)

        self.cmd(0x36, 0xC0)
        self.cmd(0x3A, 0x05)

        self.cmd(0xB2, 0x0C, 0x0C, 0x00, 0x33, 0x33)
        self.cmd(0xB7, 0x35)
        self.cmd(0xBB, 0x32)
        self.cmd(0xC2, 0x01)
        self.cmd(0xC3, 0x15)
        self.cmd(0xC4, 0x20)
        self.cmd(0xC6, 0x0F)
        self.cmd(0xD0, 0xA4, 0xA1)

        self.cmd(
            0xE0,
            0xD0, 0x08, 0x0E, 0x09, 0x09, 0x05, 0x31,
            0x33, 0x48, 0x17, 0x14, 0x15, 0x31, 0x34,
        )
        self.cmd(
            0xE1,
            0xD0, 0x08, 0x0E, 0x09, 0x09, 0x15, 0x31,
            0x33, 0x48, 0x17, 0x14, 0x15, 0x31, 0x34,
        )

        self.cmd(0x21)
        self.cmd(0x29)
        time.sleep(0.05)

    def set_window(self, x0, y0, x1, y1):
        self.cmd(0x2A, x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)

        y0 += Y_OFFSET
        y1 += Y_OFFSET
        self.cmd(0x2B, y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)

        self.cmd(0x2C)

    def flush(self, fb):
        self.set_window(0, 0, LCD_W - 1, LCD_H - 1)
        self.write_data(fb)

    def close(self):
        try:
            self.backlight(False)
            self.spi.close()
            self.dc.release()
            self.rst.release()
            self.bl.release()
            self.chip.close()
        except Exception:
            pass


# ---------- drawing ----------

def put_pixel(fb, x, y, color):
    if x < 0 or y < 0 or x >= LCD_W or y >= LCD_H:
        return

    i = 2 * (y * LCD_W + x)
    fb[i] = (color >> 8) & 0xFF
    fb[i + 1] = color & 0xFF


def fill(fb, color):
    hi = (color >> 8) & 0xFF
    lo = color & 0xFF

    for i in range(0, len(fb), 2):
        fb[i] = hi
        fb[i + 1] = lo


def draw_rect(fb, x, y, w, h, color):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            put_pixel(fb, xx, yy, color)


def draw_char(fb, x, y, ch, color=WHITE, scale=3):
    ch = ch.upper()
    glyph = FONT.get(ch, FONT[" "])

    for col, bits in enumerate(glyph):
        for row in range(7):
            if bits & (1 << row):
                px = x + col * scale
                py = y + row * scale

                for yy in range(scale):
                    for xx in range(scale):
                        put_pixel(fb, px + xx, py + yy, color)


def draw_text(fb, x, y, text, color=WHITE, scale=3):
    cx = x
    cy = y

    char_w = 6 * scale
    line_h = 9 * scale

    for ch in text:
        if ch == "\n":
            cx = x
            cy += line_h
            continue

        draw_char(fb, cx, cy, ch, color, scale)
        cx += char_w


def center_text_x(text, scale):
    width = len(text) * 6 * scale
    return max(0, (LCD_W - width) // 2)


# ---------- clock app ----------

def main():
    lcd = WhisplayLCD()
    fb = bytearray(LCD_W * LCD_H * 2)

    last_second = None

    try:
        while True:
            now = datetime.datetime.now()

            if now.second == last_second:
                time.sleep(0.05)
                continue

            last_second = now.second

            timestr = now.strftime("%H:%M:%S")
            datestr = now.strftime("%Y-%m-%d")
            weekday = now.strftime("%A").upper()

            fill(fb, BLACK)

            draw_text(fb, center_text_x("WHISPLAY", 3), 25, "WHISPLAY", BLUE, scale=3)

            draw_rect(fb, 10, 65, 220, 2, WHITE)

            draw_text(fb, center_text_x(timestr, 5), 95, timestr, GREEN, scale=5)

            draw_text(fb, center_text_x(datestr, 3), 170, datestr, YELLOW, scale=3)
            draw_text(fb, center_text_x(weekday, 2), 215, weekday, WHITE, scale=2)

            lcd.flush(fb)

    except KeyboardInterrupt:
        pass
    finally:
        lcd.close()


if __name__ == "__main__":
    main()
