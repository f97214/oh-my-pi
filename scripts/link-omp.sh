#!/bin/sh
# Install the dev `omp` wrapper into Bun's global bin directory.
#
# Replaces the bun-shebang symlink that `bun --cwd=packages/coding-agent link`
# creates (pointing at `src/cli.ts`) with the safer wrapper at
# `packages/coding-agent/scripts/omp`. See that wrapper's header comment for the
# bunfig.toml-preload bug it works around.
#
# We resolve Bun's global bin path defensively because `bun pm -g bin` aborts
# (`No package.json was found for directory "$HOME/.bun/install/global"`) on
# fresh hosts where the global install has not been initialized. Falling
# through that error would expand `$(bun pm -g bin)/omp` to `/omp` and try to
# write under `/` — see https://github.com/can1357/oh-my-pi/issues/3701.
set -e

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd -P)
target=$repo_root/packages/coding-agent/scripts/omp

if [ ! -x "$target" ]; then
	echo "link-omp: target wrapper not found or not executable: $target" >&2
	exit 1
fi

global_bin=$(bun pm -g bin 2>/dev/null || true)
if [ -z "$global_bin" ]; then
	global_bin=${BUN_INSTALL:-$HOME/.bun}/bin
fi

mkdir -p "$global_bin"
ln -sfn "$target" "$global_bin/omp"
echo "link-omp: linked $global_bin/omp -> $target"

# PowerShell and cmd.exe cannot execute an extensionless shell script, so on
# Windows the wrapper above only ever serves Git Bash. Install the cmd.exe half
# beside it. It is copied rather than linked because `ln -s` degrades to a copy
# under MSYS anyway, and because that launcher finds the CLI through Bun's
# global link rather than through this checkout -- so a copy does not go stale
# when the repository moves.
case $(uname -s) in
MINGW* | MSYS* | CYGWIN*)
	cmd_target=$repo_root/packages/coding-agent/scripts/omp.cmd
	if [ ! -f "$cmd_target" ]; then
		echo "link-omp: Windows launcher not found: $cmd_target" >&2
		exit 1
	fi
	# That launcher is ASCII-only so cmd.exe reads it correctly under any console
	# code page. The guarantee dies if Bun's install root -- which the launcher
	# embeds -- is itself non-ASCII, so refuse rather than install a broken .cmd.
	bun_root=${BUN_INSTALL:-$HOME/.bun}
	if printf '%s' "$bun_root" | LC_ALL=C grep -q '[^ -~]'; then
		echo "link-omp: WARNING: Bun's install root contains non-ASCII characters:" >&2
		echo "link-omp:   $bun_root" >&2
		echo "link-omp: skipping the Windows launcher; omp will work from Git Bash only." >&2
		echo "link-omp: set BUN_INSTALL to an ASCII path and re-run to fix this." >&2
	else
		cp -f "$cmd_target" "$global_bin/omp.cmd"
		echo "link-omp: installed $global_bin/omp.cmd"
	fi
	# The `ln -sfn` above degrades to a plain copy under MSYS, and the wrapper
	# locates the checkout by resolving its own symlink -- a copy has nothing to
	# resolve, so it looks for src/cli.ts beside Bun's bin directory and dies.
	# Overwrite that copy with a shim naming the checkout outright. sh reads
	# UTF-8, so a non-ASCII checkout path is fine here, unlike the .cmd above.
	cat > "$global_bin/omp" <<SHIM
#!/bin/sh
exec "$target" "\$@"
SHIM
	chmod +x "$global_bin/omp"
	echo "link-omp: rewrote $global_bin/omp as a shim (a copied wrapper cannot find the checkout)"
	# `bun link` leaves omp.exe/omp.bunx here on Windows, and PATHEXT resolves
	# .EXE before .CMD -- so leaving them shadows the launcher above with exactly
	# the bun-shebang bin this script exists to replace, the one that skips the
	# bunfig preload guard (#3701). Removing them is the Windows spelling of the
	# symlink overwrite that `ln -sfn` performs on POSIX.
	if [ -e "$global_bin/omp.exe" ] || [ -e "$global_bin/omp.bunx" ]; then
		rm -f "$global_bin/omp.exe" "$global_bin/omp.bunx"
		echo "link-omp: removed the bun-shebang shim that would shadow omp.cmd"
	fi
	;;
esac

# Installing into a directory that nobody's PATH mentions is, from the user's
# side, a silent no-op. Say so, and print the path in the form this platform's
# shells expect -- but never edit PATH here; that is the user's call.
case ":$PATH:" in
*":$global_bin:"*) ;;
*)
	display_bin=$global_bin
	if command -v cygpath >/dev/null 2>&1; then
		display_bin=$(cygpath -w "$global_bin" 2>/dev/null || printf '%s' "$global_bin")
	fi
	echo "link-omp: NOTE: this directory is not on your PATH:"
	echo "link-omp:   $display_bin"
	echo "link-omp: add it to run omp from any directory. PATH was not modified."
	;;
esac
