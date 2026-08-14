#!/usr/bin/env python3
"""Tests for intentionally duplicated downstream governance contracts."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

CONTRACTS = {
    "adr": (
        ROOT / ".claude" / "skills" / "grill" / "ADR-FORMAT.md",
        ROOT
        / ".agents"
        / "skills"
        / "bootstrap-ai-project"
        / "templates"
        / "rules"
        / "adr.md",
    ),
    "glossary": (
        ROOT / ".claude" / "skills" / "grill" / "CONTEXT-FORMAT.md",
        ROOT
        / ".agents"
        / "skills"
        / "bootstrap-ai-project"
        / "templates"
        / "rules"
        / "glossary.md",
    ),
}


def shared_block(path: Path, contract: str) -> str:
    start = f"<!-- shared-contract:{contract}:start -->"
    end = f"<!-- shared-contract:{contract}:end -->"
    text = path.read_text(encoding="UTF-8")
    if text.count(start) != 1 or text.count(end) != 1:
        raise AssertionError(
            f"{path} 必須各包含一個 {start} 與 {end}"
        )
    return text.split(start, 1)[1].split(end, 1)[0]


class SharedContractTests(unittest.TestCase):
    def test_shared_contract_blocks_match(self) -> None:
        for contract, paths in CONTRACTS.items():
            with self.subTest(contract=contract):
                blocks = [shared_block(path, contract) for path in paths]
                self.assertTrue(blocks[0].strip(), f"{contract} 共用區塊不可為空")
                self.assertEqual(blocks[0], blocks[1])


if __name__ == "__main__":
    unittest.main()
