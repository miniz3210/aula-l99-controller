#!/usr/bin/env python3
"""L99 screen icon mailbox client (English only, stdlib only).

Target: HFD V2.2 + DI-PATCH-A 1.4.0 + official UI (screen_v1.23). Emulator use only until the
physical flash gate is passed. Transports: TCP (CEmu bridge) and in-memory fake. No serial/COM.

Wire format: 5A A5 len body CRC16-MODBUS(LE). 0x10 = VP write, 0x03 = VP read.
VP RAM keeps frame byte order, so 16-bit values for the patch are sent low byte first.
Upload sequence: pixel frames (window-verified) -> x,y,w,h -> clear 0 -> GO -> poll DONE/ERROR.
"""
import socket
import struct
import time

GO, DONE, ERR = 0xA55A, 0x600D, 0xEEEE
SCREEN_W, SCREEN_H = 320, 480
PAGE_VP = 0x7000
MAX_WORDS = 120
DEFAULT_LAYOUT = {
    "buf_vp": 0x0400, "buf_vps": 6144, "mb_vp": 0x1F00,
    "firmware_sha256": "432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf",
    "patched_image_sha256": "df3a998b0c8cf7689610bc2dae63f4081a660e3d6b0b927f2dd3f92acb6310fe",
    "ui_sha256": "903a4fbad5ed1f6165d8b4491ef967fb2c88e375c6a416b21476cdb20a99d76d",
}
# VP ranges the client must never write (official UI widgets and system alias range).
FORBIDDEN_VP = [(0x0000, 0x00FF), (0x0300, 0x03FF), (0x2000, 0x6FFF)]


class L99Error(Exception):
    pass


def crc16(data):
    c = 0xFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c


def frame(body):
    body = bytes(body)
    if len(body) + 2 > 255:
        raise L99Error("frame too long")
    c = crc16(body)
    return b"\x5A\xA5" + bytes([len(body) + 2]) + body + bytes([c & 0xFF, c >> 8])


def split_frames(buf):
    """Return (list of bodies with valid CRC, remaining bytes)."""
    out, k = [], 0
    while True:
        k2 = buf.find(b"\x5A\xA5", k)
        if k2 < 0:
            return out, buf[-1:] if buf.endswith(b"\x5A") else b""
        if k2 + 3 > len(buf):
            return out, buf[k2:]
        n = buf[k2 + 2]
        if n < 2:
            k = k2 + 1
            continue
        if k2 + 3 + n > len(buf):
            return out, buf[k2:]
        body = buf[k2 + 3:k2 + 1 + n]
        crc = buf[k2 + 1 + n:k2 + 3 + n]
        if crc16(body) == (crc[0] | crc[1] << 8):
            out.append(bytes(body))
            k = k2 + 3 + n
        else:
            k = k2 + 1


def le_words(words):
    return b"".join(struct.pack("<H", w & 0xFFFF) for w in words)


# ---------------------------------------------------------------- transports
class TcpTransport:
    """Byte pipe to the CEmu UART bridge (use an SSH tunnel to 127.0.0.1 on REA)."""

    def __init__(self, host="127.0.0.1", port=7799, timeout=5.0):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def write(self, data):
        self.s.sendall(data)

    def read(self, timeout):
        self.s.settimeout(max(0.001, timeout))
        try:
            d = self.s.recv(65536)
        except socket.timeout:
            return b""
        if d == b"":
            raise L99Error("connection closed")
        return d

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


# ---------------------------------------------------------------- client
class L99Mailbox:
    def __init__(self, transport, layout=None, window=4, timeout=3.0):
        self.t = transport
        self.L = dict(DEFAULT_LAYOUT, **(layout or {}))
        self.window = max(1, int(window))
        self.timeout = float(timeout)
        self._rx = b""
        self.cache = {}          # (page, x, y, w, h) -> pixels
        lo, hi = self.L["buf_vp"], self.L["buf_vp"] + self.L["buf_vps"] - 1
        mlo, mhi = self.L["mb_vp"], self.L["mb_vp"] + 4
        self._allowed = [(lo, hi), (mlo, mhi)]
        for a, b in self._allowed:
            for f, g in FORBIDDEN_VP:
                if a <= g and f <= b:
                    raise L99Error("layout overlaps forbidden VP range %#x-%#x" % (f, g))
        if not (hi < mlo or mhi < lo):
            raise L99Error("buffer overlaps mailbox")

    # -- low level
    def _send(self, raw):
        self.t.write(raw)

    def _wait(self, pred, timeout=None):
        end = time.monotonic() + (self.timeout if timeout is None else timeout)
        while True:
            bodies, self._rx = split_frames(self._rx)
            for i, b in enumerate(bodies):
                if pred(b):
                    rest = bodies[i + 1:]
                    self._rx = b"".join(frame(x) for x in rest) + self._rx
                    return b
            left = end - time.monotonic()
            if left <= 0:
                raise L99Error("timeout waiting for reply")
            self._rx += self.t.read(min(left, 0.05))

    def read_raw(self, vp, n):
        self._send(frame(bytes([0x03, vp >> 8, vp & 0xFF, 0x00, n])))
        b = self._wait(lambda b: len(b) >= 5 + 2 * n and b[0] == 0x03 and (b[1] << 8 | b[2]) == vp)
        return b[5:5 + 2 * n]

    def read_words_le(self, vp, n):
        return list(struct.unpack("<%dH" % n, self.read_raw(vp, n)))

    def _write_le(self, vp, words):
        end = vp + len(words) - 1
        if not any(a <= vp and end <= b for a, b in self._allowed):
            raise L99Error("refusing write outside allowed VPs: %#x-%#x" % (vp, end))
        self._send(frame(bytes([0x10, vp >> 8, vp & 0xFF]) + le_words(words)))

    def _write_verify(self, vp, words, tries=3):
        for _ in range(tries):
            self._write_le(vp, words)
            if self.read_words_le(vp, len(words)) == [w & 0xFFFF for w in words]:
                return
        raise L99Error("write verify failed at VP %#x" % vp)

    # -- page
    def page(self):
        r = self.read_raw(PAGE_VP, 1)
        return r[0] << 8 | r[1]

    def set_page(self, page):
        if not 0 <= page <= 0xFF:
            raise L99Error("page out of range")
        self._send(frame([0x10, 0x70, 0x00, 0x00, page]))

    # -- icons
    def validate(self, x, y, w, h, pixels):
        if not (w > 0 and h > 0 and x >= 0 and y >= 0 and x + w <= SCREEN_W and y + h <= SCREEN_H):
            raise ValueError("rect outside screen")
        if w * h > self.L["buf_vps"]:
            raise ValueError("rect larger than pixel buffer")
        if len(pixels) != w * h:
            raise ValueError("pixel count does not match rect")

    def upload(self, x, y, w, h, pixels, remember=True, _skip_validation=False):
        """pixels: RGB565 ints, row-major. Returns status dict; raises L99Error on transport failure."""
        if not _skip_validation:
            self.validate(x, y, w, h, pixels)
        t0 = time.monotonic()
        buf = self.L["buf_vp"]
        px = [p & 0xFFFF for p in pixels]
        chunks = [(i, px[i:i + MAX_WORDS]) for i in range(0, len(px), MAX_WORDS)]
        for k, (i, ch) in enumerate(chunks):
            self._write_le(buf + i, ch)
            if (k + 1) % self.window == 0 or k + 1 == len(chunks):
                last = buf + i + len(ch) - 1
                ok = False
                for _ in range(3):
                    if self.read_words_le(last, 1) == [ch[-1]]:
                        ok = True
                        break
                    self._write_le(buf + i, ch)
                if not ok:
                    raise L99Error("pixel window not acknowledged at VP %#x" % last)
        mb = self.L["mb_vp"]
        self._write_verify(mb + 1, [x, y, w, h])
        self._write_verify(mb, [0])
        self._write_le(mb, [GO])
        end = time.monotonic() + self.timeout
        st = GO
        while time.monotonic() < end:
            st = self.read_words_le(mb, 1)[0]
            if st in (DONE, ERR):
                break
        res = {"status": {DONE: "DONE", ERR: "ERROR"}.get(st, "TIMEOUT"), "raw": hex(st),
               "frames": len(chunks), "seconds": round(time.monotonic() - t0, 4)}
        if res["status"] == "DONE" and remember:
            pg = self.page()
            self.cache = {k: v for k, v in self.cache.items()
                          if not (k[0] == pg and k[1:] == (x, y, w, h))}
            self.cache[(pg, x, y, w, h)] = px
        return res

    def resend_page(self, page=None):
        """Re-upload cached icons for the current (or given) page. Call after page change or reconnect."""
        pg = self.page() if page is None else page
        out = []
        for (p, x, y, w, h), px in list(self.cache.items()):
            if p == pg:
                out.append(self.upload(x, y, w, h, px, remember=False)["status"])
        return out


# ---------------------------------------------------------------- offline fake device + selftest
class FakeL99:
    """Models VP RAM, page redraw and the DI-PATCH-A mailbox (for offline tests only)."""

    def __init__(self):
        self.vp = bytearray(0x10000 * 2)
        self.page = 1
        self.lcd = [0] * (SCREEN_W * SCREEN_H)
        self.rx = b""
        self.tx = b""
        self._draw()

    def _draw(self):
        self.lcd = [(i * 7 + self.page * 131) & 0xFFFF for i in range(SCREEN_W * SCREEN_H)]

    def write(self, data):
        self.rx += data
        bodies, self.rx = split_frames(self.rx)
        for b in bodies:
            vp = b[1] << 8 | b[2]
            if b[0] == 0x10:
                if vp == PAGE_VP:
                    self.page = b[4]
                    self._draw()
                    continue
                self.vp[2 * vp:2 * vp + len(b) - 3] = b[3:]
                self._mailbox()
            elif b[0] == 0x03:
                n = b[4]
                data = bytes([0, self.page]) if vp == PAGE_VP else bytes(self.vp[2 * vp:2 * vp + 2 * n])
                self.tx += frame(bytes([0x03, b[1], b[2], 0x00, n]) + data)

    def _mailbox(self, mb=0x1F00, buf=0x0400):
        g = lambda v: struct.unpack_from("<H", self.vp, 2 * v)[0]
        if g(mb) != GO:
            return
        x, y, w, h = (g(mb + k) for k in range(1, 5))
        ok = w and h and x + w <= SCREEN_W and y + h <= SCREEN_H and w * h <= 6144
        if ok:
            for j in range(h):
                for i in range(w):
                    self.lcd[(y + j) * SCREEN_W + x + i] = g(buf + j * w + i)
        struct.pack_into("<H", self.vp, 2 * mb, DONE if ok else ERR)

    def read(self, timeout):
        d, self.tx = self.tx, b""
        return d

    def close(self):
        pass


def selftest():
    import random
    dev = FakeL99()
    m = L99Mailbox(dev)
    x, y, w, h = 48, 280, 64, 64
    rng = random.Random(1)
    B = [rng.randrange(65536) for _ in range(w * h)]
    C = [rng.randrange(65536) for _ in range(w * h)]
    base = list(dev.lcd)

    def rect(lcd):
        return [lcd[(y + j) * SCREEN_W + x + i] for j in range(h) for i in range(w)]

    def outside_changed(lcd):
        return sum(1 for k in range(len(lcd)) if lcd[k] != base[k]
                   and not (x <= k % SCREEN_W < x + w and y <= k // SCREEN_W < y + h))
    checks = {}
    checks["page_read"] = m.page() == 1
    checks["B"] = m.upload(x, y, w, h, B)["status"] == "DONE" and rect(dev.lcd) == B and outside_changed(dev.lcd) == 0
    checks["C"] = m.upload(x, y, w, h, C)["status"] == "DONE" and rect(dev.lcd) == C and outside_changed(dev.lcd) == 0
    m.set_page(21)
    checks["page21"] = m.page() == 21
    m.set_page(1)
    checks["redrawn_after_page"] = rect(dev.lcd) != C
    checks["resend"] = m.resend_page() == ["DONE"] and rect(dev.lcd) == C
    try:
        m.upload(300, 0, 64, 64, [0] * 4096)
        checks["client_rejects_bad_rect"] = False
    except ValueError:
        checks["client_rejects_bad_rect"] = True
    checks["device_error"] = m.upload(300, 0, 64, 64, [0] * 4096, remember=False,
                                      _skip_validation=True)["status"] == "ERROR"
    try:
        m._write_le(0x0000, [1])
        checks["guard_forbidden_vp"] = False
    except L99Error:
        checks["guard_forbidden_vp"] = True
    ok = all(checks.values())
    print("L99_MAILBOX_SELFTEST", "PASS" if ok else "FAIL", checks)
    return ok


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        sys.exit(0 if selftest() else 1)
    print(__doc__)
