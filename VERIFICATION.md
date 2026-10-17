# Verification — version 0.2.0

Checked on Windows on 2026-10-17.

- 75 tests pass under Python 3.14.7, including eight tests of real Tk widgets.
  Under the portable Python 3.8.10 runtime, 67 tests pass and eight GUI tests
  are skipped because that runtime does not provide Tk.
- Tests cover optional profiles, exact packet gating, mode handover, fake HID/Qt,
  synthetic CArchive bounds, source hash checks, runtime preflight, no overwrite,
  bootstrap integrity, state exclusions, original-file preservation, read-only
  planning, revalidation, stale GUI results, progress, and no automatic launch.
- The standalone Windows x64 EXE was built with Python 3.14.7 and PyInstaller
  6.22.3. Its bundled-resource smoke test creates a real Tk 9.0.4 window,
  verifies the bootstrap and payload, and never installs or accesses hardware.
- The setup window was visually checked. The standalone installer built a
  separate local copy through its GUI from the exact supported original
  executable. The original executable SHA-256 remained
  `974f28ff684091520bb742cf4a24dabd726c483b08094ded871ab87f90ab5e25`.
- That generated copy reached `window_ready` in `UMBRA_RGB_DRY_RUN=1` mode and
  exited normally. Its log confirms no explicit profile, no selected default,
  and no real HID enumeration. No hub commands were sent during this check.
- The known-working private native build and its saved profile were not edited.
- No SignalRGB files were changed while preparing this add-on.

The earlier native compatibility build was physically confirmed by the owner
after a PC restart on a JONSBO tower. That result supports the same manual-count
mechanism, not every possible controller/device combination. This public edition
adds portable packaging and generic labels, omits a preselected profile, and
redacts identity information in logs; it has not received a separate physical
lighting test on additional hardware.

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
