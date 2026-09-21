@echo off
setlocal

rem Windows dev launcher for the omp CLI, installed by `bun run setup`.
rem
rem This is the cmd.exe half of the contract the `omp` script next to this file
rem implements for POSIX shells: PowerShell and cmd.exe cannot execute an
rem extensionless shell script, so the linking step installs both.
rem
rem Why Bun is started from an empty directory: Bun reads `bunfig.toml` from the
rem *current working directory* at startup and evaluates its `preload` entries
rem before the entrypoint, so launching in place would inherit whatever preload
rem the directory you happen to be in declares -- and crash on it. The launch
rem directory holds no bunfig; scripts/omp.ts restores the real working
rem directory from OMP_LAUNCH_CWD before the entrypoint's imports run.
rem
rem Why the CLI is located through the global link rather than a checkout path:
rem batch files are read using the active console code page, so a checkout path
rem containing non-ASCII characters would be mangled. The link `bun link`
rem creates is an ASCII path that Windows resolves back to the checkout, so this
rem file stays ASCII-only, code-page independent, and survives the checkout
rem being moved.
rem
rem PI_TIMING is deliberately not wired up here. The POSIX wrapper adds a second
rem preload from packages/utils, which needs `..` traversal out of the linked
rem package -- Windows normalizes `..` lexically before resolving the link, so
rem that path would not resolve. Use `bun run dev:timing` in the checkout.

set "OMP_BUN_ROOT=%BUN_INSTALL%"
if not defined OMP_BUN_ROOT set "OMP_BUN_ROOT=%USERPROFILE%\.bun"
set "OMP_PKG=%OMP_BUN_ROOT%\install\global\node_modules\@oh-my-pi\pi-coding-agent"

if not exist "%OMP_PKG%\src\cli.ts" (
    >&2 echo omp: linked package not found at "%OMP_PKG%"
    >&2 echo omp: run "bun setup" in the oh-my-pi checkout to create the link
    exit /b 127
)

set "OMP_LAUNCH_DIR=%OMP_DEV_LAUNCH_DIR%"
if not defined OMP_LAUNCH_DIR set "OMP_LAUNCH_DIR=%USERPROFILE%\.omp\.dev-cwd"
if not exist "%OMP_LAUNCH_DIR%" mkdir "%OMP_LAUNCH_DIR%" >nul 2>&1

rem Exported to the child process; scripts/omp.ts reads it and chdir()s back.
rem setlocal also restores this shell's drive and directory when the script
rem exits, so the caller's cmd session is left exactly as it was.
set "OMP_LAUNCH_CWD=%CD%"
cd /d "%OMP_LAUNCH_DIR%"

bun --preload "%OMP_PKG%\scripts\omp.ts" "%OMP_PKG%\src\cli.ts" %*
exit /b %ERRORLEVEL%
