"""RGB-only manual LED compatibility for an isolated Umbra 3.5.5 copy.

Only an explicit LED Count action saves RGB configuration. Never replay that
flash-writing command on startup/shutdown, reset, write PWM, or update firmware.
"""
import builtins
import importlib.util
import json
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(ROOT, "umbra-rgb-addon.jsonl")
_lock = threading.RLock()
_spec = importlib.util.spec_from_file_location(
    "jonsbo_compatibility", os.path.join(ROOT, "jonsbo_compatibility.py"))
_compat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_compat)
PROFILE = _compat.CompatibilityProfile(os.path.join(ROOT, "manual-led-profile.json"))


def event(kind, **data):
    with _lock:
        with open(LOG_PATH, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(time=time.time(), event=kind, **data)) + "\n")


def permitted(report):
    try:
        b = list(report)
    except TypeError:
        return False
    if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255
           for v in b):
        return False
    if len(b) == 65 and b[:2] == [0, 0x88]:
        return b[2] > 0 and 1 <= b[3] <= b[2] and sum(b[1:64]) % 256 == b[64]
    body = _compat.native_body(b)
    if body is None:
        return False
    if body == [0] or len(body) == 2 and body[0] == 1:
        return True  # identity/topology reads
    if len(body) == 4 and body[:3] == [2, 0, 0] and 0 <= body[3] <= 100:
        return True  # only physical port 1 LED count
    if len(body) == 3 and body[0] == 5 and 0 <= body[1] < 10 and body[2] == 1:
        return True  # vendor RGB identify
    if body == [0xFD, 0] or body == [0xFD, 1]:
        return True  # motherboard sync / USB RGB control
    if len(body) == 55 and body[0] == 3:
        return True  # vendor per-port RGB effect, including its 52-byte data
    if len(body) == 2 and body[0] in (0x95, 0x96, 0x97, 0x99):
        return True  # RGB effect, animation speed, direction, brightness
    if len(body) == 13 and body[0] == 0x9A:
        return True  # four RGB colors
    return False


def compatibility_text():
    status = PROFILE.status()
    actual = status["hardware_count"]
    target = status["desired_count"]
    if not status["explicit_selection"]:
        if actual is None:
            return "Port 1: manual profile not selected; waiting for hub topology."
        return ("Port 1: active %d LEDs; manual profile not selected." % actual)
    if actual is None:
        return "Port 1: saved target %d LEDs; waiting for hub topology" % target
    if status["pending_activation"]:
        return ("Port 1: target %d / active %d LEDs. "
                "Restart the PC once to activate the saved count." % (target, actual))
    return "Port 1: active %d LEDs (confirmed by hub)" % actual


def install():
    def exception_hook(kind, value, tb):
        # Tracebacks and exception strings can contain private local paths.
        event("uncaught_exception", exception_type=kind.__name__)
    sys.excepthook = exception_hook
    event("hook_start", dry_run=os.environ.get("UMBRA_RGB_DRY_RUN") == "1")
    import hid
    original_device = hid.device
    original_enumerate = hid.enumerate

    class RgbDevice:
        def __init__(self, *args, **kwargs):
            self._inner = original_device(*args, **kwargs)
            self._selected = False
            self._write_lock = threading.RLock()
            self._mode = _compat.NativeModeNormalizer()

        def open(self, vid, pid, *args, **kwargs):
            if (vid, pid) != (0x1A86, 0xFE04):
                raise OSError("Umbra RGB Add-on supports only the FE04 hub")
            result = self._inner.open(vid, pid, *args, **kwargs)
            self._selected = True
            self._mode.opened()
            event("open", vid=vid, pid=pid)
            return result

        def open_path(self, path):
            if path not in {d["path"] for d in original_enumerate(0x1A86, 0xFE04)}:
                raise OSError("Umbra RGB Add-on supports only the FE04 hub")
            result = self._inner.open_path(path)
            self._selected = True
            self._mode.opened()
            event("open_path", vid=0x1A86, pid=0xFE04)
            return result

        def write(self, report):
            data = list(report)
            allowed = self._selected and permitted(data)
            if not allowed:
                event("blocked_write", data=data)
                # Preserve the vendor UI's flow while preventing this write.
                return len(data)
            with self._write_lock:
                prelude = self._mode.before(data)
                if prelude is not None:
                    assert permitted(prelude)
                    result = self._inner.write(prelude)
                    event("write", data=prelude, result=result, reason="native_effect_usb_handover")
                    if result <= 0:
                        raise OSError("USB RGB mode handover failed")
                    self._mode.accepted(prelude)
                result = self._inner.write(report)
                event("write", data=data, result=result)
                if result > 0:
                    self._mode.accepted(data)
                    body = _compat.native_body(data)
                    if body is not None and len(body) == 4 and body[:3] == [2, 0, 0]:
                        with _lock:
                            status = PROFILE.select_count(body[3])
                        event("compatibility_selected", **status)
                return result

        def read(self, *args, **kwargs):
            result = self._inner.read(*args, **kwargs)
            if result:
                data = list(result)
                # Identity responses include a device identifier. Never log
                # complete input reports or USB instance paths in this edition.
                event("read", length=len(data), command=data[4] if len(data) > 4 else None)
                if len(data) >= 56 and data[:2] == [82, 66] and data[4:6] == [1, 255]:
                    with _lock:
                        status = PROFILE.observe_topology([data[6 + 5 * i] for i in range(10)])
                    event("compatibility_topology", **status)
            return result

        def send_feature_report(self, *args, **kwargs):
            event("blocked_feature_report")
            raise OSError("Feature-report writes are outside RGB-only scope")

        def __getattr__(self, name):
            return getattr(self._inner, name)

    hid.device = RgbDevice
    hid.enumerate = lambda *a, **k: [] if os.environ.get("UMBRA_RGB_DRY_RUN") == "1" else [d for d in original_enumerate(*a, **k)
                                   if (d.get("vendor_id"), d.get("product_id")) == (0x1A86, 0xFE04)]
    original_build = builtins.__build_class__

    def build(func, name, *args, **kwargs):
        cls = original_build(func, name, *args, **kwargs)
        if name == "MainWindow" and func.__module__ == "__main__":
            original_handler = cls.on_ARGB_settings_box_number_selected
            original_init = cls.__init__
            original_config = cls.fan_set_config

            def show_status(self):
                label = getattr(self, "addon_status_label", None)
                if label is not None:
                    label.setText(compatibility_text())
                self.ARGB_settings_box_number.setToolTip(compatibility_text())

            def fan_config(self, index):
                original_config(self, index)
                if index == 0 and PROFILE.explicit_selection:
                    box = self.ARGB_settings_box_number
                    previous = box.blockSignals(True)
                    box.setCurrentText(str(PROFILE.desired_count))
                    box.blockSignals(previous)
                show_status(self)

            def count_handler(self, index):
                port_index = self.fan_ten_stata
                count = int(self.ARGB_settings_box_number.itemText(index))
                if port_index != 0:
                    event("blocked_count_change", port=port_index, count=count)
                    return
                original_handler(self, index)
                # The native command persists the RGB count but renders only a
                # preview. Do not fabricate active allocation in the UI cache.
                event("compatibility_count_action", **PROFILE.status())
                show_status(self)

            def init(self, *a, **k):
                original_init(self, *a, **k)
                self.setWindowTitle("UMBRA - RGB Add-on")
                from PySide2.QtCore import QTimer
                from PySide2.QtWidgets import QLabel
                box = self.ARGB_settings_box_number
                previous = box.blockSignals(True)
                for i in range(box.count() - 1, -1, -1):
                    if int(box.itemText(i)) > 100:
                        box.removeItem(i)
                box.blockSignals(previous)
                self.addon_status_label = QLabel(compatibility_text(), self.yingjian_info_group)
                self.addon_status_label.setWordWrap(True)
                self.addon_status_label.setStyleSheet("color: #ffe500; font-size: 11px;")
                self.yingjian_info_group.layout().addWidget(self.addon_status_label)
                self.addon_status_timer = QTimer(self)
                self.addon_status_timer.timeout.connect(lambda: show_status(self))
                self.addon_status_timer.start(1000)
                event("window_ready")
                if os.environ.get("UMBRA_RGB_DRY_RUN") == "1":
                    from PySide2.QtWidgets import QApplication
                    QTimer.singleShot(1500, lambda: self.grab().save(os.path.join(ROOT, "compatibility-dry-run.png")))
                    QTimer.singleShot(1500, lambda: self.yingjian_info_group.grab().save(
                        os.path.join(ROOT, "compatibility-status-dry-run.png")))
                    QTimer.singleShot(3000, QApplication.instance().quit)

            cls.on_ARGB_settings_box_number_selected = count_handler
            cls.fan_set_config = fan_config
            cls.__init__ = init
        return cls

    builtins.__build_class__ = build
    event("hook_ready", scope="FE04 RGB only; optional manual port-1 profile, actual topology, USB mode handover",
          compatibility=PROFILE.status())


def patch_code(code):
    import types
    # These vendor functions install/start a monitoring driver or helper, manage
    # scheduled startup, elevate privileges, or terminate unrelated helpers.
    blocked = {"clean_pawnio_cpuserver", "install_pawnio_signed", "start_clean_thread",
               "gengxin_cominfo", "check_startup_process", "create_startup_task",
               "start_exe", "kill_cpu_server_process", "do_elevate",
               "add_to_startup", "remove_from_startup"}
    noop = compile("def stub(*args, **kwargs): return None", "<rgb-disabled-helper>", "exec").co_consts[0]
    if code.co_name in blocked:
        event("helper_disabled", name=code.co_name)
        return noop.replace(co_name=code.co_name, co_freevars=code.co_freevars)
    constants = tuple(patch_code(c) if isinstance(c, types.CodeType) else c for c in code.co_consts)
    return code.replace(co_consts=constants)


def self_test():
    def native(body):
        data = [0, 82, 66, 5 + len(body), 0] + body
        return data + [sum(data) % 256]
    for body in ([0], [1, 255], [5, 0, 1], [2, 0, 0, 24], [0xFD, 1], [3, 253, 0] + [0] * 52):
        assert permitted(native(body)), body
    for cmd in (0xFB, 0xFA, 0xFC, 7, 0x0B, 0x0C):
        assert not permitted(native([cmd, 1])), cmd
    assert not permitted(native([2, 1, 0, 24]))
    assert not permitted(native([2, 0, 1, 24]))
    assert not permitted([0, 82, 66, 255])
    print("PASS: RGB packet gate, forbidden commands, port-1-only explicit count")


if __name__ == "__main__":
    self_test()
