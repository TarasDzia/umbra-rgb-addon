# Third-party components in the Windows setup

The authored add-on code and documentation are licensed under this project's
MIT license. The standalone setup additionally carries a Python interpreter,
its standard library, Tcl/Tk, and the PyInstaller bootloader so users do not
have to install Python. The brand icon described below is a separate asset.

- [Python](https://www.python.org/) is distributed under the PSF license and
  related notices in `licenses/Python-LICENSE.txt` inside the setup archive.
- [Tcl/Tk](https://www.tcl-lang.org/) uses the permissive terms retained in
  `licenses/Tcl-license.terms` and `licenses/Tk-license.terms`.
- [PyInstaller](https://pyinstaller.org/) uses GPL-2.0-or-later with its
  bootloader exception. Its complete notice is retained in
  `licenses/PyInstaller-COPYING.txt`. The exception permits distributing this
  bundled application under its own license.

The build script collects these texts from the build environment and includes
them unchanged as setup resources. License notices for build dependencies are
also retained there. Build dependencies are not required on the user's PC.

## AsiaHorse Umbra brand icon

The setup and source archive include `assets/umbra.ico`, copied unchanged from
`img/ARGB/0005YZM/0005YZM_LOGO.ico` in the supported AsiaHorse Umbra application.
It is an AsiaHorse Umbra brand asset, not an original work of this project,
and is not licensed under this project's MIT license. Rights in the icon and
brand remain with their respective owners. This notice records attribution and
provenance; it does not grant a trademark or copyright license. See
[the asset notice](assets/README.md).

This icon is the only vendor visual asset included. The setup does not
distribute AsiaHorse's executable, Python 3.8 runtime, libraries, other images,
firmware, or extracted code. Those application and runtime files are read only
from the user's supported local installation when creating the separate
patched copy. This independent community project is not an official AsiaHorse
release, and use of the icon does not imply endorsement or affiliation.
