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

RATE = 22050
CHUNK = RATE // 20  # 50 ms
BYTES = CHUNK * 2

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
    # The same level scale and beat detection as clawd-ears.swift: level 9 is the loudest
    # window of the last while, so the bars follow the music and not the system volume, and
    # a beat is a window clearly louder than the second before it, at most one every 250 ms.
    quiet_floor = 0.003 * 32768.0  # quieter than this is silence
    loud_floor = 0.05 * 32768.0  # the loudest recent window never drops below this
    history = [0.0] * 20
    at = 0
    peak = loud_floor
    previous = 0.0
    since_beat = 100
    said = (0, False)
    quiet = 0
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
            loudness = math.sqrt(sum(s * s for s in samples) / CHUNK)
            average = sum(history) / len(history)
            history[at] = loudness
            at = (at + 1) % len(history)
            peak = max(loudness, peak * 0.998, loud_floor)
            since_beat += 1
            audible = loudness > quiet_floor
            beat = audible and since_beat >= 5 and loudness > average * 1.35 and loudness > previous
            if beat:
                since_beat = 0
            previous = loudness
            # Swift rounds half away from zero; Python rounds half to even
            level = min(9, max(1, int(loudness / peak * 9 + 0.5))) if audible else 0
            quiet += 1
            if level != said[0] or beat or said[1] or quiet >= 20:
                out("%d %d" % (level, 1 if beat else 0))
                said = (level, beat)
                quiet = 0
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
