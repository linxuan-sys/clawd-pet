#!/usr/bin/env python3
"""clawd-ears for Linux: listens to the system output, never the microphone.

Reads the default sink's monitor through parec (PulseAudio or PipeWire's
pulse compatibility), keeps only a loudness number and whether a beat landed,
and prints one line at a time:

  ok              the monitor is running
  error <why>     it could not start; the program then exits
  <level> <beat>  loudness 0..9 and 1 when a beat landed in the last 50 ms

The audio never leaves this process.
"""

import math
import os
import signal
import struct
import subprocess
import sys
import time

RATE = 22050
CHUNK = RATE // 20  # 50 ms
BYTES = CHUNK * 2
LEVEL_STEP_DB = 6.0

running = True


def stop(_signum, _frame):
    global running
    running = False


def out(line):
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def default_monitor():
    try:
        sink = subprocess.check_output(
            ["pactl", "get-default-sink"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return None
    return sink + ".monitor" if sink else None


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGHUP, stop)

    monitor = default_monitor()
    if not monitor:
        out("error no default audio sink")
        return 1
    try:
        ears = subprocess.Popen(
            [
                "parec",
                "--device=" + monitor,
                "--format=s16le",
                "--rate=%d" % RATE,
                "--channels=1",
                "--latency-msec=50",
                "--raw",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
    except Exception as err:
        out("error " + str(err))
        return 1

    out("ok")
    parent = os.getppid()
    level = -1
    beat_at = 0.0
    slow = 0.0
    last_out = 0.0
    try:
        while running:
            if os.getppid() != parent:
                break
            data = ears.stdout.read(BYTES)
            if not data:
                break
            if len(data) < BYTES:
                data += b"\0" * (BYTES - len(data))
            samples = struct.unpack("<%dh" % CHUNK, data[:BYTES])
            rms = math.sqrt(sum(s * s for s in samples) / CHUNK)
            db = 20.0 * math.log10(rms / 32768.0) if rms > 1 else -90.0
            now = time.monotonic()
            lvl = max(0, min(9, int((db + 60.0) / LEVEL_STEP_DB)))
            slow = slow * 0.92 + rms * 0.08 if slow else rms
            beat = 0
            if lvl >= 2 and rms > max(400.0, slow * 1.45) and now - beat_at > 0.18:
                beat_at = now
                beat = 1
            if lvl != level or beat or now - last_out >= 1.0:
                out("%d %d" % (lvl, beat))
                level = lvl
                last_out = now
    finally:
        try:
            ears.terminate()
            ears.wait(timeout=1)
        except Exception:
            try:
                ears.kill()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
