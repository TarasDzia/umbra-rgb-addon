"""Authored Python 3.8 startup wrapper, compiled by tools/build_bootstrap38.py."""
import os as _os
import sys as _sys
import marshal as _marshal

_root = _os.path.dirname(_sys.executable)
_hook = {"__name__": "umbra_rgb_diagnostic_hook",
         "__file__": _os.path.join(_root, "umbra_rgb_diagnostic_hook.py")}
with open(_hook["__file__"], encoding="utf-8") as _stream:
    exec(compile(_stream.read(), _hook["__file__"], "exec"), _hook)
_hook["install"]()
with open(_os.path.join(_root, "Sync_light.original.marshal"), "rb") as _stream:
    _original_code = _marshal.loads(_stream.read())
exec(_hook["patch_code"](_original_code), globals())
