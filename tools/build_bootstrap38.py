"""Rebuild our bootstrap; requires Python 3.8, imports no vendor modules."""
import base64
import hashlib
import json
import marshal
from pathlib import Path
import sys

if sys.version_info[:2] != (3, 8):
    sys.exit("Regeneration requires Python 3.8; installation does not.")
root = Path(__file__).resolve().parents[1]
source = (root / "bootstrap.py").read_bytes()
payload = marshal.dumps(compile(source.decode("utf-8"), "Sync_light.py", "exec"))
(root / "bootstrap38.b64").write_bytes(base64.encodebytes(payload))
metadata = {"python": [3, 8], "marshal_version": marshal.version,
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "payload_sha256": hashlib.sha256(payload).hexdigest()}
(root / "bootstrap38.json").write_bytes(
    (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print("Regenerated authored Python 3.8 bootstrap; no vendor code or device accessed.")
