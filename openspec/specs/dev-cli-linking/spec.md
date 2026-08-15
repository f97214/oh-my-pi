# dev-cli-linking Specification

## Purpose

TBD - created by archiving change 'windows-dev-omp-launcher'. Update Purpose after archive.

## Requirements

### Requirement: Executable dev CLI entry point on every supported platform

After the setup linking step completes, an `omp` entry point SHALL exist in the package manager's global binary directory that the platform's default shells can execute directly. On Windows this SHALL include an entry with an extension the shell resolves through PATHEXT, because a shell script without an extension is not executable by PowerShell or cmd.exe.

#### Scenario: Windows shells invoke the dev CLI

- **WHEN** the setup linking step has completed on Windows and `omp` is typed in PowerShell or cmd.exe
- **THEN** the repository source runs and the command returns its normal output

#### Scenario: POSIX shells invoke the dev CLI

- **WHEN** the setup linking step has completed on Linux or macOS and `omp` is typed in a POSIX shell
- **THEN** the repository source runs and the command returns its normal output

##### Example: entry point resolved per shell

| Shell            | Entry file used in the global bin directory | Executes |
| ---------------- | ------------------------------------------- | -------- |
| PowerShell       | omp.cmd                                     | yes      |
| cmd.exe          | omp.cmd                                     | yes      |
| Git Bash on Windows | omp (extensionless shell script)         | yes      |
| POSIX sh / zsh   | omp (extensionless shell script)            | yes      |

#### Scenario: Shell resolution prefers the installed launcher

- **WHEN** the global bin directory is on PATH on Windows and `omp` is typed with no extension
- **THEN** the shell resolves the launcher the linking step installed, not a runtime-generated shim that bypasses the launch contract

##### Example: PATHEXT lists .EXE before .CMD

- **GIVEN** PATHEXT resolves `.EXE` ahead of `.CMD`, and `bun link` had left an `omp.exe` in the global bin directory
- **WHEN** the linking step completes
- **THEN** no `omp.exe` remains there, and `omp` resolves to `omp.cmd`


<!-- @trace
source: windows-dev-omp-launcher
updated: 2026-08-15
code:
  - docs/DEVELOPMENT.md
  - CLAUDE.md
  - scripts/link-omp.sh
  - packages/coding-agent/scripts/omp.cmd
-->

---
### Requirement: Caller working directory is preserved

The dev CLI SHALL treat the directory it was invoked from as its working directory, on every platform. The empty launch directory the entry point starts the runtime in SHALL NOT be observable to the CLI.

#### Scenario: Invoked from a directory unrelated to the repository

- **WHEN** the dev CLI is invoked from a directory that is not inside the repository
- **THEN** it resolves its workspace against that directory, not against the launch directory and not against the repository root

##### Example: workspace resolution from an unrelated directory

- **GIVEN** the current directory is a project folder with no relationship to the repository
- **WHEN** the dev CLI is invoked there
- **THEN** the workspace it reports is that project folder


<!-- @trace
source: windows-dev-omp-launcher
updated: 2026-08-15
code:
  - docs/DEVELOPMENT.md
  - CLAUDE.md
  - scripts/link-omp.sh
  - packages/coding-agent/scripts/omp.cmd
-->

---
### Requirement: A foreign bunfig preload cannot affect the dev CLI

The dev CLI SHALL start its runtime from a directory that declares no `bunfig.toml`, so preload entries belonging to the directory the user invoked from are never evaluated inside the CLI process. This SHALL hold on every platform that provides an entry point.

#### Scenario: Invoked inside a project whose preload cannot resolve

- **WHEN** the dev CLI is invoked from a directory whose `bunfig.toml` declares a preload entry that cannot be resolved
- **THEN** the CLI starts normally and the unresolvable preload is never evaluated

##### Example: unresolvable preload is ignored

- **GIVEN** a directory containing a `bunfig.toml` whose preload names a module that does not exist
- **WHEN** the dev CLI is invoked from that directory
- **THEN** the CLI returns its normal output and reports no module-resolution error


<!-- @trace
source: windows-dev-omp-launcher
updated: 2026-08-15
code:
  - docs/DEVELOPMENT.md
  - CLAUDE.md
  - scripts/link-omp.sh
  - packages/coding-agent/scripts/omp.cmd
-->

---
### Requirement: Shell session state is not mutated

Invoking the dev CLI SHALL leave the calling shell's working directory and environment variables exactly as they were. This is observable on cmd.exe, where a batch entry point that does not scope its own state changes the caller's session.

#### Scenario: cmd.exe session after invocation

- **WHEN** the dev CLI is invoked from cmd.exe and the process exits
- **THEN** the shell's current directory and environment variables are unchanged from before the invocation

##### Example: cmd.exe state before and after

- **GIVEN** a cmd.exe session whose current directory is `C:\Users\howard\Downloads`
- **WHEN** the dev CLI is invoked there and the process exits
- **THEN** typing `cd` still reports `C:\Users\howard\Downloads`, and no new variable is present in the session


<!-- @trace
source: windows-dev-omp-launcher
updated: 2026-08-15
code:
  - docs/DEVELOPMENT.md
  - CLAUDE.md
  - scripts/link-omp.sh
  - packages/coding-agent/scripts/omp.cmd
-->

---
### Requirement: Installed launcher content is encoding-independent

The Windows entry point installed by the linking step SHALL contain only ASCII characters and SHALL NOT embed the repository's filesystem path. Batch files are interpreted using the active console code page, so an embedded non-ASCII path would bind the installed launcher to the code page in effect when it was written.

#### Scenario: Repository path contains non-ASCII characters

- **WHEN** the linking step runs from a repository whose filesystem path contains non-ASCII characters
- **THEN** the installed Windows entry point contains no non-ASCII byte and locates the CLI without reference to that path

##### Example: launcher stays ASCII regardless of repository location

- **GIVEN** the repository is checked out at a path containing non-ASCII characters
- **WHEN** the linking step completes and the installed Windows entry point is inspected
- **THEN** every byte in it is ASCII, and the CLI still runs from any shell


<!-- @trace
source: windows-dev-omp-launcher
updated: 2026-08-15
code:
  - docs/DEVELOPMENT.md
  - CLAUDE.md
  - scripts/link-omp.sh
  - packages/coding-agent/scripts/omp.cmd
-->

---
### Requirement: Missing link target is surfaced

When the entry point cannot locate the linked package, it SHALL emit a message naming the setup command to run and SHALL exit with a non-zero status, rather than allowing the shell to report a generic path error.

#### Scenario: Link target absent

- **WHEN** the dev CLI entry point is invoked while the linked package is absent
- **THEN** a message naming the setup command is printed and the process exits non-zero

##### Example: linked package renamed away

- **GIVEN** the linked package directory under the global install root has been renamed
- **WHEN** the dev CLI entry point is invoked
- **THEN** the output names the setup command to run, and the exit code is non-zero


<!-- @trace
source: windows-dev-omp-launcher
updated: 2026-08-15
code:
  - docs/DEVELOPMENT.md
  - CLAUDE.md
  - scripts/link-omp.sh
  - packages/coding-agent/scripts/omp.cmd
-->

---
### Requirement: PATH absence is reported without modifying the environment

The linking step SHALL report when its target directory is absent from PATH, printing the full literal path to add. It SHALL NOT modify any persisted environment variable.

#### Scenario: Target directory is not on PATH

- **WHEN** the linking step completes and its target directory is absent from PATH
- **THEN** it prints the full literal path to add, and completes without treating this as a failure

##### Example: guidance names the exact directory

- **GIVEN** the global bin directory is absent from PATH
- **WHEN** the linking step completes
- **THEN** the output contains that directory's full literal path, and the step's exit code is 0

#### Scenario: Persisted environment is left alone

- **WHEN** the linking step runs to completion under any PATH condition
- **THEN** the persisted user and machine PATH values are identical to their values before the step ran

##### Example: persisted PATH compared across the run

- **GIVEN** the persisted user PATH value is recorded before the linking step runs
- **WHEN** the linking step runs to completion
- **THEN** re-reading the persisted user PATH yields a string identical to the recorded one


<!-- @trace
source: windows-dev-omp-launcher
updated: 2026-08-15
code:
  - docs/DEVELOPMENT.md
  - CLAUDE.md
  - scripts/link-omp.sh
  - packages/coding-agent/scripts/omp.cmd
-->

---
### Requirement: POSIX behaviour is unchanged

On Linux and macOS the linking step SHALL install exactly the same entry point as before Windows support was added, and SHALL create no Windows-specific artifact. Reporting an absent PATH entry is platform-independent and SHALL apply there as well.

#### Scenario: Linking on a POSIX host

- **WHEN** the linking step runs on Linux or macOS
- **THEN** it installs the extensionless shell wrapper as its only entry point, and emits no Windows-specific artifact

##### Example: artifacts installed per host

| Host    | omp (extensionless) | omp.cmd     |
| ------- | ------------------- | ----------- |
| Linux   | installed           | not created |
| macOS   | installed           | not created |
| Windows | installed           | installed   |

<!-- @trace
source: windows-dev-omp-launcher
updated: 2026-08-15
code:
  - docs/DEVELOPMENT.md
  - CLAUDE.md
  - scripts/link-omp.sh
  - packages/coding-agent/scripts/omp.cmd
-->