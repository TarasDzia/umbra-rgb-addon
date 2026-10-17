"""Window state checks; no vendor code, device access or real installation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

try:
    import tkinter as tk
    import installer_gui
except ImportError:
    tk = None
    installer_gui = None

import installer_service


@unittest.skipIf(tk is None, "Tk is not installed in this Python runtime")
class InstallerGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest("A desktop display is required: " + str(error))
        self.root.withdraw()
        self.window = installer_gui.InstallerWindow(self.root)

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_install_starts_disabled_until_successful_validation(self):
        self.assertEqual(str(self.window.install_button["state"]), "disabled")
        self.window.operation = "check"
        plan = installer_service.InstallPlan(Path("source"), Path("destination"))
        self.window.events.put(("checked", self.window.revision, plan))
        self.window._drain_events()
        self.assertIs(self.window.plan, plan)
        self.assertEqual(str(self.window.install_button["state"]), "normal")
        self.window.source.set("a different original folder")
        self.assertIsNone(self.window.plan)
        self.assertEqual(str(self.window.install_button["state"]), "disabled")

    def test_outdated_validation_never_enables_installation(self):
        self.window.operation = "check"
        self.window.revision = 2
        plan = installer_service.InstallPlan(Path("source"), Path("destination"))
        self.window.events.put(("checked", 1, plan))
        self.window._drain_events()
        self.assertIsNone(self.window.plan)
        self.assertEqual(str(self.window.install_button["state"]), "disabled")

    def test_enter_shortcut_is_limited_to_path_fields(self):
        self.assertFalse(self.root.bind("<Return>"))
        self.assertTrue(self.window.source_entry.bind("<Return>"))
        self.assertTrue(self.window.destination_entry.bind("<Return>"))

    def test_install_locks_fields_and_uses_only_the_service(self):
        plan = installer_service.InstallPlan(Path("source"), Path("destination"))
        self.window.plan = plan
        with mock.patch.object(installer_gui.threading, "Thread") as thread:
            self.window.install()
        self.assertEqual(self.window.operation, "install")
        for field in self.window.inputs:
            self.assertEqual(str(field["state"]), "disabled")
        worker = thread.call_args.kwargs["target"]
        with mock.patch.object(installer_service, "install_selection", return_value={}) as install:
            worker()
        self.assertEqual(install.call_args.args[0], plan)
        self.assertTrue(callable(install.call_args.kwargs["progress"]))

    def test_success_does_not_start_app_or_open_folder(self):
        self.window.operation = "install"
        self.window.installed_destination = Path("destination")
        with mock.patch.object(installer_gui.os, "startfile", create=True) as start:
            self.window.events.put(("installed", self.window.revision, Path("destination")))
            self.window._drain_events()
        start.assert_not_called()
        self.assertTrue(self.window.completed)
        self.assertEqual(self.window.install_button["text"], "Open folder")
        self.assertIn("manually", self.window.status_body.get())

    def test_install_error_preserves_partial_output_and_unlocks_fields(self):
        self.window.operation = "install"
        self.window.events.put(("failed", self.window.revision, "Access denied"))
        self.window._drain_events()
        self.assertIsNone(self.window.plan)
        self.assertIn("different new folder", self.window.status_body.get())
        for field in self.window.inputs:
            self.assertEqual(str(field["state"]), "normal")

    def test_cannot_close_while_installation_is_running(self):
        self.window.operation = "install"
        with mock.patch.object(installer_gui.messagebox, "showinfo") as info:
            self.window.close()
        info.assert_called_once()
        self.assertFalse(self.window.closed)

    def test_smoke_report_checks_bundled_resources_without_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "smoke.json"
            with mock.patch.object(installer_service, "install_selection") as install:
                code = installer_gui.smoke_test(report)
            self.assertEqual(code, 0)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(data["window_created"])
            self.assertTrue(data["bootstrap_valid"])
            self.assertFalse(data["hardware_accessed"])
            self.assertFalse(data["application_started"])
            install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
