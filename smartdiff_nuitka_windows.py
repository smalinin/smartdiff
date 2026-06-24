# nuitka-project: --onefile
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --output-dir=dist/nuitka_windows
# nuitka-project: --remove-output
# nuitka-project: --assume-yes-for-downloads
# nuitka-project-if: {OS} == "Windows":
#    nuitka-project: --windows-console-mode=disable
#    nuitka-project: --output-filename=SmartDiff.exe

from smartdiff.app import main


raise SystemExit(main())
