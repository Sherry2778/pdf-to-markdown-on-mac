# Third-party notices

This is an independent application built on Microsoft MarkItDown. It is not
affiliated with or endorsed by Microsoft or The Qt Company.

- [Microsoft MarkItDown](https://github.com/microsoft/markitdown): MIT.
  MarkItDown performs the PDF-to-Markdown conversion.
- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/):
  available under LGPLv3/GPLv3 or commercial terms.
  This application uses the LGPL distribution of Qt Essentials with dynamic
  libraries in the application bundle. The interface uses QtCore, QtGui and
  QtWidgets.
- [PyInstaller](https://pyinstaller.org/): GPL with its bootloader exception.
  Used to package the application and Python runtime.
- Python and the transitive dependencies retain their own licenses.

The application's MIT license covers this repository's original code, not
the third-party components. Each built app includes a ThirdPartyNotices
directory containing package versions, project URLs and the license files
shipped by the installed distributions.

Qt libraries are separate dynamic components in the app bundle and are not
statically linked. Users may replace compatible LGPL libraries and rebuild
the app from source. Re-signing a locally modified macOS bundle may be
necessary. This project imposes no additional restriction on reverse
engineering for debugging modifications to LGPL components.

See Qt's [licensing guidance](https://www.qt.io/licensing/open-source-lgpl-obligations)
and [source downloads](https://download.qt.io/official_releases/QtForPython/).
Public binary releases must include corresponding third-party notices and
satisfy the applicable source availability obligations; an app bundle alone
does not replace them.
