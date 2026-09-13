"""Exercise installers against isolated profiles, never the signed-in user's settings."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_quicker_mcp import ROOT, TEMP_ROOT, POWERSHELL, MockHost, encoded, request, reply


class PackageTests(unittest.TestCase):
    def test_shared_sources_and_manifests(self):
        subprocess.run(['python', str(ROOT / 'scripts/sync-packages.py'), '--check'], check=True)
        for client in ('cursor', 'claude'):
            package = ROOT / 'plugins' / ('quicker-' + client)
            manifest = json.loads((package / ('.' + client + '-plugin') / 'plugin.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['name'], 'quicker')
            self.assertTrue((package / 'skills/write-action/SKILL.md').is_file())
            market = json.loads((ROOT / ('.' + client + '-plugin') / 'marketplace.json').read_text(encoding='utf-8'))
            self.assertEqual((ROOT / market['plugins'][0]['source']).resolve(), package.resolve())
        dsh = json.loads((ROOT / 'plugins/quicker-dsh/package.json').read_text(encoding='utf-8'))
        self.assertEqual(dsh['name'], 'dsh-plugin-quicker')
        self.assertEqual(dsh['dsh']['bundle']['patch'], './cordis.patch.yml')
        self.assertTrue((ROOT / 'plugins/quicker-dsh/index.js').is_file())
        self.assertTrue((ROOT / 'plugins/quicker-dsh/cordis.patch.yml').is_file())
        self.assertTrue((ROOT / 'plugins/quicker-dsh/skills/write-action/SKILL.md').is_file())
        index = (ROOT / 'plugins/quicker-dsh/index.js').read_text(encoding='utf-8')
        self.assertIn("@deepseek-ai/dsh-mcp-client", index)
        self.assertIn("'dsh'", index)
        self.assertIn('agent/session-start', index)
        self.assertIn('loader.create', index)
        self.assertIn("'loader'", index)
        self.assertNotIn("ctx.plugin('@deepseek-ai/dsh-mcp-client'", index)


@unittest.skipUnless(POWERSHELL, 'Windows PowerShell required')
class InstallTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='安装 用户 ', dir=TEMP_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name)

    def install(self, client, *args, success=True):
        result = subprocess.run([str(POWERSHELL), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                 str(ROOT / 'scripts/install-client.ps1'), '-Client', client,
                                 '-UserRoot', str(self.profile), *args], capture_output=True, timeout=45)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def config(self, client):
        return self.profile / ('AppData/Roaming/Code/User/mcp.json' if client == 'vscode' else '.gemini/settings.json')

    def test_install_update_uninstall_preserves_other_configuration(self):
        for client in ('vscode', 'gemini'):
            with self.subTest(client=client):
                path = self.config(client)
                section = 'servers' if client == 'vscode' else 'mcpServers'
                original = {section: {'other': {'command': 'keep-me'}}, 'otherPreference': {'unicode': '保留', 'enabled': True}}
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(encoded(original))
                self.install(client)
                config = json.loads(path.read_text(encoding='utf-8'))
                entry = config[section]['quicker']
                self.assertEqual(config[section]['other'], original[section]['other'])
                self.assertEqual(config['otherPreference'], original['otherPreference'])
                self.assertNotIn('token', json.dumps(entry).lower())
                self.assertTrue(Path(entry['args'][6]).is_file())
                self.install(client)
                self.install(client, '-Uninstall')
                self.assertEqual(json.loads(path.read_text(encoding='utf-8')), original)

    def test_foreign_mcp_entry_is_not_replaced(self):
        path = self.config('gemini')
        path.parent.mkdir(parents=True)
        contents = b'{"mcpServers":{"quicker":{"command":"foreign"}}}'
        path.write_bytes(contents)
        self.install('gemini', success=False)
        self.assertEqual(path.read_bytes(), contents)
        self.assertFalse((self.profile / '.quicker/agent-integrations/gemini').exists())

    def test_cursor_package_discovery_update_and_local_edits(self):
        self.install('cursor')
        target = self.profile / '.cursor/plugins/local/quicker'
        self.assertTrue((target / '.cursor-plugin/plugin.json').is_file())
        self.assertTrue((target / 'mcp.json').is_file())
        self.install('cursor')
        (target / 'custom.txt').write_text('keep', encoding='utf-8')
        self.install('cursor', success=False)
        self.install('cursor', '-Uninstall', success=False)
        self.assertEqual((target / 'custom.txt').read_text(), 'keep')

    def test_invalid_json_leaves_existing_file_untouched(self):
        path = self.config('vscode')
        path.parent.mkdir(parents=True)
        contents = b'{ // user comment\n "servers": {} }'
        path.write_bytes(contents)
        self.install('vscode', success=False)
        self.assertEqual(path.read_bytes(), contents)

    def test_foreign_local_plugin_is_not_replaced(self):
        target = self.profile / '.cursor/plugins/local/quicker'
        target.mkdir(parents=True)
        (target / 'keep').write_text('foreign')
        self.install('cursor', success=False)
        self.assertEqual((target / 'keep').read_text(), 'foreign')

    def test_each_plugin_launches_from_unrelated_directory(self):
        for client, variable in [('cursor', 'CURSOR_PLUGIN_ROOT'), ('claude', 'CLAUDE_PLUGIN_ROOT'), ('dsh', None)]:
            with self.subTest(client=client):
                host = MockHost()
                try:
                    settings = self.profile / 'fixture.json'
                    settings.write_bytes(encoded({'Enabled': True, 'Port': host.port, 'Token': 'test-only-token'}))
                    package = self.profile / '插件 缓存' / ('quicker-' + client)
                    shutil.copytree(ROOT / 'plugins' / ('quicker-' + client), package)
                    if variable:
                        config = json.loads((package / ('mcp.json' if client == 'cursor' else '.mcp.json')).read_text(encoding='utf-8'))['mcpServers']['quicker']
                        args = [a.replace('${' + variable + '}', str(package)) for a in config['args']]
                    else:
                        args = ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                '-File', str(package / 'scripts/quicker-mcp.ps1'), '-Client', client]
                    host.respond(reply(1, {'tools': [], 'extra': '中文保真'}))
                    result = subprocess.run([str(POWERSHELL), *args, '-SettingsPath', str(settings)],
                                            input=encoded(request()) + b'\n', capture_output=True, cwd=self.profile, timeout=35)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)['result']['extra'], '中文保真')
                    headers = {k.lower(): v for k, v in host.requests[0]['headers'].items()}
                    self.assertEqual(headers['mcp-client-info'], client + '-quicker-plugin')
                    self.assertNotIn(b'test-only-token', result.stdout + result.stderr)
                finally:
                    host.close()

    def test_dsh_package_install_update_and_local_edits(self):
        result = self.install('dsh')
        target = self.profile / '.quicker/agent-integrations/dsh'
        self.assertTrue((target / 'package.json').is_file())
        self.assertTrue((target / 'index.js').is_file())
        self.assertTrue((target / 'cordis.patch.yml').is_file())
        self.assertTrue((target / 'scripts/quicker-mcp.ps1').is_file())
        if shutil.which('dsh') is None:
            self.assertIn(b'dsh CLI was not found', result.stdout)
        self.install('dsh')
        (target / 'custom.txt').write_text('keep', encoding='utf-8')
        self.install('dsh', success=False)
        self.install('dsh', '-Uninstall', success=False)
        self.assertEqual((target / 'custom.txt').read_text(), 'keep')
