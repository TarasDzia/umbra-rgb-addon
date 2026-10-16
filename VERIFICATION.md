# Verification — version 0.1.0

Checked on Windows on 2026-10-17.

- 50 offline tests pass under Python 3.14.7 and Python 3.8.10.
- Tests cover optional profiles, exact packet gating, mode handover, fake HID/Qt,
  synthetic CArchive bounds, source hash checks, runtime preflight, no overwrite,
  bootstrap integrity, state exclusions, and original-file preservation.
- The installer built a separate local copy from the exact supported original
  executable. The original executable SHA-256 remained
  `974f28ff684091520bb742cf4a24dabd726c483b08094ded871ab87f90ab5e25`.
- The generated copy reached `window_ready` in `UMBRA_RGB_DRY_RUN=1` mode and
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

The source release builder includes only an explicit list of authored files and
checks every ZIP entry by reading it back. No vendor executable, extracted vendor
marshal, bundled vendor library/resource, firmware image, personal profile, or
live log is included in the public source package. The base64 bootstrap is
compiled solely from this project's readable `bootstrap.py`.
