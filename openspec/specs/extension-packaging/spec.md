# extension-packaging Specification

## Purpose

TBD - created by archiving change 'remove-external-zip-dependency'. Update Purpose after archive.

## Requirements

### Requirement: Packaging without external executables

The extension packaging step SHALL produce the distribution archive entirely in process. It SHALL NOT invoke any external executable, and SHALL NOT branch on the host operating system or on the availability of any external tool when selecting how to package.

#### Scenario: Host without a zip executable

- **WHEN** the browser-relay build runs on a host where no zip executable is present on PATH
- **THEN** the build completes with exit code 0 and writes the distribution archive

#### Scenario: Identical code path across host operating systems

- **WHEN** the build runs on Windows, macOS, or Linux
- **THEN** the same in-process packaging code path executes on each, with no operating-system-conditional branch selecting a different packaging mechanism

##### Example: presence of the external tool changes nothing

| Host          | zip executable on PATH | Packaging mechanism used | Build exit code |
| ------------- | ---------------------- | ------------------------ | --------------- |
| Windows 11    | absent                 | in-process framer        | 0               |
| ubuntu-22.04  | present                | in-process framer        | 0               |
| macOS 14      | present                | in-process framer        | 0               |


<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->

---
### Requirement: Packaging without installed dependencies

The packaging step SHALL execute in a checkout where no package manager install has been performed. Its transitive import graph SHALL resolve using only Node built-in modules, Bun globals, and relative modules that are themselves free of bare package specifiers.

#### Scenario: Clean checkout with no installed dependency tree

- **WHEN** the browser-relay build runs in a fresh checkout that has no installed dependency tree
- **THEN** the build completes with exit code 0 and writes the distribution archive

#### Scenario: Workspace package imported into the guarded graph

- **WHEN** a module in the packaging import graph gains an import of a workspace package specifier
- **THEN** the repository lint check reports an error for that file

##### Example: a workspace import added to the writer module

- **GIVEN** the line `import { formatBytes } from "@oh-my-pi/pi-utils";` is added to `packages/coding-agent/src/utils/zip-writer.ts`
- **WHEN** the repository lint check runs against that file
- **THEN** it reports a restricted-import error naming that specifier and exits non-zero


<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->

---
### Requirement: Complete recursive archive membership

Archive membership SHALL be derived by recursively enumerating the built extension directory. Every regular file found SHALL become an archive member. Directory entries SHALL NOT be emitted. Membership SHALL NOT be derived from a hardcoded list of file names.

#### Scenario: Output that is not in the previously hardcoded set

- **WHEN** the built extension directory contains a regular file that was not part of the previously hardcoded four-file list
- **THEN** that file is present as an archive member

##### Example: membership across nested and additional outputs

| Path under the built extension directory | In archive | Entry name      |
| ---------------------------------------- | ---------- | --------------- |
| background.js                            | yes        | background.js   |
| manifest.json                            | yes        | manifest.json   |
| chunk-a1b2c3.js                          | yes        | chunk-a1b2c3.js |
| assets/icon.png                          | yes        | assets/icon.png |
| assets (the directory itself)            | no         | not emitted     |


<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->

---
### Requirement: Forward-slash archive entry names

Archive entry names SHALL use the forward slash character as the only path separator, on every host operating system. No entry name SHALL contain a backslash.

#### Scenario: Packaging a nested file on Windows

- **WHEN** the build runs on Windows and the built extension directory contains a file inside a subdirectory
- **THEN** the archive entry name for that file uses forward slashes and contains no backslash

##### Example: nested entry name on a Windows host

- **GIVEN** the host filesystem reports the member path as assets\icon.png relative to the built extension directory
- **WHEN** the archive is produced
- **THEN** the archive entry name is assets/icon.png


<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->

---
### Requirement: Deterministic archive bytes

Given identical input files, the packaging step SHALL produce a byte-identical archive. Members SHALL be ordered by entry name. Member timestamps SHALL be a fixed value rather than filesystem modification times.

#### Scenario: Two consecutive builds with unchanged inputs

- **WHEN** the build runs twice with no change to any input file
- **THEN** the two archives have identical SHA256 digests

#### Scenario: Filesystem enumeration order differs

- **WHEN** the underlying filesystem returns the files of the built extension directory in a different order than a previous run
- **THEN** the archive bytes are unchanged

##### Example: two enumeration orders produce one archive

| Order returned by the filesystem                             | Archive member order                                         | Archive SHA256 |
| ------------------------------------------------------------ | ------------------------------------------------------------ | -------------- |
| manifest.json, background.js, options.js, options.html       | background.js, manifest.json, options.html, options.js       | digest D       |
| background.js, options.html, manifest.json, options.js       | background.js, manifest.json, options.html, options.js       | digest D       |


<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->

---
### Requirement: Single-sourced ZIP framing

The repository SHALL contain exactly one ZIP container framing implementation. That implementation SHALL be split into a writer half that is importable without package resolution and a reader half. The reader half SHALL remain the public entry point for archive work and SHALL continue to export the framing function under its existing name, so existing importers require no modification.

#### Scenario: Application code imports the framing function

- **WHEN** application code imports the ZIP framing function from the archive boundary module
- **THEN** the import resolves and no existing importer requires modification

##### Example: an existing importer is left untouched

- **GIVEN** `packages/coding-agent/test/tools/fetch-binary-dispatch.test.ts` contains the line `import { zip } from "@oh-my-pi/pi-coding-agent/utils/zip";`
- **WHEN** that file is type-checked and executed without any edit
- **THEN** the import resolves to the single framing implementation and the test passes

#### Scenario: Packaging reuses the repository framing implementation

- **WHEN** the packaging step frames the distribution archive
- **THEN** it uses the same framing implementation as the rest of the repository, including its overflow guards, stored-member fallback, UTF-8 name flag, and fixed timestamp


<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->

---
### Requirement: Archive size overflow is surfaced, not wrapped

When archive content exceeds the 32-bit header limits of a non-ZIP64 archive, the framing implementation SHALL raise an error and the build SHALL exit non-zero. It SHALL NOT emit an archive whose header fields have wrapped or been truncated.

#### Scenario: Content exceeds non-ZIP64 header limits

- **WHEN** the total archive content exceeds the 32-bit offset or size limits of a non-ZIP64 archive
- **THEN** an error is raised and the build exits non-zero without writing an archive that appears valid


<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->

---
### Requirement: Embedded CLI assets regenerate independently of archiving

The build SHALL regenerate the embedded CLI text assets before producing the distribution archive. A failure in the archiving step SHALL NOT prevent the embedded assets from being regenerated.

#### Scenario: Archiving fails after a successful bundle

- **WHEN** the bundle step succeeds and the archiving step then fails
- **THEN** the embedded CLI text assets have already been regenerated on disk

##### Example: assets present on disk after an archiving failure

- **GIVEN** the bundle step has written background.js, manifest.json, options.html, and options.js into the built extension directory, and the archiving step then raises an error
- **WHEN** the build process exits
- **THEN** background.js.txt, manifest.json.txt, options.html.txt, and options.js.txt under `packages/coding-agent/src/tools/browser/relay/extension-assets/` have already been rewritten, and the process exit code is non-zero

#### Scenario: Rebuild with unchanged extension sources

- **WHEN** the build runs with no change to the extension sources
- **THEN** the embedded CLI text assets are byte-identical to their committed contents

##### Example: version control reports no change

- **GIVEN** no file under `packages/browser-relay/extension/` differs from its committed contents
- **WHEN** the build runs to completion and the version control short status is taken for `packages/coding-agent/src/tools/browser/relay/extension-assets/`
- **THEN** the status output contains zero lines


<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->

---
### Requirement: Archive readable by independent implementations

The distribution archive SHALL conform to the ZIP format such that implementations outside this repository enumerate and extract it correctly.

#### Scenario: Third-party reader enumerates the archive

- **WHEN** a ZIP implementation that is not part of this repository opens the distribution archive
- **THEN** it reports one entry per regular file in the built extension directory, each carrying the uncompressed size of the corresponding file

##### Example: entries reported for the current extension

| Entry name    | Corresponding file in the built extension directory | Reported uncompressed size    |
| ------------- | --------------------------------------------------- | ----------------------------- |
| background.js | background.js                                       | equal to the file size on disk |
| manifest.json | manifest.json                                       | equal to the file size on disk |
| options.html  | options.html                                        | equal to the file size on disk |
| options.js    | options.js                                          | equal to the file size on disk |

Total entry count reported: 4. Entry names containing a backslash: 0.

#### Scenario: Extracted tree loads as an unpacked extension

- **WHEN** the archive is extracted and the resulting directory is loaded as an unpacked browser extension
- **THEN** the extension loads without a manifest error

##### Example: loading the extracted directory

- **GIVEN** the distribution archive is extracted into an empty directory, yielding background.js, manifest.json, options.html, and options.js at the directory root
- **WHEN** that directory is loaded through the browser developer-mode unpacked-extension entry point
- **THEN** the extension is listed with the name declared in manifest.json and no manifest error is reported


<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->

---
### Requirement: Stable distribution archive path

The distribution archive SHALL keep its existing file name and location so release automation requires no change.

#### Scenario: Release automation locates the archive

- **WHEN** the release workflow computes checksums and uploads release assets
- **THEN** it locates the distribution archive at the same path as before this change

##### Example: the path referenced by release automation

- **GIVEN** the release workflow references `packages/browser-relay/dist/omp-browser-relay-extension.zip` in both its checksum step and its release-asset upload step
- **WHEN** the build runs to completion
- **THEN** a file exists at exactly that path, and neither workflow step requires an edit

<!-- @trace
source: remove-external-zip-dependency
updated: 2026-08-15
code:
  - biome.json
  - packages/browser-relay/scripts/build-extension.ts
  - CLAUDE.md
  - packages/coding-agent/src/utils/zip-writer.ts
  - packages/coding-agent/src/utils/zip.ts
  - .github/workflows/ci.yml
  - packages/browser-relay/CHANGELOG.md
-->