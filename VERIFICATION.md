# Verification — version 0.2.1

Checked on Windows on 2026-10-17.

- 78 tests pass under Python 3.14.7, including eight tests of real Tk widgets.
  Under the portable Python 3.8.10 runtime, 70 tests pass and eight GUI tests
  are skipped because that runtime does not provide Tk.
- Tests cover optional profiles, exact packet gating, mode handover, fake HID/Qt,
  synthetic CArchive bounds, source hash checks, runtime preflight, no overwrite,
  bootstrap integrity, state exclusions, original-file preservation, read-only
  planning, revalidation, stale GUI results, progress, and no automatic launch.
- Three new fake-HID tests verify that `UMBRA_RGB_DRY_RUN=1` never constructs
  or enumerates a hardware device and blocks direct opening, reads, writes,
  feature reports, and delegated methods. Handles created before the flag is
  set are blocked too; offline handles cannot become live after it is removed.
  Blocked count writes do not save a profile.
- The standalone Windows x64 EXE was built with Python 3.14.7 and PyInstaller
  6.22.3. Its bundled-resource smoke test creates a real Tk 9.0.4 window,
  verifies the bootstrap and payload, and never installs or accesses hardware.
- Historical version 0.2.0 check: the setup window was visually checked and its
  standalone installer built a
  separate local copy through its GUI from the exact supported original
  executable. The original executable SHA-256 remained
  `974f28ff684091520bb742cf4a24dabd726c483b08094ded871ab87f90ab5e25`.
- That version 0.2.0 generated copy reached `window_ready` in
  `UMBRA_RGB_DRY_RUN=1` mode and exited normally. Its retained log records no
  open, open-path, read, write, or profile-selection events. The old dry-run
  implementation hid enumeration but did not block direct HID access, so the
  flag alone was not a complete guarantee. No recorded hardware activity from
  that check explains a lost setting. Version 0.2.1 closes that gap; no generated
  Umbra application or live HID device was started for this release's checks.
- The known-working private native build and its saved profile were not edited.
- No SignalRGB files were changed while preparing this add-on.

The earlier native compatibility build was physically confirmed by the owner
after a PC restart on a JONSBO tower. That result supports the same manual-count
mechanism, not every possible controller/device combination. This public edition
adds portable packaging and generic labels, omits a preselected profile, and
redacts identity information in logs; it has not received a separate physical
lighting test on additional hardware.

Version 0.2.1 hardens a developer diagnostic mode. Normal RGB logic is unchanged;
this release is not evidence that a reported manual-count regression was caused
by tests or has been fixed.

The source release builder uses an explicit allowlist and checks every ZIP entry
by reading it back. The source package contains authored code/documentation and
one attributed Umbra brand icon outside the MIT license. No vendor executable,
extracted vendor marshal, vendor runtime/library, other vendor image, firmware,
personal profile, or live log is included. The base64 bootstrap is compiled
solely from this project's readable `bootstrap.py`.

The setup bundles the interpreter/Tk it needs, the authored payload, the brand
icon, and retained license notices. It does not bundle Umbra's Python 3.8 runtime
or PySide2. The original Umbra runtime is copied locally during installation.
The brand icon is included in both the executable's Windows resources and the
Tk window; the rebuilt EXE's icon/resource smoke test passes.
