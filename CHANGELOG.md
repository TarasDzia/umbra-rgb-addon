# Changelog

## 0.2.0 — 2026-10-17

- Standalone Windows setup with a graphical folder picker, compatibility check, installation progress, and completion screen.
- No Python installation or command-line commands needed for the setup EXE.
- Separate destination under the current user's local application data by default, with no overwrite of existing folders.
- Read-only validation of the exact supported original executable and runtime before creating the destination.
- Installation copies the user's local Umbra runtime without launching the application, opening HID devices, downloading files, or installing drivers.
- Source-based CLI installation remains available with Python 3.8 or newer.
- Updated English and Ukrainian setup and build instructions.

RGB behavior and the verified hardware scope are unchanged. This release adds installation packaging; it does not establish support for additional Umbra builds, ports, controllers, or devices.

## 0.1.0 — 2026-10-17

- First source distribution of the unofficial RGB-only Umbra add-on.
- Reproducible local patcher for the exact verified vendor executable.
- New output folder only; no changes to the original installation.
- Explicit manual LED profile for FE04 physical port 1, with saved/active status.
- No model-specific default count, automatic count replay, or zero-on-exit.
- USB RGB handover before native effects and after manual preview.
- RGB command gate; fan PWM, reset, boot settings and firmware writes blocked.
- Offline synthetic archive, profile, packet, and fake-HID/Qt tests.
- English and Ukrainian installation, operation, and removal documentation.

The original private compatibility build was physically verified on a JONSBO
tower after a PC restart. This release changes packaging, generic labels,
logging, and the absence of a default profile. It does not establish support
for additional hardware or vendor versions.
