# Changelog

## [Unreleased]

### Changed

- Build the release archive in process instead of shelling out to the Unix `zip` binary, so `bun run build` works on Windows without any external tool.
- Archive contents are now enumerated recursively and sorted by entry name, making `omp-browser-relay-extension.zip` byte-deterministic; its SHA256 changes once as a result of the new framing.
## [18.0.7] - 2026-08-26

### Changed

- Clarified the scope of the two browser relay opt-in paths: per-call `app.relay: true` enables relay access for an individual call, while the `browser.relay` setting enables it by default across projects in a profile.

## [17.2.5] - 2026-08-03

### Added

- Initial release of the Chrome MV3 extension, enabling the omp browser tool to attach to and drive existing browser tabs via chrome.debugger.
- Added automatic, robust tab management that groups active agent-driven tabs into a dedicated per-window "omp" tab group and ensures clean dissolution upon disconnect.
