"""Create a source-only release from an explicit list of authored files."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from patcher import VERSION, load_bootstrap


# New runtime files can never enter a release by recursive directory scanning.
FILES = (
    ".gitattributes", ".gitignore", "LICENSE", "README.md", "README.uk.md",
    "CHANGELOG.md", "VERIFICATION.md", "patcher.py", "install.ps1", "bootstrap.py",
    "bootstrap38.b64", "bootstrap38.json",
    "payload/umbra_rgb_diagnostic_hook.py", "payload/jonsbo_compatibility.py",
    "tests/test_profile.py", "tests/test_hook.py", "tests/test_patcher.py",
    "tools/build_bootstrap38.py", "tools/build_source_release.py",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT.parent / ("umbra-rgb-addon-%s-source.zip" % VERSION))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        parser.error("Output exists; pass --force to replace this source release")
    load_bootstrap()  # Refuse a stale or mismatched authored bootstrap.
    contents = {name: (ROOT / name).read_bytes() for name in FILES}
    manifest = {"version": VERSION, "scope": "authored-addon-only; no vendor runtime",
                "files": {name: hashlib.sha256(data).hexdigest()
                          for name, data in contents.items()}}
    contents["RELEASE-MANIFEST.json"] = (
        json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
    prefix = "umbra-rgb-addon/"
    with zipfile.ZipFile(str(args.output), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(contents.items()):
            info = zipfile.ZipInfo(prefix + name, (2026, 10, 17, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    with zipfile.ZipFile(str(args.output)) as archive:
        assert set(archive.namelist()) == {prefix + name for name in contents}
        for name, data in contents.items():
            if archive.read(prefix + name) != data:
                raise RuntimeError("Release read-back mismatch: " + name)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        digest + "  " + args.output.name + "\n", encoding="utf-8")
    print("Verified %d authored files: %s" % (len(contents), args.output))
    print("SHA256", digest)


if __name__ == "__main__":
    main()
