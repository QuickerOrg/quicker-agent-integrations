"""Contract tests using Windows PowerShell 5.1 and an isolated loopback HTTP server."""

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins/quicker"
TEMP_ROOT = ROOT / ".temp"
# A fresh Windows runner can take over ten seconds to start PowerShell/.NET.
# This bounds the test process wait, independently of the transport's HTTP timeout.
PROCESS_TIMEOUT_SECONDS = 30
POWERSHELL = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
if not POWERSHELL.is_file():
    POWERSHELL = shutil.which("powershell.exe")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def request(request_id=1, method="tools/list", params=None):
    value = {"jsonrpc": "2.0", "method": method}
    if request_id is not ...:
        value["id"] = request_id
    if params is not None:
        value["params"] = params
    return value


def reply(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def manifest_launch(extra_args, plugin_root=PLUGIN_ROOT):
    """Mirror Codex's legacy MCP loader: root relative cwd, pass args/env literally."""
    config = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["quicker"]
    expanded_root = str(plugin_root.resolve())
    if os.name == "nt" and not expanded_root.startswith("\\\\?\\"):
        expanded_root = "\\\\?\\" + expanded_root

    env = dict(os.environ)
    env.update({"HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1"})
    env.update(config.get("env", {}))
    return {
        "args": [config["command"], *config["args"], *extra_args],
        "cwd": str(Path(expanded_root) / config["cwd"]) if "cwd" in config else ROOT,
        "env": env,
    }


class MockHost:
    def __init__(self):
        self.requests = []
        self.responses = queue.Queue()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                owner.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                spec = owner.responses.get(timeout=5)
                if spec is None:
                    self.close_connection = True
                    return
                if spec.get("delay"):
                    time.sleep(spec["delay"])
                self.send_response(spec.get("status", 200))
                for key, value in spec.get("headers", {}).items():
                    self.send_header(key, value)
                body = spec.get("body", b"")
                self.send_header("Content-Type", spec.get("type", "application/json; charset=utf-8"))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def respond(self, value=None, **kwargs):
        if value is not None:
            kwargs["body"] = encoded(value)
        self.responses.put(kwargs)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class Bridge:
    def __init__(self, settings_path, timeout=4, plugin_root=PLUGIN_ROOT):
        self.process = subprocess.Popen(
            **manifest_launch(["-SettingsPath", str(settings_path), "-RequestTimeoutSeconds", str(timeout)], plugin_root),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="strict",
        )
        self.output = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.stderr = ""
        self.closed = False

    def _read(self):
        for line in self.process.stdout:
            self.output.put(line.rstrip("\r\n"))

    def send(self, value):
        raw = value if isinstance(value, str) else encoded(value).decode("utf-8")
        self.process.stdin.write(raw + "\n")
        self.process.stdin.flush()

    def receive(self, timeout=PROCESS_TIMEOUT_SECONDS):
        try:
            return self.output.get(timeout=timeout)
        except queue.Empty:
            raise AssertionError(f"No bridge response; process status {self.process.poll()}") from None

    def call(self, value):
        self.send(value)
        return json.loads(self.receive())

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)
        self.reader.join(timeout=2)
        self.stderr = self.process.stderr.read()
        self.process.stderr.close()
        self.process.stdout.close()


@unittest.skipUnless(POWERSHELL, "Windows PowerShell 5.1 is required")
class QuickerMcpTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="codex-mcp-test-", dir=TEMP_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.settings_path = Path(self.temp.name) / "server.json"
        self.host = MockHost()
        self.addCleanup(self.host.close)
        self.settings = {"Enabled": True, "Port": self.host.port, "AllowWrites": True,
                         "ApprovalMode": "sandbox_confirm", "Token": "qk_test_secret_DO_NOT_LOG"}
        self.save_settings()
        self.bridge = None

    def save_settings(self):
        self.settings_path.write_bytes(encoded(self.settings))

    def start(self, timeout=4):
        self.bridge = Bridge(self.settings_path, timeout)
        self.addCleanup(self.bridge.close)
        return self.bridge

    def assert_failure(self, result, code, request_id=1, unknown=False):
        self.assertEqual(result["id"], request_id)
        self.assertEqual(result["error"]["data"]["code"], code)
        self.assertEqual(result["error"]["data"]["stateUnknown"], unknown)
        self.assertNotIn("qk_test_secret", json.dumps(result))
        self.assertNotIn("sensitive-request-body", json.dumps(result))

    def test_handshake_is_forwarded_and_sets_negotiated_protocol_header(self):
        init = reply("hello", {"protocolVersion": "2025-03-26", "instructions": "编写动作\n加载技能", "capabilities": {}})
        self.host.respond(init)
        bridge = self.start()
        self.assertEqual(bridge.call(request("hello", "initialize", {"protocolVersion": "2025-06-18"})), init)
        self.host.respond(status=202)
        bridge.send(request(..., "notifications/initialized"))
        expected = reply(2, {"tools": []})
        self.host.respond(expected)
        self.assertEqual(bridge.call(request(2)), expected)
        self.assertEqual([json.loads(item["body"])["method"] for item in self.host.requests],
                         ["initialize", "notifications/initialized", "tools/list"])
        self.assertNotIn("MCP-Protocol-Version", self.host.requests[0]["headers"])
        self.assertEqual(self.host.requests[1]["headers"]["MCP-Protocol-Version"], "2025-03-26")
        self.assertEqual(self.host.requests[2]["path"], "/mcp")
        self.assertEqual(self.host.requests[2]["headers"]["Authorization"], "Bearer " + self.settings["Token"])
        self.assertTrue(bridge.output.empty(), "notifications must not produce output")

    def test_payloads_preserve_chinese_numbers_schema_and_all_content(self):
        raw_request = '{"jsonrpc":"2.0","id":9007199254740993,"method":"tools/call","params":{"arguments":{"number":123456789012345678901234567890,"text":"00123","中文":"动作\\n多行"}}}'
        raw_response = '''{
          "jsonrpc":"2.0", "id":9007199254740993,
          "result":{"schema":{"properties":{"Name":{"type":"string"},"name":{"type":"number"}}},
          "content":[{"type":"text","text":"中文\\n第二行"},{"type":"text","text":"[Rule: quicker-authoring]"},{"type":"image","data":"AA==","mimeType":"image/png"}],
          "structuredContent":{"number":123456789012345678901234567890,"text":"00123"},"isError":false}
        }'''
        self.host.respond(body=raw_response.encode("utf-8"))
        bridge = self.start()
        actual = bridge.call(raw_request)
        self.assertEqual(actual, json.loads(raw_response))
        self.assertEqual(self.host.requests[0]["body"], raw_request.encode("utf-8"))

    def test_sse_multiline_data_and_server_notifications(self):
        expected = reply(4, {"content": [{"type": "text", "text": "一\n二"}, {"type": "text", "text": "rule"}]})
        notify = request(..., "notifications/message", {"level": "info", "data": "进度"})
        body = ": keepalive\r\nevent: message\r\ndata: " + encoded(notify).decode("utf-8") + "\r\n\r\n"
        body += "event: message\nid: ignored\ndata: {\ndata: " + encoded(expected).decode("utf-8")[1:-1] + "\ndata: }\n\n"
        self.host.respond(body=body.encode("utf-8"), type="text/event-stream; charset=utf-8")
        bridge = self.start()
        bridge.send(request(4))
        self.assertEqual(json.loads(bridge.receive()), notify)
        self.assertEqual(json.loads(bridge.receive()), expected)

    def test_http_auth_errors_are_sanitized_and_keep_request_id(self):
        bridge = self.start()
        for status, code in ((401, "unauthorized"), (403, "client_not_approved")):
            self.host.respond(status=status, body=b"qk_test_secret_DO_NOT_LOG sensitive-request-body")
            result = bridge.call(request("id-" + str(status), "tools/call", {"secret": "sensitive-request-body"}))
            self.assert_failure(result, code, "id-" + str(status))
            self.assertEqual(result["error"]["data"]["httpStatus"], status)
        self.assertEqual(len(self.host.requests), 2)

    def test_missing_disabled_invalid_and_tokenless_settings_never_connect(self):
        bridge = self.start()
        self.settings_path.unlink()
        self.assert_failure(bridge.call(request()), "settings_missing")
        self.settings["Enabled"] = False
        self.save_settings()
        self.assert_failure(bridge.call(request()), "server_disabled")
        self.settings["Enabled"] = True
        self.settings["Token"] = ""
        self.save_settings()
        self.assert_failure(bridge.call(request()), "token_missing")
        for bad in ("not json", '{"Port":"127.0.0.1:99/path","Enabled":true}', '{"Port":80}', '{"Port":65536}'):
            self.settings_path.write_text(bad, encoding="utf-8")
            self.assert_failure(bridge.call(request()), "settings_invalid")
        self.assertEqual(self.host.requests, [])

    def test_settings_token_and_port_are_refreshed_for_every_request(self):
        bridge = self.start()
        self.host.respond(reply(1, {}))
        self.assertEqual(bridge.call(request()), reply(1, {}))
        next_host = MockHost()
        self.addCleanup(next_host.close)
        self.settings.update({"Port": next_host.port, "Token": "qk_rotated_secret"})
        self.save_settings()
        next_host.respond(reply(2, {}))
        self.assertEqual(bridge.call(request(2)), reply(2, {}))
        self.assertEqual(next_host.requests[0]["headers"]["Authorization"], "Bearer qk_rotated_secret")
        self.assertEqual(len(self.host.requests), 1)
        self.assertEqual(json.loads(self.settings_path.read_bytes()), self.settings, "adapter must not change settings")

    def test_redirects_are_not_followed_and_token_stays_on_loopback_endpoint(self):
        self.host.respond(status=307, headers={"Location": f"http://127.0.0.1:{self.host.port}/steal-token"})
        result = self.start().call(request())
        self.assert_failure(result, "redirect_refused")
        self.assertEqual(len(self.host.requests), 1)
        self.assertEqual(self.host.requests[0]["path"], "/mcp")

    def test_disconnect_after_post_is_not_retried_and_marks_unknown_state(self):
        self.host.responses.put(None)
        result = self.start().call(request(9007199254740993, "tools/call", {"name": "quicker_save"}))
        self.assert_failure(result, "transport_failed", 9007199254740993, unknown=True)
        self.assertEqual(len(self.host.requests), 1)

    def test_timeout_is_bounded_and_never_retries(self):
        bridge = self.start(timeout=1)
        self.host.respond(reply("ready", {}))
        self.assertEqual(bridge.call(request("ready")), reply("ready", {}))
        self.host.respond(reply(1, {}), delay=2)
        # Measure the request deadline after startup, not PowerShell cold-start time.
        start = time.monotonic()
        result = bridge.call(request())
        self.assert_failure(result, "transport_failed", unknown=True)
        self.assertLess(time.monotonic() - start, 6)
        self.assertEqual([json.loads(item["body"])["id"] for item in self.host.requests], ["ready", 1])

    def test_http_500_does_not_expose_response_and_marks_unknown_state(self):
        self.host.respond(status=500, body=b"sensitive-request-body qk_test_secret_DO_NOT_LOG")
        self.assert_failure(self.start().call(request()), "http_error", unknown=True)
        self.assertEqual(len(self.host.requests), 1)

    def test_malformed_response_is_sanitized_and_stream_survives(self):
        bridge = self.start()
        self.host.respond(body=b"<html>sensitive-request-body qk_test_secret_DO_NOT_LOG</html>")
        self.assert_failure(bridge.call(request()), "transport_failed", unknown=True)
        self.host.respond(reply(2, {"tools": []}))
        self.assertEqual(bridge.call(request(2)), reply(2, {"tools": []}))

    def test_remote_json_rpc_errors_are_forwarded_verbatim(self):
        expected = {"jsonrpc": "2.0", "id": "error", "error": {"code": -32602, "message": "无效参数", "data": {"a": "b"}}}
        self.host.respond(expected)
        self.assertEqual(self.start().call(request("error")), expected)

    def test_invalid_input_does_not_connect_or_leak_and_next_request_works(self):
        bridge = self.start()
        result = bridge.call("sensitive-request-body not json")
        self.assert_failure(result, "invalid_request", request_id=None)
        self.host.respond(reply(2, {}))
        self.assertEqual(bridge.call(request(2)), reply(2, {}))
        self.assertEqual(len(self.host.requests), 1)

    def test_notification_failure_goes_only_to_sanitized_stderr(self):
        self.settings["Enabled"] = False
        self.save_settings()
        bridge = self.start()
        bridge.send(request(..., "notifications/initialized", {"secret": "sensitive-request-body"}))
        bridge.close()
        self.assertTrue(bridge.output.empty())
        self.assertIn("server_disabled", bridge.stderr)
        self.assertNotIn("sensitive-request-body", bridge.stderr)
        self.assertNotIn(self.settings["Token"], bridge.stderr)

    def test_check_mode_is_read_only_sanitized_and_does_not_initialize(self):
        before = self.settings_path.read_bytes()
        completed = subprocess.run(
            **manifest_launch(["-SettingsPath", str(self.settings_path), "-Check"]),
            capture_output=True, encoding="utf-8", timeout=PROCESS_TIMEOUT_SECONDS,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        diagnostic = json.loads(completed.stdout)
        self.assertEqual(diagnostic, {"ok": True, "enabled": True, "allowWrites": True,
                                      "port": self.host.port, "tokenPresent": True, "portReachable": True})
        self.assertNotIn(self.settings["Token"], completed.stdout + completed.stderr)
        self.assertEqual(self.settings_path.read_bytes(), before)
        self.assertEqual(self.host.requests, [])

    def test_installed_package_path_with_spaces_and_unicode(self):
        cached_plugin = Path(self.temp.name) / "插件 cache with spaces" / "quicker"
        shutil.copytree(PLUGIN_ROOT, cached_plugin)
        bridge = Bridge(self.settings_path, plugin_root=cached_plugin)
        self.addCleanup(bridge.close)
        expected = reply(1, {"tools": []})
        self.host.respond(expected)
        self.assertEqual(bridge.call(request()), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
