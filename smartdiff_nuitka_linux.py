# nuitka-project: --onefile
# nuitka-project: --output-filename=smartdiff
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --output-dir=dist/nuitka_linux
# nuitka-project: --remove-output
# nuitka-project: --assume-yes-for-downloads
# nuitka-project: --lto=yes
# nuitka-project: --jobs=4
# nuitka-project-if: {OS} == "Linux":
#    nuitka-project: --output-filename=smartdiff
#    nuitka-project: --onefile



from smartdiff.app import main


raise SystemExit(main())
