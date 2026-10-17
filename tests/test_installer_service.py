"""Installer planning uses synthetic local files and never starts Umbra or HID."""
import builtins
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import installer_service as service
import patcher
from test_patcher import BOOTSTRAP, ORIGINAL_MAIN, fixture


def snapshot(folder):
    return {str(path.relative_to(folder)): path.read_bytes() if path.is_file() else None
            for path in folder.rglob("*")}


class InstallerServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="umbra-installer-test-", dir=PROJECT)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "original application"
        self.source.mkdir()
        self.data = fixture()
        (self.source / patcher.SOURCE_EXE).write_bytes(self.data)
        (self.source / "python38.dll").write_bytes(b"local vendor runtime")
        (self.source / "base_library.zip").write_bytes(b"local standard library")
        (self.source / "PySide2").mkdir()
        (self.source / "shiboken2").mkdir()
        self.addon = self.root / "addon"
        (self.addon / "payload").mkdir(parents=True)
        for name in patcher.PAYLOAD_FILES:
            (self.addon / "payload" / name).write_bytes(("# " + name).encode("ascii"))
        self.destination = self.root / "new parent" / "installed copy"
        settings = mock.patch.multiple(patcher, ROOT=self.addon,
                                       SUPPORTED_SHA256=hashlib.sha256(self.data).hexdigest())
        settings.start()
        self.addCleanup(settings.stop)
        bootstrap = mock.patch.object(patcher, "load_bootstrap", return_value=BOOTSTRAP)
        bootstrap.start()
        self.addCleanup(bootstrap.stop)

    def validate(self):
        return service.validate_selection(str(self.source), str(self.destination))

    def assert_preflight_failure(self, expected=patcher.PatchError):
        before = snapshot(self.root)
        with self.assertRaises(expected):
            self.validate()
        self.assertEqual(snapshot(self.root), before)

    def test_normalize_accepts_folder_and_quoted_executable(self):
        candidates = [str(self.source), ' "' + str(self.source) + '" ',
                      str(self.source / patcher.SOURCE_EXE),
                      "'" + str(self.source / patcher.SOURCE_EXE) + "'"]
        for value in candidates:
            with self.subTest(value=value):
                self.assertEqual(service.normalize_source(value), self.source.resolve())

    def test_blank_or_non_path_selections_are_rejected(self):
        for value in ("", "  ", '""', "''", None):
            with self.subTest(value=value):
                self.assertRaises(patcher.PatchError, service.normalize_source, value)
                self.assertRaises(patcher.PatchError, service.validate_selection, self.source, value)

    def test_default_destination_is_per_user_unique_and_read_only(self):
        local = self.root / "local app data"
        before = snapshot(self.root)
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)}):
            base = service.default_destination()
            self.assertEqual(base, local / "UmbraRGBAddon" / "v0.2.0")
            self.assertEqual(snapshot(self.root), before)
            base.mkdir(parents=True)
            base.with_name(base.name + "-2").write_bytes(b"occupied by a file")
            before = snapshot(self.root)
            self.assertEqual(service.default_destination(), base.with_name(base.name + "-3"))
            self.assertEqual(snapshot(self.root), before)

    def test_default_destination_has_read_only_home_fallback(self):
        before = snapshot(self.root)
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(Path, "home", return_value=self.root):
            self.assertEqual(service.default_destination(),
                             self.root / "AppData" / "Local" / "UmbraRGBAddon" / "v0.2.0")
        self.assertEqual(snapshot(self.root), before)

    def test_validation_allows_missing_parent_without_creating_anything(self):
        before = snapshot(self.root)
        plan = self.validate()
        self.assertEqual(plan, service.InstallPlan(self.source.resolve(), self.destination.resolve()))
        self.assertEqual(snapshot(self.root), before)

    def test_unknown_vendor_and_missing_runtime_fail_without_source_or_output_changes(self):
        with mock.patch.object(patcher, "SUPPORTED_SHA256", "0" * 64):
            self.assert_preflight_failure()
        (self.source / "base_library.zip").unlink()
        self.assert_preflight_failure()

    def test_bootstrap_and_payload_failures_do_not_create_output_parent(self):
        with mock.patch.object(patcher, "load_bootstrap", side_effect=patcher.PatchError("bad bootstrap")):
            self.assert_preflight_failure()
        (self.addon / "payload" / patcher.PAYLOAD_FILES[0]).unlink()
        self.assert_preflight_failure(FileNotFoundError)

    def test_invalid_archive_with_known_hash_is_still_rejected(self):
        invalid = b"not a vendor archive"
        (self.source / patcher.SOURCE_EXE).write_bytes(invalid)
        with mock.patch.object(patcher, "SUPPORTED_SHA256", hashlib.sha256(invalid).hexdigest()):
            self.assert_preflight_failure()

    def test_existing_destinations_and_overlapping_paths_are_rejected(self):
        existing = self.root / "existing"
        existing.mkdir()
        (existing / "keep.txt").write_bytes(b"preserve")
        before = snapshot(self.root)
        for destination in (existing, self.source, self.source / "nested",
                            self.root, self.addon / "generated", self.addon):
            with self.subTest(destination=destination):
                self.assertRaises(patcher.PatchError, service.validate_selection,
                                  self.source, destination)
        self.assertEqual(snapshot(self.root), before)

    def test_linked_source_root_source_executable_destination_parent_and_payload_are_rejected(self):
        self.destination.parent.mkdir()
        original_is_symlink = Path.is_symlink
        candidates = [self.source, self.source / patcher.SOURCE_EXE,
                      self.destination.parent, self.addon / "payload" / patcher.PAYLOAD_FILES[0]]
        for linked in candidates:
            def pretend_link(path):
                return path == linked or original_is_symlink(path)
            with self.subTest(linked=linked), mock.patch.object(Path, "is_symlink", pretend_link):
                self.assert_preflight_failure()

    def test_install_creates_missing_parent_only_after_complete_validation(self):
        plan = self.validate()
        original = snapshot(self.source)
        progress = []
        manifest = service.install_selection(plan, lambda stage, message: progress.append((stage, message)))
        self.assertEqual(snapshot(self.source), original)
        self.assertEqual([stage for stage, message in progress], ["validate", "copy", "patch", "complete"])
        self.assertTrue(all(isinstance(message, str) and message for stage, message in progress))
        self.assertTrue((self.destination / patcher.OUTPUT_EXE).is_file())
        self.assertEqual((self.destination / "Sync_light.original.marshal").read_bytes(), ORIGINAL_MAIN)
        self.assertEqual(json.loads((self.destination / "addon-install.json").read_text()), manifest)
        self.assertEqual(manifest["addon_version"], "0.2.0")
        self.assertFalse(manifest["count_written_to_hub"])

    def test_install_revalidates_source_before_creating_missing_parent(self):
        plan = self.validate()
        (self.source / patcher.SOURCE_EXE).write_bytes(b"changed after selection")
        before = snapshot(self.root)
        self.assertRaises(patcher.PatchError, service.install_selection, plan)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(self.destination.parent.exists())

    def test_install_revalidates_bootstrap_and_runtime_before_creating_missing_parent(self):
        plan = self.validate()
        with mock.patch.object(patcher, "load_bootstrap", side_effect=patcher.PatchError("changed bootstrap")):
            self.assertRaises(patcher.PatchError, service.install_selection, plan)
        self.assertFalse(self.destination.parent.exists())
        (self.source / "python38.dll").unlink()
        self.assertRaises(patcher.PatchError, service.install_selection, plan)
        self.assertFalse(self.destination.parent.exists())

    def test_install_never_overwrites_destination_created_after_validation(self):
        plan = self.validate()
        self.destination.mkdir(parents=True)
        marker = self.destination / "keep.txt"
        marker.write_bytes(b"keep")
        before = snapshot(self.root)
        self.assertRaises(patcher.PatchError, service.install_selection, plan)
        self.assertEqual(snapshot(self.root), before)

    def test_install_error_leaves_new_partial_copy_and_original_unchanged(self):
        plan = self.validate()
        original = snapshot(self.source)
        with mock.patch.object(patcher.shutil, "copy2", side_effect=OSError("copy failed")):
            self.assertRaises(OSError, service.install_selection, plan)
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(snapshot(self.source), original)

    def test_gui_parent_creation_does_not_change_cli_contract(self):
        self.assertRaises(patcher.PatchError, patcher.install_addon, self.source, self.destination)
        self.assertFalse(self.destination.parent.exists())

    def test_import_and_validation_do_not_import_vendor_or_hardware_modules(self):
        original_import = builtins.__import__
        forbidden = {"hid", "PySide2", "PySide6", "PyInstaller", "Sync_light", "marshal", "subprocess"}
        def restricted_import(name, *args, **kwargs):
            if name.split(".")[0] in forbidden:
                raise AssertionError("Installer must not import " + name)
            return original_import(name, *args, **kwargs)
        spec = importlib.util.spec_from_file_location("installer_service_no_vendor", PROJECT / "installer_service.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(sys.modules.pop, spec.name, None)
        with mock.patch.object(builtins, "__import__", restricted_import):
            spec.loader.exec_module(module)
            plan = module.validate_selection(self.source, self.destination)
            module.install_selection(plan)


if __name__ == "__main__":
    unittest.main()
