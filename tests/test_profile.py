"""Offline unit tests. No vendor app import and no HID library are needed."""
import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "payload"))

from jonsbo_compatibility import (
    CompatibilityProfile, NativeModeNormalizer, native_body, native_report,
)


TOPOLOGY = [0, 48, 72, 0, 48, 0, 0, 0, 0, 0]


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(
            prefix="umbra-profile-test-", dir=str(Path(__file__).resolve().parent))
        self.addCleanup(self.directory.cleanup)
        self.path = os.path.join(self.directory.name, "manual-led-profile.json")

    def test_default_has_no_disk_or_hardware_side_effect(self):
        profile = CompatibilityProfile(self.path)
        self.assertEqual(profile.desired_count, 0)
        self.assertFalse(profile.pending_activation)
        self.assertFalse(profile.explicit_selection)
        self.assertFalse(os.path.exists(self.path))

    def test_manual_selection_persists_across_restart(self):
        profile = CompatibilityProfile(self.path)
        profile.select_count(7)
        restored = CompatibilityProfile(self.path)
        self.assertEqual(restored.desired_count, 7)
        self.assertTrue(restored.explicit_selection)
        self.assertTrue(restored.pending_activation)
        with open(self.path, encoding="utf-8") as stream:
            self.assertEqual(json.load(stream),
                             {"schema": 1, "port": 0, "led_count": 7})

    def test_only_real_matching_topology_clears_pending(self):
        profile = CompatibilityProfile(self.path)
        profile.select_count(24)
        profile.observe_topology(TOPOLOGY)
        effective = profile.effective_counts()
        effective[0] = 99
        self.assertEqual(profile.hardware_counts, tuple(TOPOLOGY))
        self.assertTrue(profile.pending_activation)
        matching = list(TOPOLOGY)
        matching[0] = 24
        profile.observe_topology(matching)
        matching[0] = 0
        self.assertFalse(profile.pending_activation)
        self.assertEqual(profile.hardware_counts[0], 24)
        profile.observe_topology(TOPOLOGY)
        self.assertTrue(profile.pending_activation)

    def test_topology_and_cache_updates_do_not_persist_or_confirm(self):
        profile = CompatibilityProfile(self.path)
        hardware = list(TOPOLOGY)
        profile.observe_topology(hardware)
        cache = profile.effective_counts()
        self.assertEqual(cache[0], 0)
        self.assertEqual(hardware, TOPOLOGY)
        self.assertFalse(profile.pending_activation)
        self.assertFalse(os.path.exists(self.path))

    def test_manual_count_limits_match_vendor_ui(self):
        profile = CompatibilityProfile(self.path)
        for count in (0, 1, 24, 100):
            profile.select_count(count)
            self.assertEqual(profile.desired_count, count)
        for count in (-1, 101, 120, True, "24", None, 24.0):
            with self.assertRaises(ValueError):
                profile.select_count(count)

    def test_bad_or_wrong_port_profile_is_not_silently_accepted(self):
        with open(self.path, "w", encoding="utf-8") as stream:
            json.dump({"schema": 1, "port": 1, "led_count": 24}, stream)
        with self.assertRaises(ValueError):
            CompatibilityProfile(self.path)


class NativeModeTests(unittest.TestCase):
    def setUp(self):
        self.mode = NativeModeNormalizer()
        self.effect = native_report([3, 0xFD, 0] + list(range(52)))
        self.mode_report = [0, 82, 66, 7, 0, 253, 1, 153]

    def test_fd01_once_before_first_effect_original_unchanged(self):
        original = self.effect[:]
        self.assertEqual(self.mode.before(self.effect), self.mode_report)
        self.assertEqual(self.effect, original)
        self.mode.accepted(self.mode_report)
        self.mode.accepted(self.effect)
        self.assertIsNone(self.mode.before(self.effect))
        self.assertEqual(self.effect, original)

    def test_failed_prelude_is_retryable_and_open_resets_mode(self):
        self.assertEqual(self.mode.before(self.effect), self.mode_report)
        self.assertEqual(self.mode.before(self.effect), self.mode_report)
        self.mode.accepted(self.mode_report)
        self.mode.opened()
        self.assertEqual(self.mode.before(self.effect), self.mode_report)

    def test_count_preview_requires_new_handover_without_count_replay(self):
        self.mode.accepted(self.mode_report)
        preview = native_report([2, 0, 0, 24])
        self.assertIsNone(self.mode.before(preview))
        self.mode.accepted(preview)
        self.assertEqual(self.mode.before(self.effect), self.mode_report)
        self.assertEqual(native_body(self.mode.before(self.effect)), [0xFD, 1])

    def test_no_forbidden_or_automatic_motherboard_mode_writes(self):
        for command in (0xFB, 0xFA, 0xFC, 7, 0x0B, 0x0C):
            report = native_report([command, 1])
            self.assertIsNone(self.mode.before(report))
            self.mode.accepted(report)
        self.assertIsNone(self.mode.before(native_report([0xFD, 0])))
        self.assertEqual(native_body(self.mode.before(self.effect)), [0xFD, 1])

    def test_invalid_effect_never_gets_prelude(self):
        for malformed in (None, [], self.effect[:-1],
                          self.effect[:-1] + [(self.effect[-1] + 1) % 256],
                          native_report([3, 0xFD, 0] + [0] * 51)):
            self.assertIsNone(self.mode.before(malformed))


if __name__ == "__main__":
    unittest.main(verbosity=2)
