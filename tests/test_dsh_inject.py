"""Replay the DSH session-load failure against the local DeepSeek Harness validator."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve().parent / "dsh_inject_reload.mjs"
EVIDENCE = Path(r"C:\Users\ldy\Downloads\session.v3.jsonl")


def resolve_dsh_node_modules() -> Path | None:
    override = os.environ.get("DSH_NODE_MODULES")
    if override:
        root = Path(override)
        if (root / "@deepseek-ai" / "dsh-session").is_dir():
            return root
    cache = Path(os.environ.get("LOCALAPPDATA", "")) / "npm-cache" / "_npx"
    if cache.is_dir():
        matches = sorted(cache.glob("*/node_modules/@deepseek-ai/dsh-session"), key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return matches[0].parents[1]
    return None


@unittest.skipUnless(shutil.which("node"), "Node is required to load the DSH plugin")
class DshInjectReloadTests(unittest.TestCase):
    def test_broken_inject_fails_dsh_reload_and_fixed_inject_passes(self) -> None:
        node_modules = resolve_dsh_node_modules()
        if node_modules is None:
            self.skipTest("local @deepseek-ai/dsh-session was not found")
        env = os.environ.copy()
        env["DSH_SESSION_ENTRY"] = str(node_modules / "@deepseek-ai" / "dsh-session" / "lib" / "index.js")
        if EVIDENCE.is_file():
            env["QUICKER_DSH_SESSION_JSONL"] = str(EVIDENCE)
        result = subprocess.run(
            ["node", str(SCRIPT)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("lacks an identified message", payload["brokenError"])
        self.assertTrue(payload["fixedId"])
        self.assertTrue(payload["injectedId"])
