# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --output-dir=dist/nuitka_macos_x86
# nuitka-project: --remove-output
# nuitka-project: --assume-yes-for-downloads
# nuitka-project-set: SMARTDIFF_VERSION = __import__("importlib.metadata", fromlist=("version",)).version("smartdiff")
# nuitka-project-set: SMARTDIFF_DIST_INFO = str(__import__("importlib.metadata", fromlist=("distribution",)).distribution("smartdiff")._path)
# nuitka-project: --include-data-dir={SMARTDIFF_DIST_INFO}=smartdiff-{SMARTDIFF_VERSION}.dist-info
# nuitka-project-if: {OS} == "Darwin":
#    nuitka-project: --macos-create-app-bundle
#    nuitka-project: --macos-target-arch=x86_64
#    nuitka-project: --output-filename=SmartDiff

from smartdiff.app import main


raise SystemExit(main())
