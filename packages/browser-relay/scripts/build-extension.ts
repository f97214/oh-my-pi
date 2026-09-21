/**
 * Builds the browser relay extension and its distribution artifacts:
 * - `dist/extension/` — unpacked extension (load via chrome://extensions)
 * - `../coding-agent/src/tools/browser/relay/extension-assets/*.txt` —
 *   generated text assets embedded into the omp CLI so `omp browser-relay
 *   install` works from the compiled binary (same committed-generated-output
 *   pattern as tool-views.generated.js). Re-run this script after touching
 *   anything under `extension/` and commit the regenerated assets.
 * - `dist/omp-browser-relay-extension.zip` — packaged extension for GH releases
 *
 * The embedded assets are written before the zip because they are what local
 * development and the compiled binary consume; the zip is a release-only
 * artifact and must not be able to strand them.
 *
 * Dependency-free on purpose: CI runs this without `bun install`, and now
 * without a `zip` binary either (Windows has none). Only `node:*`, Bun globals,
 * and relative modules that are themselves free of bare package specifiers may
 * be imported here — hence `../../coding-agent/src/utils/zip-writer` rather
 * than `.../utils/zip`, which pulls in `@oh-my-pi/pi-utils`.
 */
import * as fs from "node:fs/promises";
import * as path from "node:path";
import { zip } from "../../coding-agent/src/utils/zip-writer";

const root = path.resolve(import.meta.dir, "..");
const repoRoot = path.resolve(root, "../..");
const dist = path.join(root, "dist");
const distExtension = path.join(dist, "extension");
const assetsDir = path.resolve(root, "../coding-agent/src/tools/browser/relay/extension-assets");

await fs.rm(dist, { recursive: true, force: true });
await fs.mkdir(distExtension, { recursive: true });

const bundle = await Bun.build({
	entrypoints: [path.join(root, "extension/background.ts")],
	outdir: distExtension,
	target: "browser",
	sourcemap: "none",
});
if (!bundle.success) {
	for (const log of bundle.logs) console.error(log);
	process.exit(1);
}

for (const file of ["manifest.json", "options.html", "options.js"]) {
	await Bun.write(path.join(distExtension, file), Bun.file(path.join(root, "extension", file)));
}
for (const file of ["LICENSE", "THIRD-PARTY-NOTICES.txt"]) {
	await Bun.write(path.join(distExtension, file), Bun.file(path.join(repoRoot, file)));
}

await fs.rm(assetsDir, { recursive: true, force: true });
const embeddedAssets = [
	["background.js", "background.js.txt"],
	["manifest.json", "manifest.json.txt"],
	["options.html", "options.html.txt"],
	["options.js", "options.js.txt"],
	["LICENSE", "LICENSE.txt"],
	["THIRD-PARTY-NOTICES.txt", "THIRD-PARTY-NOTICES.txt"],
] as const;
for (const [source, destination] of embeddedAssets) {
	await Bun.write(path.join(assetsDir, destination), Bun.file(path.join(distExtension, source)));
}

// `zip -qr ../omp-browser-relay-extension.zip .`, minus the Unix `zip` binary.
// Recursive rather than a hardcoded four-file list so a future Bun.build output
// — a chunk, a wasm blob — cannot be silently dropped.
const members: [name: string, bytes: Uint8Array][] = [];
for (const entry of await fs.readdir(distExtension, { withFileTypes: true, recursive: true })) {
	if (!entry.isFile()) continue;
	const absolute = path.join(entry.parentPath, entry.name);
	// ZIP entry names are forward-slash separated on the wire and that is what
	// Chrome expects; `path.relative` yields backslashes on Windows. Same
	// normalization `writeArchive` applies in `../../coding-agent/src/utils/zip`.
	const name = path.relative(distExtension, absolute).replaceAll("\\", "/");
	members.push([name, await Bun.file(absolute).bytes()]);
}
// Sorted so the released archive's SHA256 depends only on file contents, not on
// directory-iteration order (`zip()` already pins the timestamp to 1980-01-01).
members.sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
const zipPath = path.join(dist, "omp-browser-relay-extension.zip");
await Bun.write(zipPath, zip(Object.fromEntries(members)));

console.log("built:");
console.log(`  ${distExtension}`);
console.log(`  ${assetsDir} (embedded CLI assets — commit these)`);
console.log(`  ${zipPath}`);
