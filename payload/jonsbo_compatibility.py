"""Pure host support for an optional manual port-1 RGB compatibility profile.

No HID access, hardware writes, resets, timers, or firmware operations occur in
this module. A profile selection records intent. Only a fresh hardware topology
can confirm that the firmware has activated the requested LED count.
"""

import json
import os


PROFILE_SCHEMA = 1
COMPATIBILITY_PORT = 0
DEFAULT_LED_COUNT = 0
MAX_MANUAL_LED_COUNT = 100


def validate_count(count):
    if isinstance(count, bool) or not isinstance(count, int):
        raise ValueError("LED count must be an integer")
    if not 0 <= count <= MAX_MANUAL_LED_COUNT:
        raise ValueError("Manual LED count must be between 0 and 100")
    return count


def native_report(body):
    """Build stock RB framing; caller remains responsible for its RGB gate."""
    body = list(body)
    if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255
           for v in body):
        raise ValueError("A report body must contain byte values")
    report = [0, 0x52, 0x42, 5 + len(body), 0] + body
    return report + [sum(report) % 256]


def native_body(report):
    """Return a validated body, or None. Never rewrites the caller's report."""
    try:
        packet = list(report)
    except TypeError:
        return None
    if (len(packet) < 7 or packet[:3] != [0, 0x52, 0x42]
            or any(isinstance(v, bool) or not isinstance(v, int)
                   or not 0 <= v <= 255 for v in packet)):
        return None
    length = packet[3]
    if length != len(packet) - 1 or packet[4] != 0:
        return None
    if sum(packet[:length]) % 256 != packet[length]:
        return None
    return packet[5:length]


class CompatibilityProfile:
    """Persist explicit selections while keeping hardware evidence separate.

    Construction and topology observation do not write any file. `select_count`
    is for an explicit user action only. Startup must not replay count commands:
    the firmware count command writes flash, even though its immediate effect is
    a preview. No shutdown path should reset or erase this selection.
    """

    def __init__(self, path, default_count=DEFAULT_LED_COUNT):
        self.path = os.fspath(path)
        self.desired_count = validate_count(default_count)
        self.hardware_counts = None
        self.explicit_selection = False
        try:
            with open(self.path, "r", encoding="utf-8") as stream:
                data = json.load(stream)
        except FileNotFoundError:
            return
        if (not isinstance(data, dict) or data.get("schema") != PROFILE_SCHEMA
                or data.get("port") != COMPATIBILITY_PORT):
            raise ValueError("Unsupported manual RGB compatibility profile")
        self.desired_count = validate_count(data.get("led_count"))
        self.explicit_selection = True

    def select_count(self, count):
        """Persist an explicit manual selection; emit no hardware commands."""
        count = validate_count(count)
        payload = {"schema": PROFILE_SCHEMA, "port": COMPATIBILITY_PORT,
                   "led_count": count}
        parent = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(parent, exist_ok=True)
        temporary = self.path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, self.path)
        self.desired_count = count
        self.explicit_selection = True
        return self.status()

    def observe_topology(self, counts):
        """Record a fresh real ten-port response, without applying UI overrides."""
        observed = tuple(counts)
        if len(observed) != 10 or any(
                isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255
                for v in observed):
            raise ValueError("Hardware topology must contain ten byte counts")
        self.hardware_counts = observed
        return self.status()

    record_hardware_topology = observe_topology

    @property
    def pending_activation(self):
        return (self.explicit_selection
                and (self.hardware_counts is None
                     or self.hardware_counts[COMPATIBILITY_PORT] != self.desired_count))

    def effective_counts(self):
        """Return a copy of real hardware counts; never invent an active slot.

        The manual count field may display desired_count with a pending label,
        but rendering offsets and port availability must use this hardware data.
        """
        if self.hardware_counts is None:
            raise ValueError("No topology is available")
        return list(self.hardware_counts)

    def status(self):
        actual = (None if self.hardware_counts is None
                  else self.hardware_counts[COMPATIBILITY_PORT])
        return {"port": COMPATIBILITY_PORT,
                "desired_count": self.desired_count,
                "hardware_count": actual,
                "hardware_counts": self.hardware_counts,
                "explicit_selection": self.explicit_selection,
                "pending_activation": self.pending_activation}


class NativeModeNormalizer:
    """Suggest FD 01 before native effects after opening or count preview.

    `before` returns a separate prelude or None, never a replacement effect.
    Caller sends/logs the prelude through its normal RGB packet gate, calls
    `accepted` only after successful transport, then sends the original report
    unchanged. A failed prelude must not be acknowledged via `accepted`.
    """

    def __init__(self):
        self.opened()

    def opened(self):
        self.normalization_needed = True

    def before(self, report):
        body = native_body(report)
        if (self.normalization_needed and body is not None
                and len(body) == 55 and body[0] == 3):
            return native_report([0xFD, 1])
        return None

    def accepted(self, report):
        body = native_body(report)
        if body == [0xFD, 1]:
            self.normalization_needed = False
        elif body == [0xFD, 0]:
            self.normalization_needed = True
        elif (body is not None and len(body) == 4
              and body[:3] == [2, COMPATIBILITY_PORT, 0]
              and 0 <= body[3] <= MAX_MANUAL_LED_COUNT):
            self.normalization_needed = True
