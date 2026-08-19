#!/usr/bin/env python3
"""Compact clock and network status screen for the Whisplay LCD."""

import datetime
import re
import subprocess
import time

from clock import (
    BLACK,
    BLUE,
    GREEN,
    LCD_H,
    LCD_W,
    RED,
    WHITE,
    YELLOW,
    WhisplayLCD,
    center_text_x,
    draw_rect,
    draw_text,
    fill,
)


NETWORK_REFRESH = 10.0
LEASE_FILE = "/var/lib/misc/dnsmasq.leases"


def command(*args):
    """Run a small local query without ever holding up the display loop."""
    try:
        return subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def safe_text(value, limit):
    # The built-in clock font has A-Z, digits and this punctuation.
    value = re.sub(r"[^A-Za-z0-9 .:/-]", " ", value)
    return value[:limit].upper()


def interface_ipv4(name):
    output = command("ip", "-4", "-o", "addr", "show", "dev", name)
    match = re.search(r"\binet\s+([0-9.]+)/", output)
    return match.group(1) if match else ""


def gateway_latency():
    routes = command("ip", "route", "show", "default", "dev", "wlan0")
    match = re.search(r"\bvia\s+([0-9.]+)", routes)
    if not match:
        return ""

    output = command("ping", "-c", "1", "-W", "1", match.group(1))
    match = re.search(r"\btime[=<]([0-9.]+)\s*ms", output, re.IGNORECASE)
    if not match:
        return "TIMEOUT"
    return "%d MS" % round(float(match.group(1)))


def wlan_status():
    link = command("iw", "dev", "wlan0", "link")
    if not link or "Not connected" in link:
        return "WLAN DOWN", interface_ipv4("wlan0") or "NO ADDRESS", ""

    match = re.search(r"^\s*SSID:\s*(.+)$", link, re.MULTILINE)
    ssid = safe_text(match.group(1), 15) if match else "CONNECTED"
    address = interface_ipv4("wlan0") or "NO ADDRESS"
    return "WLAN " + ssid, address, gateway_latency()


def leases_by_mac():
    leases = {}
    try:
        with open(LEASE_FILE, "r", encoding="ascii", errors="replace") as stream:
            for line in stream:
                fields = line.split()
                if len(fields) >= 4:
                    leases[fields[1].lower()] = (fields[2], fields[3])
    except OSError:
        pass
    return leases


def ap_clients():
    stations = re.findall(
        r"^Station\s+([0-9a-f:]{17})\s+",
        command("iw", "dev", "ap0", "station", "dump"),
        re.MULTILINE | re.IGNORECASE,
    )
    leases = leases_by_mac()

    # Neighbours provide an IP fallback if a lease file is absent or stale.
    neighbours = {}
    for ip, mac in re.findall(
        r"^([0-9.]+).*\blladdr\s+([0-9a-f:]{17})\b",
        command("ip", "neigh", "show", "dev", "ap0"),
        re.MULTILINE | re.IGNORECASE,
    ):
        neighbours[mac.lower()] = ip

    clients = []
    for mac in stations:
        mac = mac.lower()
        ip, hostname = leases.get(mac, (neighbours.get(mac, "NO IP"), ""))
        name = "CLIENT" if hostname in ("", "*") else safe_text(hostname, 19)
        clients.append((name, safe_text(ip, 15)))
    return clients


def read_network():
    wlan_line, wlan_ip, latency = wlan_status()
    return wlan_line, wlan_ip, latency, ap_clients()


def main():
    lcd = WhisplayLCD()
    fb = bytearray(LCD_W * LCD_H * 2)
    last_second = None
    last_network_read = 0.0
    network = ("WLAN CHECKING", "", "", [])

    try:
        while True:
            now = datetime.datetime.now()
            monotonic_now = time.monotonic()
            if monotonic_now - last_network_read >= NETWORK_REFRESH:
                network = read_network()
                last_network_read = monotonic_now

            if now.second == last_second:
                time.sleep(0.05)
                continue
            last_second = now.second

            wlan_line, wlan_ip, latency, clients = network
            fill(fb, BLACK)

            timestr = now.strftime("%H:%M:%S")
            datestr = now.strftime("%a %Y-%m-%d").upper()
            draw_text(fb, center_text_x("ZERO SITE", 2), 3, "ZERO SITE", BLUE, scale=2)
            draw_text(fb, center_text_x(timestr, 5), 24, timestr, GREEN, scale=5)
            draw_text(fb, center_text_x(datestr, 2), 65, datestr, YELLOW, scale=2)
            draw_rect(fb, 4, 84, 232, 1, BLUE)

            wlan_color = GREEN if not wlan_line.endswith("DOWN") else RED
            draw_text(fb, 4, 92, wlan_line, wlan_color, scale=2)
            draw_text(fb, 4, 112, wlan_ip, WHITE, scale=2)
            if latency:
                latency_text = "(" + latency + ")"
                draw_text(
                    fb,
                    LCD_W - 4 - len(latency_text) * 6,
                    116,
                    latency_text,
                    GREEN if latency != "TIMEOUT" else RED,
                    scale=1,
                )

            draw_rect(fb, 4, 133, 232, 1, BLUE)
            heading = "AP0 %d CLIENT%s" % (len(clients), "" if len(clients) == 1 else "S")
            draw_text(fb, 4, 141, heading, BLUE, scale=2)

            if clients:
                for index, (hostname, address) in enumerate(clients[:5]):
                    y = 163 + index * 19
                    address_x = LCD_W - 4 - len(address) * 12
                    hostname_chars = max(1, (address_x - 4) // 12 - 1)
                    draw_text(fb, 4, y, hostname[:hostname_chars], WHITE, scale=2)
                    draw_text(fb, address_x, y, address, WHITE, scale=2)
            else:
                draw_text(fb, 4, 163, "NO CLIENTS", WHITE, scale=2)

            lcd.flush(fb)
    except KeyboardInterrupt:
        pass
    finally:
        lcd.close()


if __name__ == "__main__":
    main()
