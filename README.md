# Umbra RGB Add-on

[Українською](README.uk.md)

An open-source, unofficial add-on for **AsiaHorse Umbra** that makes manual LED-count settings usable when automatic detection misses an ARGB device.

The add-on patches a **local copy of your installed application**. It is not an official Umbra plugin API, a firmware update, or a replacement for the entire vendor application. The original application is a packaged Python program; this project adds a small Python hook to its startup.

## What it fixes

A device can respond to the port-identification light and the LED-count preview while Umbra still reports **0 LEDs** and excludes it from animations. On the tested hub, the firmware already supports a saved manual count, but activates that count during hub startup.

This add-on:

- Saves an explicit LED-count selection for **physical ARGB port 1** in a local profile and the hub's existing RGB configuration.
- Distinguishes the saved target from the active count reported by the hub.
- Selects USB RGB control before normal effects and again after a count preview.
- Leaves normal effect data intact and uses actual hardware topology for RGB allocation.
- Never replays the count-setting command automatically at startup or shutdown.

There is no device-brand emulation: a JONSBO device does not need to identify itself as JUMPEAK. The same mechanism may help other ARGB devices with failed detection, but those combinations have not been physically verified.

## Supported configuration

| Item | Current scope |
| --- | --- |
| Operating system | Windows; standalone setup for **x64** |
| Original application | AsiaHorse Umbra **V3.5.5_09.03** |
| Original executable | `Sync_light.exe`, exact SHA-256 below |
| Tested controller | USB VID `1A86`, PID `FE04` |
| Firmware analyzed and tested | **1.0.6** |
| Manual override | Physical ARGB **port 1**, values **0–100** |
| Physical validation | JONSBO tower recognition and lighting confirmed after a PC restart |

Supported original executable SHA-256:

```text
974f28ff684091520bb742cf4a24dabd726c483b08094ded871ab87f90ab5e25
```

The installer refuses an unrecognized executable. A matching version label alone is not enough. Other ports, controllers, firmware versions, and vendor updates are outside the verified scope.

The physical confirmation was for the original private compatibility build. Public package checks are documented separately in [VERIFICATION.md](VERIFICATION.md); an installer check does not verify physical RGB behavior.

The successful local setup saved **7** before the PC restart. That is an observation for one device, not a default or a recommended count for every tower. The post-restart active count was not retained in telemetry. This public package does **not** preselect 7 or 24.

## Install

Download **[Umbra-RGB-Addon-Setup-0.2.0.exe](https://github.com/TarasDzia/umbra-rgb-addon/releases/download/v0.2.0/Umbra-RGB-Addon-Setup-0.2.0.exe)** from the [0.2.0 release](https://github.com/TarasDzia/umbra-rgb-addon/releases/tag/v0.2.0). **You do not need to install Python or use PowerShell.** You still need your own installation of the supported Umbra version, with `Sync_light.exe` and its supporting runtime files.

1. Close Umbra and other RGB programs that control the same hub.
2. Run the setup EXE and select the original Umbra folder containing `Sync_light.exe`.
3. Choose a **new, separate destination folder**. The default is `%LOCALAPPDATA%\UmbraRGBAddon\v0.2.0`; if that folder exists, setup suggests an unused name.
4. Check the selected installation, then install. Setup accepts only the exact supported original executable and complete runtime.
5. When installation finishes, manually start `Umbra-RGB-Addon.exe` from the destination folder. Keep its supporting files together.

Setup bundles the Python/Tk runtime needed for its own window and patcher. It copies Umbra's runtime from your local installation and adds this project's code. The generated application keeps the vendor's bundled Python 3.8 runtime.

Installation does not start Umbra, open the hub, send HID packets, install drivers, or download files. It never overwrites an existing destination; the original installation and SignalRGB files stay unchanged. Setup and the modified local executable are unsigned; any original executable signature is not carried over to the modified copy.

If copying or patching fails, setup reports the error and leaves any partial destination for inspection. Retry with a new folder; remove the incomplete folder yourself when it is no longer needed.

## Set the manual count

1. In the generated application, open **Ctrl Settings** and select **physical port 1**.
2. Explicitly choose the appropriate **LED Count** for your connected device. No manual count is written until you make a selection.
3. Restart the PC, then reopen `Umbra-RGB-Addon.exe` and try a normal lighting effect.

On firmware 1.0.6 this value is a **manual fallback**, not an unrestricted
replacement for detection: at boot it applies a positive saved count only when
that count is larger than the detected count. It can recover a port detected as
zero; it cannot force a lower count than successful automatic detection. Zero
disables this saved fallback at the next boot; it is not a general lights-off
control.

Restarting the application alone does not activate the saved count on the tested firmware. The confirmed successful step was a PC restart; the add-on sends no controller-reset command. If the hub remains powered throughout a restart, a complete shutdown and power cycle may be needed for a new hub startup.

When changing the count, the immediate pattern of **N−1 red samples followed by one white sample** is the firmware's count preview. It is not an animation and does not prove that the active animation topology has already changed. Use the saved/active status to distinguish these states.

## RGB-only scope

The transport gate permits only the supported RGB packet forms. It blocks fan PWM, controller reset commands (`FA`, `07`, `FC`), boot-setting commands (`0B`, `0C`), feature writes, and firmware writes. Driver installers and privilege/startup helper routines are disabled in the generated copy.

**Fan-speed controls in the copied vendor interface are not functional through this add-on.** This project changes lighting behavior only. It does not modify or install hub firmware.

Use one RGB controller application at a time. This package does not install or change a SignalRGB plugin.

## Update or uninstall

- **Update the add-on:** close the generated application and create a new destination folder from the same supported original installation. Retain any profile you need separately; do not assume a new installation inherits another folder's profile.
- **Update Umbra:** an unknown executable is rejected. Wait for support for that exact build instead of bypassing the hash check.
- **Uninstall:** close the generated application and delete only its generated destination folder. The original Umbra installation remains available.

Removing the folder does **not** undo a manual RGB count already saved in the hub. Installation and removal send no hardware commands. There is no background service, network download, or automatic updater.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Patcher rejects `Sync_light.exe` | Use the supported original executable; patched copies and different builds do not match its hash. |
| Runtime files cannot be found | Select the full installed Umbra folder, not an EXE copied on its own. |
| Destination is rejected | Choose a new folder outside the original installation and add-on source folder. The CLI also requires an existing parent folder. |
| Installation stopped while copying | Keep the error message, inspect the partial output if needed, and retry with a new destination. |
| Count preview works but effects do not | Restart the PC/hub after the explicit count selection; check saved target versus reported active count. |
| Another port changes color | This release targets physical port 1; do not infer port identity from a component list in another RGB application. |
| Fan-speed buttons do nothing | Expected: PWM is blocked in this RGB-only copy. |

For an issue, include the original app version/hash, controller VID/PID and firmware, physical port, selected count, reported active count if available, and whether a PC restart changed the result. Do not upload the generated application, your entire runtime folder, or unreviewed personal logs/profiles.

## For contributors

### Install from source

The command-line patcher remains available and uses only Python's standard library. It requires **Python 3.8 or newer**; it does not require Python 3.8 specifically. Download and extract the source package, close RGB applications, then run:

```powershell
python patcher.py inspect --source "C:\path\AsiaHorse UMBRA"
python patcher.py install --source "C:\path\AsiaHorse UMBRA" --destination "C:\path\Umbra-RGB-Addon"
```

The destination must be a new folder outside both the original installation and this source folder. For the CLI, its parent folder must already exist. Start the generated application manually after installation.

### Tests and builds

Run the offline tests from this project folder:

```powershell
python -m unittest discover -s tests -v
```

Version 0.1.0 passed 50 offline tests under Python 3.8 and 3.14. A locally generated application also reached the window-ready state in USB-disabled mode. Current release checks and their limits are recorded in [VERIFICATION.md](VERIFICATION.md).

The source package contains our hook, patcher, installer, tests, documentation, readable bootstrap source, build tools, and a precompiled **Python 3.8 bootstrap belonging to this project**, stored as base64 text. The precompiled bootstrap lets a newer Python patcher prepare the vendor's Python 3.8 application without executing its code during installation. Rebuilding that bootstrap requires Python 3.8; ordinary installation does not.

Build the standalone setup on Windows with **Python 3.14 x64** in a separate build environment. The output's parent folder must already exist:

```powershell
python -m pip install -r requirements-build.txt
python tools/build_windows_installer.py --output "C:\path\Umbra-RGB-Addon-Setup-0.2.0.exe"
```

The build requirements pin PyInstaller to **6.22.3**. Setup includes its own interpreter and Tk libraries, so end users do not need a Python installation. Its Umbra icon is the separately attributed brand asset described below. It contains no original or patched Umbra executable, vendor libraries, extracted code, or firmware.

To regenerate the Python 3.8 bootstrap or make the source archive:

```powershell
py -3.8 tools/build_bootstrap38.py
python tools/build_source_release.py
```

The second command creates a source-only ZIP next to the project folder, with
an explicit file list, a per-file hash manifest, and a ZIP checksum. Generated
vendor runtime folders are never scanned for inclusion.

Keep the version pin, packet gate, separate destination, explicit-only count writes, actual-topology allocation, and saved/active distinction when making changes. Tests must not require a connected controller.

For a USB-disabled startup check of a locally generated copy, set the dry-run environment variable for that process:

```powershell
$env:UMBRA_RGB_DRY_RUN = "1"
& "C:\path\Umbra-RGB-Addon\Umbra-RGB-Addon.exe"
Remove-Item Env:\UMBRA_RGB_DRY_RUN
```

Dry-run mode skips real HID enumeration. An offline test or a successful startup is not evidence that another device/controller combination works physically.

## Distribution and license

This repository's authored add-on code and documentation use the [MIT License](LICENSE). The standalone setup also bundles its Python/Tk runtime and packaging components under their respective licenses; see [third-party notices](THIRD-PARTY-NOTICES.md).

The setup and source archive include one AsiaHorse Umbra brand icon, [`assets/umbra.ico`](assets/umbra.ico), copied unchanged from the supported application's icon resource. It is **not covered by this project's MIT license**. Attribution and provenance are recorded in [the asset notice](assets/README.md); no permission to use the brand is granted by this repository's license.

Apart from that icon, do not add vendor resources, original or patched Umbra executables, extracted vendor code, vendor libraries, firmware images, local runtime folders, logs, or personal profiles to source releases. The generated copy uses the application and runtime you supply locally; it is for local use and is not the source package to upload to GitHub.

This is an independent community project and is not an official AsiaHorse release.
