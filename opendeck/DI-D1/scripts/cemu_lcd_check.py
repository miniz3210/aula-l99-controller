#!/usr/bin/env python3
"""CEmu LCD check: capture the CEmu LCD framebuffer and compare a rect.

Connects to the bridge control port (default 127.0.0.1:7800), sends `LCD`,
decodes base64 RGB565 LE (320x480), and compares a given rect against an
expected RGB565 file. Prints PASS/FAIL with mismatch count. Also supports
`SNAP <name>` to save a captured frame.

Uses stdlib only. No serial/COM/HID/USB writes.
"""

import base64
import socket
import struct
import sys
import argparse

SCREEN_W, SCREEN_H = 320, 480
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7800


def send_cmd(sock, cmd):
    sock.sendall(cmd.encode("ascii") + b"\n")
    buf = b""
    while b"\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            raise RuntimeError("connection closed while waiting for reply")
        buf += chunk
    return buf.split(b"\n", 1)[0].decode("ascii", errors="replace")


def capture_lcd(host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=10.0):
    s = socket.create_connection((host, port), timeout=timeout)
    try:
        reply = send_cmd(s, "LCD")
    finally:
        s.close()
    if not reply.startswith("LCD "):
        raise RuntimeError(f"unexpected LCD reply: {reply!r}")
    b64 = reply[4:]
    data = base64.b64decode(b64)
    expected = SCREEN_W * SCREEN_H * 2
    if len(data) != expected:
        raise RuntimeError(f"LCD payload {len(data)} bytes, expected {expected}")
    return data


def compare_rect(frame, x, y, w, h, expected_path):
    with open(expected_path, "rb") as f:
        expected = f.read()
    rect_len = w * h * 2
    if len(expected) < rect_len:
        raise RuntimeError(f"expected file {len(expected)} bytes, need {rect_len} for rect")

    mismatches = 0
    for j in range(h):
        row_off = (y + j) * SCREEN_W + x
        exp_off = j * w
        for i in range(w):
            a = struct.unpack_from("<H", frame, 2 * (row_off + i))[0]
            b = struct.unpack_from("<H", expected, 2 * (exp_off + i))[0]
            if a != b:
                mismatches += 1
    return mismatches


def snap(frame, name):
    path = f"{name}.rgb565"
    with open(path, "wb") as f:
        f.write(frame)
    return path


def main():
    ap = argparse.ArgumentParser(description="CEmu LCD rect comparison")
    ap.add_argument("--host", default=DEFAULT_HOST, help="bridge host (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="bridge control port (default 7800)")
    ap.add_argument("--rect", default="0,0,320,480", help="x,y,w,h rect to compare (default full screen)")
    ap.add_argument("--expected", help="expected RGB565 LE file to compare against")
    ap.add_argument("--snap", help="save captured frame to <name>.rgb565")
    args = ap.parse_args()

    try:
        x, y, w, h = (int(v) for v in args.rect.split(","))
    except ValueError:
        print("FAIL: --rect must be x,y,w,h")
        return 1

    try:
        frame = capture_lcd(args.host, args.port)
    except Exception as e:
        print(f"FAIL: capture failed: {e}")
        return 1

    if args.snap:
        path = snap(frame, args.snap)
        print(f"SNAP {path} ({len(frame)} bytes)")

    if args.expected is None:
        print("PASS: LCD captured, no --expected to compare")
        return 0

    try:
        mismatches = compare_rect(frame, x, y, w, h, args.expected)
    except Exception as e:
        print(f"FAIL: compare failed: {e}")
        return 1

    total = w * h
    if mismatches == 0:
        print(f"PASS: rect ({x},{y},{w}x{h}) matches expected, {total} pixels, 0 mismatches")
        return 0
    else:
        print(f"FAIL: rect ({x},{y},{w}x{h}) {mismatches}/{total} pixels mismatch expected")
        return 1


if __name__ == "__main__":
    sys.exit(main())
