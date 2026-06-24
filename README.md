# SmartDiff

Python + PySide6 diff viewer and merge program.

## Run

```powershell
uv run smartdiff
uv run smartdiff --d C:\left C:\right
uv run smartdiff C:\left\file.py C:\right\file.py
```

`--d` disables subdirectory scanning when comparing directories.

## Build EXE

Nuitka can build a standalone Windows `.exe` with bundled PySide6/Qt files:

```powershell
uv run --with nuitka python -m nuitka smartdiff_nuitka_windows.py

uv run --with nuitka python -m nuitka smartdiff_nuitka_linux.py

uv run --with nuitka python -m nuitka smartdiff_nuitka_macos.py
```

Launchers:

- `smartdiff_nuitka_windows.py` builds the Windows standalone executable in `dist/nuitka_windows`
  with the PySide6 plugin and hidden console window.
- `smartdiff_nuitka_linux.py` builds the Linux onefile executable in
  `dist/nuitka_linux`. The GitHub Actions Linux release build runs on
  `ubuntu-22.04` for broader glibc compatibility.
- `smartdiff_nuitka_macos.py` builds the macOS `.app` bundle in
  `dist/nuitka_macos` for Apple Silicon. `smartdiff_nuitka_macos_x86.py`
  builds the Intel `x86_64` variant in `dist/nuitka_macos_x86`.

A C compiler is required; on Windows, Visual Studio 2022 Build Tools is the safest
choice. On macOS, use the system Clang compiler from Xcode.

GitHub Actions builds release artifacts on tag pushes matching `v*`. You can also
run the `SmartDiff Nuitka` workflow manually for build verification.

## Current Features

- Compare two directories or two files.
- Hide equal files by default with the `Only changes` checkbox.
- Double-click a changed file to open a side-by-side diff window.
- Line-level and inline changed-text highlighting.
- Find, Find Next, Find Previous in the selected side.
- Editable diff panes with built-in undo/redo from `QPlainTextEdit`.
- Save changes only when `File -> Save` is used.
- Unsaved-change prompt on close.
- Ignore whitespace, ignore case, and light/dark theme options.
- Binary files and text files over 10 MB are compared by size, timestamp, and SHA-256 without text diff.
- Recursive directory scans skip known generated/service directories such as `.git`, `.venv`, `__pycache__`, and `node_modules`.
- `File -> Preferences...` edits binary extensions, ignored directories, and max text diff size in `~/.smartdiff/settings.json`.

## License

Licensed under the Apache License 2.0. See `LICENSE`.
