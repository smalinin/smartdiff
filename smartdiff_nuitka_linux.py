# nuitka-project: --onefile
# nuitka-project: --output-filename=smartdiff
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --output-dir=dist/nuitka_linux
# nuitka-project: --remove-output
# nuitka-project: --assume-yes-for-downloads
# nuitka-project-set: SMARTDIFF_VERSION = __import__("importlib.metadata", fromlist=("version",)).version("smartdiff")
# nuitka-project-set: SMARTDIFF_DIST_INFO = str(__import__("importlib.metadata", fromlist=("distribution",)).distribution("smartdiff")._path)
# nuitka-project: --include-data-dir={SMARTDIFF_DIST_INFO}=smartdiff-{SMARTDIFF_VERSION}.dist-info
# nuitka-project: --lto=yes
# nuitka-project: --jobs=4
# nuitka-project-if: {OS} == "Linux":
#    nuitka-project: --output-filename=smartdiff
#    nuitka-project: --onefile



from smartdiff.app import main


raise SystemExit(main())
