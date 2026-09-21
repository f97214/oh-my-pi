#!/usr/bin/env python3
"""Isolated compatibility check for the supplemental evidence report."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
REPORT_TEMPLATE = SKILL / "templates" / "test-evidence.md"
EXPECTED_SPECTRA = "spectra 2.3.1"


class SpectraCompatibilityTests(unittest.TestCase):
    def run_spectra(
        self, executable: str, cwd: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [executable, "--no-color", *arguments],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="UTF-8",
            timeout=30,
            check=False,
        )
        self.assertEqual(
            0,
            completed.returncode,
            completed.stdout + completed.stderr,
        )
        return completed

    def test_report_validates_and_survives_archive_on_spectra_2_3_1(self) -> None:
        executable = shutil.which("spectra")
        if not executable:
            self.skipTest("Spectra CLI 不可用")
        version = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            encoding="UTF-8",
            timeout=10,
            check=False,
        )
        if version.returncode != 0 or not version.stdout.startswith(EXPECTED_SPECTRA):
            self.skipTest(
                f"需要 {EXPECTED_SPECTRA}，目前為 {version.stdout.strip() or 'unknown'}"
            )

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "spectra-fixture"
            target.mkdir()
            role_skill = target / ".agents" / "skills" / "doc-writer" / "SKILL.md"
            role_skill.parent.mkdir(parents=True)
            role_skill.write_text("canonical role sentinel\n", encoding="UTF-8")
            self.run_spectra(
                executable,
                target,
                "init",
                str(target),
                "--tools",
                "claude,codex",
            )
            self.assertTrue(
                (target / ".claude" / "skills" / "spectra-propose" / "SKILL.md").is_file()
            )
            self.assertTrue(
                (target / ".agents" / "skills" / "spectra-propose" / "SKILL.md").is_file()
            )
            self.assertEqual(
                "canonical role sentinel\n", role_skill.read_text(encoding="UTF-8")
            )
            self.run_spectra(executable, target, "demo")
            listed = json.loads(
                self.run_spectra(executable, target, "list", "--json").stdout
            )
            self.assertEqual(1, len(listed["changes"]))
            change = listed["changes"][0]["name"]
            active = target / "openspec" / "changes" / change
            report = active / "test-evidence.md"
            expected_report = REPORT_TEMPLATE.read_text(encoding="UTF-8")
            report.write_text(expected_report, encoding="UTF-8")

            validated = json.loads(
                self.run_spectra(
                    executable,
                    target,
                    "validate",
                    change,
                    "--strict",
                    "--json",
                ).stdout
            )
            self.assertEqual(
                [{"change": change, "errors": [], "valid": True, "warnings": []}],
                validated,
            )

            self.run_spectra(
                executable,
                target,
                "archive",
                change,
                "--yes",
                "--skip-specs",
                "--mark-tasks-complete",
            )
            archive_root = target / "openspec" / "changes" / "archive"
            matches = [
                path
                for path in archive_root.iterdir()
                if path.is_dir() and path.name.endswith("-" + change)
            ]
            self.assertEqual(1, len(matches))
            archived_report = matches[0] / "test-evidence.md"
            self.assertTrue(archived_report.is_file())
            self.assertEqual(
                expected_report,
                archived_report.read_text(encoding="UTF-8"),
            )


if __name__ == "__main__":
    unittest.main()
