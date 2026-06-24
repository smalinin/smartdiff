# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --output-dir=dist/nuitka_macos
# nuitka-project: --remove-output
# nuitka-project: --assume-yes-for-downloads
# nuitka-project-if: {OS} == "Darwin":
#    nuitka-project: --macos-create-app-bundle
#    nuitka-project: --macos-target-arch=arm64
#    nuitka-project: --output-filename=SmartDiff

from smartdiff.app import main


raise SystemExit(main())
