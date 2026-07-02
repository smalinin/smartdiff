# nuitka-project: --onefile
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --output-dir=dist/nuitka_windows
# nuitka-project: --remove-output
# nuitka-project: --assume-yes-for-downloads
# nuitka-project-set: SMARTDIFF_VERSION = __import__("importlib.metadata", fromlist=("version",)).version("smartdiff")
# nuitka-project-set: SMARTDIFF_DIST_INFO = str(__import__("importlib.metadata", fromlist=("distribution",)).distribution("smartdiff")._path)
# nuitka-project: --include-data-dir={SMARTDIFF_DIST_INFO}=smartdiff-{SMARTDIFF_VERSION}.dist-info
# nuitka-project-if: {OS} == "Windows":
#    nuitka-project: --windows-console-mode=disable
#    nuitka-project: --output-filename=SmartDiff.exe

from smartdiff.app import main


raise SystemExit(main())
