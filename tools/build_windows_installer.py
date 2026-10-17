"""Build standalone Windows x64 setup from project code and attributed icon.

Run with the Python environment containing requirements-build.txt. No original
Umbra installation is read or bundled. PyInstaller collects Python/Tk itself.
"""
import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from patcher import VERSION, load_bootstrap

PYINSTALLER_VERSION = "6.22.3"
RESOURCES = (
    "bootstrap.py", "bootstrap38.b64", "bootstrap38.json", "LICENSE",
    "THIRD-PARTY-NOTICES.md", "payload/umbra_rgb_diagnostic_hook.py",
    "payload/jonsbo_compatibility.py", "assets/umbra.ico",
)


def collect_licenses(folder):
    """Copy notices verbatim from the exact interpreter and build packages."""
    folder.mkdir(parents=True, exist_ok=True)
    base = Path(sys.base_prefix)
    shutil.copyfile(str(base / "LICENSE.txt"), str(folder / "Python-LICENSE.txt"))
    # Python 3.14 stores Tcl/Tk scripts and their licenses in library ZIPs.
    for library, prefix in (("tcl", "Tcl"), ("tk", "Tk")):
        archives = sorted((base / "tcl").glob("lib%s*.zip" % library))
        if archives:
            with zipfile.ZipFile(str(archives[-1])) as archive:
                names = [n for n in archive.namelist() if n.endswith("/license.terms")]
                if len(names) != 1:
                    raise RuntimeError("Ambiguous %s license" % prefix)
                data = archive.read(names[0])
        else:
            paths = sorted((base / "tcl").glob(library + "*/license.terms"))
            if len(paths) != 1:
                raise RuntimeError("Cannot locate the %s license" % prefix)
            data = paths[0].read_bytes()
        (folder / (prefix + "-license.terms")).write_bytes(data)
    packages = ("pyinstaller", "altgraph", "packaging", "pefile",
                "pywin32-ctypes", "pyinstaller-hooks-contrib", "setuptools")
    for package in packages:
        distribution = metadata.distribution(package)
        matches = [p for p in distribution.files or ()
                   if ".dist-info/" in str(p).replace("\\", "/")
                   and (p.name.upper().startswith("LICENSE") or p.name == "COPYING.txt")]
        if package == "pyinstaller":
            matches = [p for p in matches if p.name == "COPYING.txt"]
        if not matches:
            raise RuntimeError("Missing license for " + package)
        for entry in matches:
            label = "PyInstaller-COPYING.txt" if package == "pyinstaller" else package + "-" + entry.name
            shutil.copyfile(str(distribution.locate_file(entry)), str(folder / label))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent /
                        ("Umbra-RGB-Addon-Setup-%s.exe" % VERSION))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if (sys.platform != "win32" or struct.calcsize("P") != 8
            or platform.machine().upper() not in ("AMD64", "X86_64")):
        parser.error("Build on Windows x64 with x64 Python and Tcl/Tk installed")
    if metadata.version("pyinstaller") != PYINSTALLER_VERSION:
        parser.error("Install requirements-build.txt in the build environment")
    output = args.output.resolve()
    if output.suffix.lower() != ".exe":
        parser.error("--output must name an .exe file")
    if output.exists() and not args.force:
        parser.error("Output exists; use --force to replace this setup build")
    if not output.parent.is_dir():
        parser.error("Output parent must already exist")
    load_bootstrap()
    for name in RESOURCES:
        if not (ROOT / name).is_file():
            parser.error("Missing authored resource: " + name)
    build = ROOT / "build" / "windows-installer"
    build.mkdir(parents=True, exist_ok=True)
    collect_licenses(build / "licenses")
    version = tuple(int(part) for part in VERSION.split(".")) + (0,)
    version_text = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=%r, prodvers=%r, mask=0x3f, flags=0,
                   OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Umbra RGB Add-on contributors'),
    StringStruct('FileDescription', 'Umbra RGB Add-on Setup'),
    StringStruct('FileVersion', %r),
    StringStruct('ProductName', 'Umbra RGB Add-on Setup'),
    StringStruct('ProductVersion', %r),
    StringStruct('LegalCopyright', 'MIT License - Umbra RGB Add-on contributors')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""" % (version, version, VERSION, VERSION)
    version_file = build / "version-info.txt"
    version_file.write_bytes(version_text.encode("utf-8"))
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile",
               "--windowed", "--name", output.stem, "--noupx",
               "--icon", str(ROOT / "assets" / "umbra.ico"),
               "--distpath", str(build / "dist"), "--workpath", str(build / "work"),
               "--specpath", str(build), "--version-file", str(version_file),
               "--exclude-module", "hid", "--exclude-module", "PySide2",
               "--exclude-module", "shiboken2"]
    for name in RESOURCES:
        destination = str(Path(name).parent)
        command += ["--add-data", str(ROOT / name) + ";" + destination]
    command += ["--add-data", str(build / "licenses") + ";licenses", str(ROOT / "installer_gui.py")]
    subprocess.run(command, cwd=str(ROOT), check=True)
    shutil.copyfile(str(build / "dist" / output.name), str(output))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".exe.sha256").write_bytes(
        (digest + "  " + output.name + "\n").encode("utf-8"))
    print(json.dumps({"file": str(output), "sha256": digest,
                      "python": platform.python_version(),
                      "pyinstaller": PYINSTALLER_VERSION,
                      "vendor_runtime_bundled": False, "brand_icon_bundled": True}, indent=2))


if __name__ == "__main__":
    main()
