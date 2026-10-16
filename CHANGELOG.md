# Changelog

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
