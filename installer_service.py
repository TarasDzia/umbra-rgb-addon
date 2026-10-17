"""Read-only installer planning and explicit installation, without GUI or HID."""
from dataclasses import dataclass
import os
from pathlib import Path

import patcher


@dataclass(frozen=True)
class InstallPlan:
    source: Path
    destination: Path


def _selection_path(value, label):
    if not isinstance(value, (str, os.PathLike)):
        raise patcher.PatchError("Choose the %s path" % label)
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    if not text:
        raise patcher.PatchError("Choose the %s path" % label)
    return Path(text).expanduser()


def normalize_source(value):
    """Accept the original app folder or Sync_light.exe, with optional quotes."""
    path = _selection_path(value, "original application")
    if path.name.lower() == patcher.SOURCE_EXE.lower():
        patcher._plain_path(path, "source executable")
        path = path.parent
    return patcher._plain_path(path, "source")


def default_destination():
    """Suggest a fresh per-user folder; do not create it or reserve its name."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    parent = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    base = parent / "UmbraRGBAddon" / ("v" + patcher.VERSION)
    candidate, number = base, 2
    while os.path.lexists(str(candidate)):
        candidate = base.with_name(base.name + "-" + str(number))
        number += 1
    return candidate


def validate_selection(source, destination):
    """Fully check a selection without creating folders or loading vendor code."""
    source_path = normalize_source(source)
    destination_path = _selection_path(destination, "destination")
    prepared = patcher.preflight_install(source_path, destination_path, require_parent=False)
    return InstallPlan(prepared.source, prepared.destination)


def install_selection(plan, progress=None):
    """Revalidate then create the selected copy; existing folders are never used."""
    if not isinstance(plan, InstallPlan):
        raise TypeError("Expected an InstallPlan")
    # install_addon repeats full preflight before creating even a missing parent.
    # Never trust a previous validation: paths or source files may have changed.
    return patcher.install_addon(plan.source, plan.destination,
                                 progress=progress, create_parent=True)
