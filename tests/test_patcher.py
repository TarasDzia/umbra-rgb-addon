"""Patcher tests use synthetic archives only; they never load Umbra or HID."""
import base64
import builtins
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib


PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("umbra_addon_patcher_under_test", PROJECT / "patcher.py")
patcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = patcher
SPEC.loader.exec_module(patcher)

# These bytes describe the documented CArchive structure independently of the
# parser's constants. They contain no marshalled code and are never executed.
MAGIC = b"MEI\x0c\x0b\x0a\x0b\x0e"
COOKIE = struct.Struct("!8sIIII64s")
TOC = struct.Struct("!IIIIBc")
ORIGINAL_MAIN = b"synthetic main bytecode, deliberately not executable"
BOOTSTRAP = b"synthetic add-on bootstrap, deliberately not executable"


def fixture(entries=None, prefix=b"MZ synthetic bootloader\x00", version=308,
            library=b"python38.dll"):
    if entries is None:
        entries = [
            ("support", b"compressed support module", 1, b"m"),
            ("Sync_light", ORIGINAL_MAIN, 1, b"s"),
            ("data/assets.bin", b"\x00\x01\xffunchanged", 0, b"x"),
        ]
    body, table = bytearray(), bytearray()
    for name, raw, compressed, kind in entries:
        encoded = zlib.compress(raw, 1) if compressed else raw
        label = name.encode("utf-8") + b"\0"
        size = (TOC.size + len(label) + 15) // 16 * 16
        table.extend(TOC.pack(size, len(body), len(encoded), len(raw), compressed, kind))
        table.extend(label + bytes(size - TOC.size - len(label)))
        body.extend(encoded)
    archive_size = len(body) + len(table) + COOKIE.size
    return prefix + body + table + COOKIE.pack(
        MAGIC, archive_size, len(body), len(table), version, library)


def cookie_fields(data):
    return list(COOKIE.unpack_from(data, len(data) - COOKIE.size))


def with_cookie(data, field, value):
    fields = cookie_fields(data)
    fields[field] = value
    return data[:-COOKIE.size] + COOKIE.pack(*fields)


def toc_start(data):
    fields = cookie_fields(data)
    return len(data) - fields[1] + fields[2]


def with_toc_field(data, field, value):
    changed = bytearray(data)
    offset = toc_start(data)
    fields = list(TOC.unpack_from(changed, offset))
    fields[field] = value
    changed[offset:offset + TOC.size] = TOC.pack(*fields)
    return bytes(changed)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def test_parse_returns_archive_without_executing_payloads(self):
        archive = patcher.parse_archive(self.data)
        self.assertEqual(archive.prefix, b"MZ synthetic bootloader\x00")
        self.assertEqual(archive.python_version, 308)
        self.assertEqual([entry.name for entry in archive.entries],
                         ["support", "Sync_light", "data/assets.bin"])

    def test_import_does_not_require_vendor_gui_hid_or_marshal(self):
        original_import = builtins.__import__
        forbidden = {"hid", "PySide2", "PySide6", "PyInstaller", "Sync_light", "marshal"}
        def restricted_import(name, *args, **kwargs):
            if name.split(".")[0] in forbidden:
                raise AssertionError("Patcher must not import " + name)
            return original_import(name, *args, **kwargs)
        spec = importlib.util.spec_from_file_location("umbra_addon_no_vendor_imports", PROJECT / "patcher.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            with mock.patch.object(builtins, "__import__", restricted_import):
                spec.loader.exec_module(module)
                module.repack_archive(self.data, BOOTSTRAP)
        finally:
            sys.modules.pop(spec.name, None)

    def test_repack_changes_only_main_payload_and_keeps_other_stored_bytes(self):
        patched, original = patcher.repack_archive(self.data, BOOTSTRAP)
        before = patcher.parse_archive(self.data)
        after = patcher.parse_archive(patched)
        self.assertEqual(original, ORIGINAL_MAIN)
        self.assertEqual(before.prefix, after.prefix)
        self.assertEqual(before.python_version, after.python_version)
        self.assertEqual(before.library, after.library)
        for old, new in zip(before.entries, after.entries):
            if old.name == "Sync_light":
                self.assertEqual(zlib.decompress(new.payload), BOOTSTRAP)
                self.assertEqual(new.raw_size, len(BOOTSTRAP))
                self.assertEqual(new.kind, b"s")
                self.assertEqual(new.compressed, 1)
            else:
                self.assertEqual(new, old)

    def test_uncompressed_main_is_preserved_as_original(self):
        data = fixture([("Sync_light", ORIGINAL_MAIN, 0, b"s")])
        patched, original = patcher.repack_archive(data, BOOTSTRAP)
        self.assertEqual(original, ORIGINAL_MAIN)
        self.assertEqual(zlib.decompress(patcher.parse_archive(patched).entries[0].payload), BOOTSTRAP)

    def test_trailing_certificate_is_accepted_then_dropped_from_modified_copy(self):
        patched, original = patcher.repack_archive(self.data + b"synthetic certificate", BOOTSTRAP)
        self.assertEqual(original, ORIGINAL_MAIN)
        self.assertEqual(patched, patcher.repack_archive(self.data, BOOTSTRAP)[0])

    def test_missing_and_truncated_cookies_are_rejected(self):
        for data in (b"", b"MZ not an archive", self.data[:-1], self.data[:-64], MAGIC):
            with self.subTest(length=len(data)):
                self.assertRaises(patcher.PatchError, patcher.parse_archive, data)

    def test_cookie_bounds_are_rejected(self):
        fields = cookie_fields(self.data)
        for field, value in ((1, 1), (1, len(self.data) + 1),
                             (2, fields[1]), (3, fields[3] + 1), (3, fields[3] - 1)):
            with self.subTest(field=field, value=value):
                self.assertRaises(patcher.PatchError, patcher.parse_archive,
                                  with_cookie(self.data, field, value))

    def test_toc_and_payload_bounds_are_rejected(self):
        for field, value in ((0, 0), (0, TOC.size), (0, len(self.data)),
                             (1, len(self.data)), (2, len(self.data)), (4, 2)):
            with self.subTest(field=field, value=value):
                self.assertRaises(patcher.PatchError, patcher.parse_archive,
                                  with_toc_field(self.data, field, value))

    def test_names_require_null_terminator_and_zero_padding(self):
        start = toc_start(self.data)
        entry_size = TOC.unpack_from(self.data, start)[0]
        invalid = bytearray(self.data)
        invalid[start + TOC.size:start + entry_size] = b"a" * (entry_size - TOC.size)
        self.assertRaises(patcher.PatchError, patcher.parse_archive, bytes(invalid))
        invalid = bytearray(self.data)
        invalid[start + entry_size - 1] = 1
        self.assertRaises(patcher.PatchError, patcher.parse_archive, bytes(invalid))

    def test_empty_invalid_utf8_and_duplicate_names_are_rejected(self):
        duplicate = fixture([("Sync_light", ORIGINAL_MAIN, 0, b"s"),
                             ("Sync_light", b"duplicate", 0, b"s")])
        self.assertRaises(patcher.PatchError, patcher.parse_archive, duplicate)
        for value in (0, 255):
            invalid = bytearray(self.data)
            invalid[toc_start(self.data) + TOC.size] = value
            self.assertRaises(patcher.PatchError, patcher.parse_archive, bytes(invalid))

    def test_uncompressed_size_mismatch_is_rejected(self):
        data = fixture([("Sync_light", ORIGINAL_MAIN, 0, b"s")])
        self.assertRaises(patcher.PatchError, patcher.parse_archive,
                          with_toc_field(data, 3, len(ORIGINAL_MAIN) + 1))

    def test_missing_main_wrong_kind_and_wrong_runtime_are_rejected(self):
        candidates = [fixture([("other", b"data", 0, b"s")]),
                      fixture([("Sync_light", ORIGINAL_MAIN, 0, b"m")]),
                      fixture(version=309), fixture(library=b"python39.dll")]
        for data in candidates:
            with self.subTest(data=data[-72:]):
                self.assertRaises(patcher.PatchError, patcher.parse_archive, data)

    def test_corrupt_compressed_main_and_wrong_raw_size_are_rejected(self):
        data = fixture([("Sync_light", ORIGINAL_MAIN, 1, b"s")])
        invalid = bytearray(data)
        invalid[len(b"MZ synthetic bootloader\x00")] ^= 255
        self.assertRaises(patcher.PatchError, patcher.repack_archive, bytes(invalid), BOOTSTRAP)
        self.assertRaises(patcher.PatchError, patcher.repack_archive,
                          with_toc_field(data, 3, len(ORIGINAL_MAIN) + 1), BOOTSTRAP)
        self.assertRaises(patcher.PatchError, patcher.repack_archive,
                          with_toc_field(data, 3, 64 * 1024 * 1024 + 1), BOOTSTRAP)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="umbra-addon-test-", dir=PROJECT)
        self.assertEqual(Path(self.temporary.name).resolve().parent, PROJECT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "vendor"
        self.source.mkdir()
        self.data = fixture()
        (self.source / patcher.SOURCE_EXE).write_bytes(self.data)
        (self.source / "python38.dll").write_bytes(b"synthetic local runtime")
        (self.source / "base_library.zip").write_bytes(b"synthetic standard library")
        (self.source / "PySide2").mkdir()
        (self.source / "shiboken2").mkdir()
        (self.source / "assets").mkdir()
        (self.source / "assets" / "icon.bin").write_bytes(b"synthetic local asset")
        self.addon = self.root / "addon-source"
        (self.addon / "payload").mkdir(parents=True)
        for name in patcher.PAYLOAD_FILES:
            (self.addon / "payload" / name).write_bytes(("# authored " + name).encode("ascii"))
        self.destination = self.root / "installed-copy"
        self.settings = mock.patch.multiple(patcher, ROOT=self.addon,
                                            SUPPORTED_SHA256=hashlib.sha256(self.data).hexdigest())
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.bootstrap = mock.patch.object(patcher, "load_bootstrap", return_value=BOOTSTRAP)
        self.bootstrap.start()
        self.addCleanup(self.bootstrap.stop)

    def test_unknown_executable_hash_fails_before_creating_destination(self):
        with mock.patch.object(patcher, "SUPPORTED_SHA256", "0" * 64):
            self.assertRaises(patcher.PatchError, patcher.install_addon, self.source, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual((self.source / patcher.SOURCE_EXE).read_bytes(), self.data)

    def test_known_hash_still_requires_valid_archive(self):
        invalid = b"known hash cannot bypass parser"
        (self.source / patcher.SOURCE_EXE).write_bytes(invalid)
        with mock.patch.object(patcher, "SUPPORTED_SHA256", hashlib.sha256(invalid).hexdigest()):
            self.assertRaises(patcher.PatchError, patcher.install_addon, self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_runtime_is_rejected_before_creating_destination(self):
        (self.source / "base_library.zip").unlink()
        self.assertRaises(patcher.PatchError, patcher.install_addon, self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_missing_source_or_main_is_rejected_without_output(self):
        for source in (self.root / "missing", self.source / "assets"):
            self.assertRaises(patcher.PatchError, patcher.install_addon, source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_existing_destination_is_never_overwritten(self):
        self.destination.mkdir()
        marker = self.destination / "keep.txt"
        marker.write_bytes(b"keep me")
        self.assertRaises(patcher.PatchError, patcher.install_addon, self.source, self.destination)
        self.assertEqual(marker.read_bytes(), b"keep me")
        self.assertEqual(list(self.destination.iterdir()), [marker])

    def test_source_destination_and_addon_paths_must_be_disjoint(self):
        candidates = [self.source, self.source / "nested", self.root,
                      self.addon / "generated"]
        for destination in candidates:
            with self.subTest(destination=destination):
                self.assertRaises(patcher.PatchError, patcher.install_addon, self.source, destination)
        self.assertFalse((self.source / "nested").exists())
        self.assertFalse((self.addon / "generated").exists())

    def test_destination_parent_must_exist(self):
        destination = self.root / "missing-parent" / "installed-copy"
        self.assertRaises(patcher.PatchError, patcher.install_addon, self.source, destination)
        self.assertFalse(destination.parent.exists())

    def test_bad_bootstrap_fails_before_creating_destination(self):
        with mock.patch.object(patcher, "load_bootstrap", side_effect=patcher.PatchError("invalid bootstrap")):
            self.assertRaises(patcher.PatchError, patcher.install_addon, self.source, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual((self.source / patcher.SOURCE_EXE).read_bytes(), self.data)

    def test_nested_stale_state_is_not_copied(self):
        (self.source / "assets" / "old.log").write_bytes(b"private old log")
        cache = self.source / "assets" / "__pycache__"
        cache.mkdir()
        (cache / "old.pyc").write_bytes(b"private old bytecode")
        patcher.install_addon(self.source, self.destination)
        self.assertFalse((self.destination / "assets" / "old.log").exists())
        self.assertFalse((self.destination / "assets" / "__pycache__").exists())

    def test_install_keeps_original_unchanged_and_copies_only_local_runtime_plus_addon(self):
        for name in ("jonsbo-profile.json", "manual-led-profile.json", "rgb-diagnostic.jsonl", "unins000.exe",
                     "compatibility-old.json", "stale.pyc", "private.log"):
            (self.source / name).write_bytes(b"private stale state")
        manifest = patcher.install_addon(self.source, self.destination)
        self.assertEqual((self.source / patcher.SOURCE_EXE).read_bytes(), self.data)
        self.assertEqual((self.destination / "python38.dll").read_bytes(), b"synthetic local runtime")
        self.assertEqual((self.destination / "assets" / "icon.bin").read_bytes(), b"synthetic local asset")
        self.assertEqual((self.destination / "Sync_light.original.marshal").read_bytes(), ORIGINAL_MAIN)
        self.assertFalse((self.destination / patcher.SOURCE_EXE).exists())
        self.assertFalse((self.destination / "jonsbo-profile.json").exists())
        self.assertFalse((self.destination / "manual-led-profile.json").exists())
        self.assertFalse((self.destination / "unins000.exe").exists())
        self.assertFalse((self.destination / "rgb-diagnostic.jsonl").exists())
        for name in patcher.PAYLOAD_FILES:
            self.assertEqual((self.destination / name).read_bytes(),
                             (self.addon / "payload" / name).read_bytes())
        self.assertFalse(manifest["count_written_to_hub"])
        self.assertTrue(manifest["rgb_only"])
        self.assertEqual(json.loads((self.destination / "addon-install.json").read_text()), manifest)
        self.assertEqual(manifest["patched_sha256"],
                         hashlib.sha256((self.destination / patcher.OUTPUT_EXE).read_bytes()).hexdigest())

    def test_runtime_link_is_rejected_before_destination_creation(self):
        original = Path.is_symlink
        def pretend_link(path):
            return path == self.source / "python38.dll" or original(path)
        with mock.patch.object(Path, "is_symlink", pretend_link):
            self.assertRaises(patcher.PatchError, patcher.install_addon, self.source, self.destination)
        self.assertFalse(self.destination.exists())


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="umbra-bootstrap-test-", dir=PROJECT)
        self.assertEqual(Path(self.temporary.name).resolve().parent, PROJECT)
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = b"# synthetic authored source\n"
        (self.folder / "bootstrap.py").write_bytes(self.source)
        (self.folder / "bootstrap38.b64").write_bytes(base64.b64encode(BOOTSTRAP) + b"\n")
        self.metadata = {"python": [3, 8], "marshal_version": 4,
                         "payload_sha256": hashlib.sha256(BOOTSTRAP).hexdigest(),
                         "source_sha256": hashlib.sha256(self.source).hexdigest()}
        self.write_metadata()

    def write_metadata(self):
        (self.folder / "bootstrap38.json").write_text(json.dumps(self.metadata), encoding="utf-8")

    def test_integrity_checked_bytes_are_returned_without_unmarshalling(self):
        self.assertEqual(patcher.load_bootstrap(self.folder), BOOTSTRAP)

    def test_wrong_python_or_marshal_version_is_rejected(self):
        for key, value in (("python", [3, 9]), ("marshal_version", 5)):
            with self.subTest(key=key), mock.patch.dict(self.metadata, {key: value}):
                self.write_metadata()
                self.assertRaises(patcher.PatchError, patcher.load_bootstrap, self.folder)

    def test_changed_source_payload_or_invalid_encoding_is_rejected(self):
        (self.folder / "bootstrap.py").write_bytes(b"tampered source")
        self.assertRaises(patcher.PatchError, patcher.load_bootstrap, self.folder)
        (self.folder / "bootstrap.py").write_bytes(self.source)
        (self.folder / "bootstrap38.b64").write_bytes(base64.b64encode(b"tampered payload"))
        self.assertRaises(patcher.PatchError, patcher.load_bootstrap, self.folder)
        (self.folder / "bootstrap38.b64").write_bytes(b"%%% invalid %%%")
        self.assertRaises(patcher.PatchError, patcher.load_bootstrap, self.folder)


if __name__ == "__main__":
    unittest.main()
