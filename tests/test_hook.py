"""Offline integration of the real vendor hook with fake HID and Qt objects.

No installed app is imported and no hardware can be opened. The hook is copied
to a temporary workspace folder so its logs/profile stay isolated from live data.
"""
import builtins
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "payload"
sys.path.insert(0, str(ROOT))

from jonsbo_compatibility import native_report


COUNTS = [0, 48, 72, 0, 48, 0, 0, 0, 0, 0]


class FakeSignal:
    def connect(self, callback):
        self.callback = callback


class FakeWidget:
    def __init__(self, *args, **kwargs):
        self.value = args[0] if args and isinstance(args[0], str) else ""
        self.tooltip = ""
        self._blocked = False
        self._layout = SimpleNamespace(addWidget=lambda *a: None)
        self.timeout = FakeSignal()

    def layout(self):
        return self._layout

    def setText(self, text):
        self.value = text

    def text(self):
        return self.value

    def setCurrentText(self, text):
        self.value = text

    def currentText(self):
        return self.value

    def itemText(self, index):
        return str(index)

    def count(self):
        return 121

    def removeItem(self, index):
        pass

    def blockSignals(self, blocked):
        previous, self._blocked = self._blocked, blocked
        return previous

    def setToolTip(self, text):
        self.tooltip = text

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class FakeTimer(FakeWidget):
    @staticmethod
    def singleShot(*args):
        pass


class HookIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(
            prefix="umbra-hook-test-", dir=str(Path(__file__).resolve().parent))
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.devices = []
        devices = self.devices

        class FakeHidDevice:
            def __init__(self, *args, **kwargs):
                self.writes = []
                self.reads = []
                devices.append(self)

            def open(self, *args, **kwargs):
                return None

            def open_path(self, *args, **kwargs):
                return None

            def write(self, report):
                self.writes.append(list(report))
                return 65

            def read(self, *args, **kwargs):
                return self.reads.pop(0) if self.reads else []

            def close(self):
                return None

        hid = ModuleType("hid")
        hid.device = FakeHidDevice
        hid.enumerate = lambda *a, **k: [{"path": b"fake-fe04", "vendor_id": 0x1A86,
                                        "product_id": 0xFE04, "interface_number": 0}]
        qtcore, qtwidgets, pyside = (ModuleType(name) for name in
                                      ("PySide2.QtCore", "PySide2.QtWidgets", "PySide2"))
        qtcore.QTimer = FakeTimer
        qtwidgets.QLabel = FakeWidget
        qtwidgets.QApplication = SimpleNamespace(instance=lambda: SimpleNamespace(quit=lambda: None))
        pyside.QtCore, pyside.QtWidgets = qtcore, qtwidgets
        self.module_patch = patch.dict(sys.modules, {"hid": hid, "PySide2": pyside,
                                                    "PySide2.QtCore": qtcore,
                                                    "PySide2.QtWidgets": qtwidgets})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.environment_patch = patch.dict(os.environ, {"UMBRA_RGB_DRY_RUN": "0"})
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        original_builder, original_exception = builtins.__build_class__, sys.excepthook
        self.addCleanup(setattr, builtins, "__build_class__", original_builder)
        self.addCleanup(setattr, sys, "excepthook", original_exception)
        hook_path = self.folder / "hook.py"
        hook_path.write_text((ROOT / "umbra_rgb_diagnostic_hook.py").read_text(encoding="utf-8"),
                             encoding="utf-8")
        (self.folder / "jonsbo_compatibility.py").write_text(
            (ROOT / "jonsbo_compatibility.py").read_text(encoding="utf-8"), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("offline_umbra_hook", str(hook_path))
        self.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hook)
        self.hook.install()
        self.hid = hid
        self.transport = hid.device()
        self.transport.open(0x1A86, 0xFE04)
        self.inner = self.devices[-1]

    def make_window(self):
        port = SimpleNamespace(ARGB_ser=self.transport, ARGB_TEN_NUM=list(COUNTS),
                               ARGB_TEN_NUM_LEIXING=list(COUNTS),
                               sum_list_device=[sum(COUNTS[:i + 1]) for i in range(10)],
                               sum_list_device_jingxi=[sum(COUNTS[:i + 1]) for i in range(10)])
        agreement = SimpleNamespace(ARGB_dan_config=lambda ser, p, f, n:
                                    ser.write(native_report([2, p, f, n])))
        namespace = {"__name__": "__main__", "port": port,
                     "agreement": agreement, "FakeWidget": FakeWidget}
        exec('''class MainWindow:
    def __init__(self):
        self.fan_ten_stata = 0
        self.ARGB_settings_box_number = FakeWidget("0")
        self.ARGB_number_lable = FakeWidget("LED Count")
        self.yingjian_group = FakeWidget()
        self.yingjian_info_group = FakeWidget()
        self.fan_config_widget = FakeWidget()
    def setWindowTitle(self, value):
        self.title = value
    def fan_set_config(self, index):
        self.ARGB_settings_box_number.setCurrentText(str(port.ARGB_TEN_NUM[index]))
    def on_ARGB_settings_box_number_selected(self, index):
        count = int(self.ARGB_settings_box_number.itemText(index))
        agreement.ARGB_dan_config(port.ARGB_ser, self.fan_ten_stata, 0, count)
''', namespace)
        return namespace["MainWindow"](), port

    def test_first_effect_gets_fd01_prelude_once_and_exact_original(self):
        effect = native_report([3, 0xFD, 0] + list(range(52)))
        original = effect[:]
        self.transport.write(effect)
        self.transport.write(effect)
        self.assertEqual(self.inner.writes,
                         [native_report([0xFD, 1]), original, original])
        self.assertEqual(effect, original)

    def test_manual_count_preview_requires_handover_again(self):
        effect = native_report([3, 0xFD, 0] + [0] * 52)
        self.transport.write(effect)
        self.inner.writes[:] = []
        window, port = self.make_window()
        window.on_ARGB_settings_box_number_selected(24)
        self.transport.write(effect)
        self.assertEqual(self.inner.writes,
                         [native_report([2, 0, 0, 24]), native_report([0xFD, 1]), effect])
        self.assertEqual(port.ARGB_TEN_NUM, COUNTS,
                         "Pending manual profile must not invent hardware registration")

    def test_no_startup_count_replay_and_profile_survives_shutdown(self):
        window, port = self.make_window()
        self.assertEqual(self.inner.writes, [])
        window.on_ARGB_settings_box_number_selected(24)
        self.transport.close()
        self.assertEqual(self.inner.writes, [native_report([2, 0, 0, 24])])
        saved = list(self.folder.glob("*.json"))
        self.assertTrue(saved, "Explicit selection must persist its profile")
        self.assertEqual(port.ARGB_TEN_NUM, COUNTS)

    def test_forbidden_writes_remain_blocked(self):
        for command in (0xFB, 0xFA, 0xFC, 7, 0x0B, 0x0C):
            self.transport.write(native_report([command, 1]))
        self.assertEqual(self.inner.writes, [])

    def test_real_topology_clears_pending_without_mutation_or_host_writes(self):
        window, port = self.make_window()
        window.on_ARGB_settings_box_number_selected(24)
        self.inner.writes[:] = []
        data = [82, 66, 57, 0, 1, 255]
        for index, count in enumerate(COUNTS):
            data.extend([count, 0, 1, index, 0])
        data.extend([2, 253, 0, 0, 0, 0, 0, 0])
        original = data[:]
        self.inner.reads.append(data)
        self.assertEqual(self.transport.read(64), original)
        self.assertTrue(self.hook.PROFILE.pending_activation)
        self.assertEqual(self.hook.PROFILE.hardware_counts, tuple(COUNTS))
        self.assertEqual(port.ARGB_TEN_NUM, COUNTS)
        self.assertEqual(self.inner.writes, [])
        matching = data[:]
        matching[6] = 24
        self.inner.reads.append(matching)
        self.transport.read(64)
        self.assertFalse(self.hook.PROFILE.pending_activation)
        self.assertEqual(self.inner.writes, [])

    def test_desired_manual_field_remains_separate_from_hardware_count(self):
        window, port = self.make_window()
        self.hook.PROFILE.observe_topology(COUNTS)
        self.hook.PROFILE.select_count(24)
        window.fan_set_config(0)
        self.assertEqual(window.ARGB_settings_box_number.currentText(), "24")
        self.assertEqual(port.ARGB_TEN_NUM[0], 0)
        self.assertIn("target 24 / active 0", window.addon_status_label.text())
        self.assertFalse(window.ARGB_settings_box_number._blocked)
        window.fan_set_config(1)
        self.assertEqual(window.ARGB_settings_box_number.currentText(), "48")
        self.assertEqual(port.ARGB_TEN_NUM, COUNTS)
        self.assertEqual(self.inner.writes, [])

    def test_no_profile_keeps_real_dropdown_and_never_saves_default(self):
        window, port = self.make_window()
        port.ARGB_TEN_NUM[0] = 12
        counts = list(COUNTS)
        counts[0] = 12
        self.hook.PROFILE.observe_topology(counts)
        window.fan_set_config(0)
        self.assertEqual(window.ARGB_settings_box_number.currentText(), "12")
        self.assertIn("manual profile not selected", window.addon_status_label.text())
        self.assertIn("active 12", window.addon_status_label.text())
        self.assertEqual(window.title, "UMBRA - RGB Add-on")
        self.assertFalse(self.hook.PROFILE.explicit_selection)
        self.assertFalse(self.hook.PROFILE.pending_activation)
        self.assertFalse((self.folder / "manual-led-profile.json").exists())
        self.assertEqual(self.inner.writes, [])

    def test_only_port_one_explicit_count_writes_are_allowed(self):
        window, port = self.make_window()
        window.fan_ten_stata = 1
        window.on_ARGB_settings_box_number_selected(12)
        for body in ([2, 1, 0, 12], [2, 0, 1, 12], [2, 0, 0, 101]):
            self.transport.write(native_report(body))
        self.assertEqual(self.inner.writes, [])
        self.assertFalse(self.hook.PROFILE.explicit_selection)
        for count in (0, 100):
            self.transport.write(native_report([2, 0, 0, count]))
        self.assertEqual(self.inner.writes,
                         [native_report([2, 0, 0, 0]), native_report([2, 0, 0, 100])])

    def test_other_hubs_and_feature_writes_are_rejected(self):
        other = self.hid.device()
        with self.assertRaises(OSError):
            other.open(0x1A86, 0xFE05)
        with self.assertRaises(OSError):
            other.open_path(b"other-device-path")
        other.write(native_report([2, 0, 0, 12]))
        self.assertEqual(self.devices[-1].writes, [])
        with self.assertRaises(OSError):
            self.transport.send_feature_report([0, 0])
        self.assertEqual(self.inner.writes, [])

    def test_packet_gate_rejects_malformed_framing(self):
        valid = native_report([2, 0, 0, 12])
        for malformed in (None, [], valid + [0], valid[:-1],
                          valid[:-1] + [(valid[-1] + 1) % 256],
                          [True] + valid[1:], ["0"] + valid[1:],
                          [-1] + valid[1:]):
            self.assertFalse(self.hook.permitted(malformed))
        stream = [0, 0x88, 1, 1] + [0] * 60
        stream.append(sum(stream[1:]) % 256)
        self.assertTrue(self.hook.permitted(stream))
        stream[64] ^= 1
        self.assertFalse(self.hook.permitted(stream))

    def test_public_logs_do_not_include_usb_path_or_identity_data(self):
        self.transport.open_path(b"fake-fe04")
        identity = [82, 66, 14, 0, 0] + [199] * 59
        self.inner.reads.append(identity)
        self.assertEqual(self.transport.read(64), identity)
        with open(self.hook.LOG_PATH, encoding="utf-8") as stream:
            log = stream.read()
        self.assertNotIn("fake-fe04", log)
        self.assertNotIn("199", log)

    def test_vendor_helper_patch_preserves_rgb_function(self):
        source = compile('''def install_pawnio_signed():
    raise RuntimeError("must not run")
def on_ARGB_settings_box_number_selected(index):
    return index + 1
''', "<offline-stub>", "exec")
        patched = self.hook.patch_code(source)
        namespace = {}
        exec(patched, namespace)
        self.assertIsNone(namespace["install_pawnio_signed"]())
        self.assertEqual(namespace["on_ARGB_settings_box_number_selected"](4), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
