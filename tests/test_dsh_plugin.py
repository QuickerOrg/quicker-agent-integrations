"""Register the DSH write-action skill as a catalog card instead of injecting it."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve().parent / "dsh_plugin.mjs"
INDEX = ROOT / "plugins/quicker-dsh/index.js"


@unittest.skipUnless(shutil.which("node"), "Node is required to load the DSH plugin")
class DshPluginTests(unittest.TestCase):
    def test_write_action_skill_registers_without_session_inject(self) -> None:
        result = subprocess.run(
            ["node", str(SCRIPT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["skill"], "write-action")
        self.assertGreater(payload["descriptionChars"], 20)
        self.assertLess(payload["descriptionChars"], 500)
        self.assertGreater(payload["contentChars"], payload["descriptionChars"])
        self.assertEqual(payload["mcpClient"], "@deepseek-ai/dsh-mcp-client")
        self.assertEqual(payload["injectedEvents"], [])

    def test_plugin_source_does_not_inject_authoring_guide(self) -> None:
        index = INDEX.read_text(encoding="utf-8")
        self.assertIn("ctx.skills.register", index)
        self.assertIn("write-action", index)
        self.assertIn("'skills'", index)
        self.assertNotIn("agent/session-start", index)
        self.assertNotIn("agent.inject", index)
        self.assertNotIn("randomUUID", index)
        self.assertNotIn("createAuthoringGuideMessage", index)
