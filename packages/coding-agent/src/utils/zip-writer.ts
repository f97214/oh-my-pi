// ZIP wire format: the on-disk constants shared by the reader and the writer,
// plus the container framer itself. The reading half — and the public archive
// API (`unzip`, `openArchive`, `writeArchive`) — lives in `./zip`, which
// re-exports `zip`, so application code keeps importing from `./zip`.
//
// This file is a separate module for exactly one reason:
// `packages/browser-relay/scripts/build-extension.ts` packages the extension
// zip on a CI runner that never runs `bun install` (.github/workflows/ci.yml,
// job `release_github`), so it can only import modules that resolve with zero
// node_modules. `./zip` cannot be imported there because it pulls in
// `@oh-my-pi/pi-utils`.
//
// Therefore this module imports `node:*` and `../tools/tool-errors` (itself
// dependency-free) and NOTHING ELSE. Adding a bare package specifier here — or
// to `tool-errors.ts` — breaks the GitHub release job and only the GitHub
// release job: every test, type check and local build still passes. The
// `noRestrictedImports` override in `biome.json` guards the obvious case.
import * as zlib from "node:zlib";
import { ToolError } from "../tools/tool-errors";

const ENCODER = new TextEncoder();

export const ZIP_LOCAL_FILE_HEADER_SIGNATURE = 0x04034b50;
export const ZIP_CENTRAL_DIRECTORY_HEADER_SIGNATURE = 0x02014b50;
export const ZIP64_EOCD_SIGNATURE = 0x06064b50;
export const ZIP64_EOCD_LOCATOR_SIGNATURE = 0x07064b50;
export const ZIP_EOCD_SIGNATURE = 0x06054b50;
export const ZIP_DATA_DESCRIPTOR_SIGNATURE = 0x08074b50;
export const ZIP_EOCD_MIN_LENGTH = 22;
export const ZIP_EOCD_MAX_COMMENT_LENGTH = 0xffff;
export const ZIP64_EOCD_LOCATOR_LENGTH = 20;
export const ZIP_STORED_COMPRESSION = 0;
export const ZIP_DEFLATE_COMPRESSION = 8;
export const ZIP_UTF8_FLAG = 0x0800;
export const ZIP_ENCRYPTED_FLAG = 0x0001;
export const ZIP_UINT16_MAX = 0xffff;
export const ZIP_UINT32_MAX = 0xffffffff;
export const ZIP_UINT32_RANGE = 0x100000000;

function writeUInt16LE(buf: Uint8Array, offset: number, value: number): void {
	buf[offset] = value & 0xff;
	buf[offset + 1] = (value >>> 8) & 0xff;
}

function writeUInt32LE(buf: Uint8Array, offset: number, value: number): void {
	buf[offset] = value & 0xff;
	buf[offset + 1] = (value >>> 8) & 0xff;
	buf[offset + 2] = (value >>> 16) & 0xff;
	buf[offset + 3] = (value >>> 24) & 0xff;
}
/**
 * Frame a `path → bytes` map into a ZIP archive in memory. Each member is raw
 * DEFLATE unless that would not shrink it, in which case it is stored. ZIP64 is
 * not emitted; archives beyond the 32-bit limits throw rather than corrupt.
 */
export function zip(entries: Record<string, Uint8Array>): Uint8Array {
	const localParts: Uint8Array[] = [];
	const centralParts: Uint8Array[] = [];
	let offset = 0;
	let count = 0;

	for (const name in entries) {
		const data = entries[name]!;
		const nameBytes = ENCODER.encode(name);
		const crc = zlib.crc32(data) >>> 0;
		const uncompressedSize = data.byteLength;
		const deflated = zlib.deflateRawSync(data);
		const stored = deflated.byteLength >= uncompressedSize;
		const method = stored ? ZIP_STORED_COMPRESSION : ZIP_DEFLATE_COMPRESSION;
		const payload = stored ? data : deflated;

		// Without ZIP64 the name length is a u16 and offsets/sizes are u32 (with
		// 0xffff/0xffffffff reserved as ZIP64 sentinels); reject anything that
		// would silently wrap a header field instead of producing a valid archive.
		if (
			count + 1 >= ZIP_UINT16_MAX ||
			nameBytes.byteLength > ZIP_UINT16_MAX ||
			uncompressedSize >= ZIP_UINT32_MAX ||
			offset + 30 + nameBytes.byteLength + payload.byteLength >= ZIP_UINT32_MAX
		) {
			throw new ToolError("ZIP archive is too large to write (ZIP64 is not supported)");
		}

		const header = new Uint8Array(30 + nameBytes.byteLength);
		writeUInt32LE(header, 0, ZIP_LOCAL_FILE_HEADER_SIGNATURE);
		writeUInt16LE(header, 4, 20);
		writeUInt16LE(header, 6, ZIP_UTF8_FLAG);
		writeUInt16LE(header, 8, method);
		// Fixed 1980-01-01 timestamp keeps the output deterministic.
		writeUInt16LE(header, 12, 0x21);
		writeUInt32LE(header, 14, crc);
		writeUInt32LE(header, 18, payload.byteLength);
		writeUInt32LE(header, 22, uncompressedSize);
		writeUInt16LE(header, 26, nameBytes.byteLength);
		header.set(nameBytes, 30);
		localParts.push(header, payload);

		const record = new Uint8Array(46 + nameBytes.byteLength);
		writeUInt32LE(record, 0, ZIP_CENTRAL_DIRECTORY_HEADER_SIGNATURE);
		writeUInt16LE(record, 4, 20);
		writeUInt16LE(record, 6, 20);
		writeUInt16LE(record, 8, ZIP_UTF8_FLAG);
		writeUInt16LE(record, 10, method);
		writeUInt16LE(record, 14, 0x21);
		writeUInt32LE(record, 16, crc);
		writeUInt32LE(record, 20, payload.byteLength);
		writeUInt32LE(record, 24, uncompressedSize);
		writeUInt16LE(record, 28, nameBytes.byteLength);
		writeUInt32LE(record, 42, offset);
		record.set(nameBytes, 46);
		centralParts.push(record);

		offset += header.byteLength + payload.byteLength;
		count++;
	}

	const centralSize = centralParts.reduce((sum, part) => sum + part.byteLength, 0);
	if (centralSize >= ZIP_UINT32_MAX || offset + centralSize + ZIP_EOCD_MIN_LENGTH >= ZIP_UINT32_MAX) {
		throw new ToolError("ZIP archive is too large to write (ZIP64 is not supported)");
	}
	const eocd = new Uint8Array(ZIP_EOCD_MIN_LENGTH);
	writeUInt32LE(eocd, 0, ZIP_EOCD_SIGNATURE);
	writeUInt16LE(eocd, 8, count);
	writeUInt16LE(eocd, 10, count);
	writeUInt32LE(eocd, 12, centralSize);
	writeUInt32LE(eocd, 16, offset);

	const out = new Uint8Array(offset + centralSize + ZIP_EOCD_MIN_LENGTH);
	let pos = 0;
	for (const part of localParts) {
		out.set(part, pos);
		pos += part.byteLength;
	}
	for (const part of centralParts) {
		out.set(part, pos);
		pos += part.byteLength;
	}
	out.set(eocd, pos);
	return out;
}
