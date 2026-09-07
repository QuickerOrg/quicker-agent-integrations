"""Build release archives from isolated Git tags, never from a developer's checkout."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT / ".temp"
SCRIPT = ROOT / "scripts/package-release.py"
TAG = "v1.2.3"
RELEASE_VERSION = "1.2.3"
SHARED_FILES = (
    "scripts/quicker-mcp.ps1",
    "skills/write-action/SKILL.md",
    "skills/write-action/references/connection.md",
)
PACKAGES = (
    {"id": "codex", "path": "plugins/quicker", "manifest": ".codex-plugin/plugin.json",
     "mcpConfig": ".mcp.json", "marketplace": ".agents/plugins/marketplace.json"},
    {"id": "cursor", "path": "plugins/quicker-cursor", "manifest": ".cursor-plugin/plugin.json",
     "mcpConfig": "mcp.json", "marketplace": ".cursor-plugin/marketplace.json"},
    {"id": "claude", "path": "plugins/quicker-claude", "manifest": ".claude-plugin/plugin.json",
     "mcpConfig": ".mcp.json", "marketplace": ".claude-plugin/marketplace.json"},
    {"id": "mcp", "path": "plugins/quicker-mcp", "manifest": "package.json"},
)
PACKAGE_VERSIONS = {"codex": "0.2.0", "cursor": "0.2.0", "claude": "0.2.1", "mcp": "0.2.0"}
EXPECTED_ZIPS = {"quicker-agent-integrations-1.2.3.zip"} | {
    f"quicker-{package['id']}-1.2.3.zip" for package in PACKAGES
}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(shutil.which("git"), "Git required for isolated release fixtures")
class ReleasePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("quicker_package_release", SCRIPT)
        cls.release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.release)

    def setUp(self):
        TEMP_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="release-test-", dir=TEMP_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.output = self.base / "dist"
        self.git("init", "--quiet")
        self.files = {
            ".gitignore": b".temp/\ndist/\nplugins/codex/\n",
            "README.md": "Tagged source; 插件版本与发布版本分开。\n".encode("utf-8"),
            "LICENSE": b"Fixture root license\n",
            "docs/release.md": b"A tracked document belongs in the source archive.\n",
            "scripts/release-packages.json": json_bytes({
                "schemaVersion": 1,
                "sharedFiles": list(SHARED_FILES),
                "packages": list(PACKAGES),
            }),
        }
        for relative in SHARED_FILES:
            self.files["shared/" + relative] = f"Tagged shared content: {relative}\n".encode()
        for package in PACKAGES:
            prefix = package["path"] + "/"
            self.files[prefix + "README.md"] = f"Install {package['id']} from this package.\n".encode()
            self.files[prefix + package["manifest"]] = json_bytes({
                "name": "quicker-mcp" if package["id"] == "mcp" else "quicker",
                "version": PACKAGE_VERSIONS[package["id"]],
            })
            for relative in SHARED_FILES:
                self.files[prefix + relative] = self.files["shared/" + relative]
            if "mcpConfig" in package:
                self.files[prefix + package["mcpConfig"]] = json_bytes({
                    "mcpServers": {"quicker": {"command": "powershell.exe"}}
                })
            if "marketplace" in package:
                source = "./" + package["path"]
                if package["id"] == "codex":
                    source = {"source": "local", "path": source}
                self.files[package["marketplace"]] = json_bytes({
                    "name": "fixture-marketplace",
                    "owner": {"name": "Fixture"},
                    "plugins": [{"name": "quicker", "source": source}],
                })
        # A committed license and a missing package license must yield the same root notice.
        self.files["plugins/quicker/LICENSE"] = self.files["LICENSE"]
        for relative, content in self.files.items():
            self.write(relative, content)
        self.commit("Initial tagged fixture")
        self.git("tag", TAG)
        self.source_commit = self.git("rev-parse", "HEAD")

    def git(self, *args):
        # Ignore a caller's Git environment so no operation can escape this fixture repository.
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
        result = subprocess.run(
            ["git", "-C", str(self.repo), "-c", "core.autocrlf=false",
             "-c", f"core.hooksPath={self.base / 'no-hooks'}", "-c", "commit.gpgSign=false",
             "-c", "tag.gpgSign=false", "-c", "user.name=Release Fixture",
             "-c", "user.email=fixture@example.invalid", *args],
            check=True, capture_output=True, text=True, encoding="utf-8", env=env, timeout=30,
        )
        return result.stdout.strip()

    def write(self, relative, content):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def commit(self, message):
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", message)

    def tag_changes(self, tag="v1.2.4"):
        self.commit("Changed release fixture")
        self.git("tag", tag)
        return tag

    def build(self, tag=TAG, output=None):
        return self.release.build_release(self.repo, tag, output or self.output)

    def verify(self, tag=TAG):
        return self.release.verify_release(self.repo, tag, self.output)

    def assert_rejected(self, action):
        with self.assertRaises((ValueError, RuntimeError)):
            action()

    def resign_checksums(self):
        # Deliberately re-sign tampered metadata: verification must still bind it to the Git tag.
        paths = sorted([*self.output.glob("*.zip"), self.output / "release-manifest.json"])
        (self.output / "SHA256SUMS.txt").write_text(
            "".join(f"{sha256(path)}  {path.name}\n" for path in paths), encoding="utf-8"
        )

    def test_all_four_plugins_are_packaged_even_with_different_unchanged_versions(self):
        manifest = self.build()
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["tag"], TAG)
        self.assertEqual(manifest["sourceCommit"], self.source_commit)
        self.assertEqual(manifest["releaseVersion"], RELEASE_VERSION)
        self.assertEqual(set(path.name for path in self.output.iterdir()),
                         EXPECTED_ZIPS | {"release-manifest.json", "SHA256SUMS.txt"})
        artifacts = manifest["artifacts"]
        self.assertEqual(len(artifacts), 5)
        plugins = {artifact["id"]: artifact for artifact in artifacts if artifact["kind"] == "plugin"}
        self.assertEqual(set(plugins), {"codex", "cursor", "claude", "mcp"})
        for package in PACKAGES:
            with self.subTest(package=package["id"]):
                artifact = plugins[package["id"]]
                self.assertEqual(artifact["packageVersion"], PACKAGE_VERSIONS[package["id"]])
                self.assertEqual(artifact["packageName"], "quicker-mcp" if package["id"] == "mcp" else "quicker")
                self.assertEqual(artifact["path"], package["path"])
                self.assertEqual(artifact["manifest"], package["manifest"])
                self.assertEqual(artifact["root"], "quicker/")
                archive_path = self.output / artifact["file"]
                self.assertEqual(artifact["size"], archive_path.stat().st_size)
                self.assertEqual(artifact["sha256"], sha256(archive_path))
                with zipfile.ZipFile(archive_path) as archive:
                    package_files = {path.removeprefix(package["path"] + "/"): content
                                     for path, content in self.files.items()
                                     if path.startswith(package["path"] + "/")}
                    package_files.setdefault("LICENSE", self.files["LICENSE"])
                    members = {name for name in archive.namelist() if not name.endswith("/")}
                    self.assertEqual(members, {"quicker/" + path for path in package_files})
                    for path, content in package_files.items():
                        self.assertEqual(archive.read("quicker/" + path), content)
        self.assertEqual(self.verify(), manifest)

    def test_source_and_plugins_use_only_tagged_files_despite_new_head_and_dirty_checkout(self):
        self.write("README.md", b"Committed after the release tag\n")
        self.write("shared/scripts/quicker-mcp.ps1", b"Changed after the tag\n")
        self.commit("Changes after tag must not enter the release")
        self.write("scripts/release-packages.json", b"invalid dirty inventory")
        self.write("plugins/quicker/README.md", b"Dirty package document")
        self.write("plugins/untracked/secret.txt", b"untracked")
        self.write("plugins/codex/private.txt", b"ignored legacy staging output")
        self.write(".temp/private.txt", b"ignored temporary output")
        manifest = self.build()
        source = next(item for item in manifest["artifacts"] if item["kind"] == "source")
        self.assertEqual(source["file"], "quicker-agent-integrations-1.2.3.zip")
        self.assertEqual(source["root"], "quicker-agent-integrations-1.2.3/")
        with zipfile.ZipFile(self.output / source["file"]) as archive:
            members = {name for name in archive.namelist() if not name.endswith("/")}
            self.assertEqual(members, {source["root"] + path for path in self.files})
            for path, content in self.files.items():
                self.assertEqual(archive.read(source["root"] + path), content)
        for package in PACKAGES:
            with zipfile.ZipFile(self.output / f"quicker-{package['id']}-1.2.3.zip") as archive:
                self.assertEqual(archive.read("quicker/README.md"), self.files[package["path"] + "/README.md"])
        self.assertEqual(self.verify()["sourceCommit"], self.source_commit)

    def test_checksums_cover_exactly_all_archives_and_release_manifest(self):
        self.build()
        checksums = {}
        for line in (self.output / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            digest, name = line.split("  ", 1)
            self.assertNotIn(name, checksums)
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            checksums[name] = digest
        self.assertEqual(set(checksums), EXPECTED_ZIPS | {"release-manifest.json"})
        for name, digest in checksums.items():
            self.assertEqual(digest, sha256(self.output / name))

    def test_build_accepts_empty_directory_but_never_overwrites_existing_output(self):
        self.output.mkdir()
        self.build()
        sentinel = self.output / "do-not-overwrite.txt"
        sentinel.write_bytes(b"keep")
        manifest_before = (self.output / "release-manifest.json").read_bytes()
        self.assert_rejected(self.build)
        self.assertEqual(sentinel.read_bytes(), b"keep")
        self.assertEqual((self.output / "release-manifest.json").read_bytes(), manifest_before)

    def test_tag_is_required_and_cannot_be_a_branch_or_arbitrary_git_expression(self):
        self.git("branch", "9.8.7")
        for tag in ("9.8.7", "v8.7.6", "HEAD", "", "../v1.2.3", "v1.2", "v1.2.3^", "refs/tags/v1.2.3"):
            with self.subTest(tag=tag):
                self.assert_rejected(lambda: self.build(tag))

    def test_existing_tags_with_invalid_semver_identifiers_are_rejected(self):
        for tag in ("v1.2.3-01", "v1.2.3-alpha.01", "v1.2.3-", "v1.2.3+"):
            with self.subTest(tag=tag):
                self.git("tag", tag)
                self.assert_rejected(lambda: self.build(tag, self.base / tag))

    def test_annotated_prerelease_tag_without_v_keeps_release_and_package_versions_separate(self):
        tag = "1.2.3-rc.1+build.7"
        self.git("tag", "--annotate", tag, "--message", "Fixture prerelease")
        manifest = self.build(tag)
        self.assertEqual(manifest["tag"], tag)
        self.assertEqual(manifest["releaseVersion"], tag)
        self.assertEqual(manifest["sourceCommit"], self.source_commit)
        self.assertEqual({item["packageVersion"] for item in manifest["artifacts"] if item["kind"] == "plugin"},
                         {"0.2.0", "0.2.1"})
        self.assertEqual(self.verify(tag), manifest)

    def test_missing_archive_and_extra_publishable_file_are_rejected(self):
        self.build()
        archive = self.output / "quicker-cursor-1.2.3.zip"
        contents = archive.read_bytes()
        archive.unlink()
        self.assert_rejected(self.verify)
        archive.write_bytes(contents)
        (self.output / "quicker-legacy-1.2.3.zip").write_bytes(b"unexpected publication")
        self.assert_rejected(self.verify)

    def test_tampered_archive_is_rejected(self):
        self.build()
        archive = self.output / "quicker-mcp-1.2.3.zip"
        with archive.open("ab") as stream:
            stream.write(b"tampered")
        self.assert_rejected(self.verify)

    def test_tampered_or_incomplete_checksum_list_is_rejected(self):
        self.build()
        path = self.output / "SHA256SUMS.txt"
        original = path.read_text(encoding="utf-8")
        path.write_text("0" * 64 + original[64:], encoding="utf-8")
        self.assert_rejected(self.verify)
        path.write_text("\n".join(original.splitlines()[1:]) + "\n", encoding="utf-8")
        self.assert_rejected(self.verify)

    def test_resigned_manifest_metadata_or_missing_plugin_is_rejected(self):
        manifest = self.build()
        manifest_path = self.output / "release-manifest.json"
        mutations = (
            lambda value: value.update(sourceCommit="0" * 40),
            lambda value: value.update(releaseVersion="7.7.7"),
            lambda value: value.update(tag="v7.7.7"),
            lambda value: value["artifacts"].pop(),
            lambda value: next(item for item in value["artifacts"] if item["kind"] == "plugin").update(packageVersion="7.7.7"),
            lambda value: next(item for item in value["artifacts"] if item["kind"] == "plugin").update(root="wrong/"),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                changed = json.loads(json.dumps(manifest))
                mutate(changed)
                manifest_path.write_bytes(json_bytes(changed))
                self.resign_checksums()
                self.assert_rejected(self.verify)

    def test_archive_with_resigned_hashes_must_still_match_tagged_contents(self):
        manifest = self.build()
        artifact = next(item for item in manifest["artifacts"] if item.get("id") == "claude")
        archive_path = self.output / artifact["file"]
        with zipfile.ZipFile(archive_path) as archive:
            contents = [(info, archive.read(info)) for info in archive.infolist()]
        with zipfile.ZipFile(archive_path, "w") as archive:
            for info, content in contents:
                if info.filename == "quicker/README.md":
                    content = b"Replaced content with matching attacker-controlled hashes"
                archive.writestr(info, content)
        artifact.update(sha256=sha256(archive_path), size=archive_path.stat().st_size)
        (self.output / "release-manifest.json").write_bytes(json_bytes(manifest))
        self.resign_checksums()
        self.assert_rejected(self.verify)

    def test_inventory_cannot_silently_omit_a_tracked_plugin(self):
        path = "scripts/release-packages.json"
        inventory = json.loads(self.files[path])
        inventory["packages"] = inventory["packages"][:-1]
        self.write(path, json_bytes(inventory))
        tag = self.tag_changes()
        self.assert_rejected(lambda: self.build(tag))

    def test_inventory_cannot_claim_a_package_missing_from_tag(self):
        for relative in self.files:
            if relative.startswith("plugins/quicker-mcp/"):
                (self.repo / relative).unlink()
        tag = self.tag_changes()
        self.assert_rejected(lambda: self.build(tag))

    def test_required_readme_manifest_shared_file_and_declared_mcp_config_are_checked(self):
        required = (
            "plugins/quicker-cursor/README.md",
            "plugins/quicker-claude/.claude-plugin/plugin.json",
            "plugins/quicker-mcp/skills/write-action/SKILL.md",
            "plugins/quicker/.mcp.json",
        )
        for index, relative in enumerate(required):
            with self.subTest(path=relative):
                (self.repo / relative).unlink()
                tag = self.tag_changes(f"v1.2.{index + 4}")
                self.assert_rejected(lambda: self.build(tag, self.base / f"missing-{index}"))
                self.write(relative, self.files[relative])
                self.commit("Restore required fixture file")

    def test_shared_copy_drift_is_rejected(self):
        self.write("plugins/quicker-cursor/scripts/quicker-mcp.ps1", b"Outdated copied transport\n")
        tag = self.tag_changes()
        self.assert_rejected(lambda: self.build(tag))

    def test_different_package_license_cannot_replace_repository_notice(self):
        self.write("plugins/quicker/LICENSE", b"An unrelated package notice\n")
        tag = self.tag_changes()
        self.assert_rejected(lambda: self.build(tag))

    def test_marketplace_must_point_at_its_inventory_package(self):
        for index, package in enumerate(PACKAGES[:3]):
            with self.subTest(package=package["id"]):
                path = package["marketplace"]
                market = json.loads(self.files[path])
                wrong_source = "./plugins/quicker-mcp"
                if package["id"] == "codex":
                    wrong_source = {"source": "local", "path": wrong_source}
                market["plugins"][0]["source"] = wrong_source
                self.write(path, json_bytes(market))
                tag = self.tag_changes(f"v1.2.{index + 4}")
                self.assert_rejected(lambda: self.build(tag, self.base / f"marketplace-{index}"))
                self.write(path, self.files[path])
                self.commit("Restore fixture marketplace")

    def test_moved_tag_cannot_validate_old_release(self):
        self.build()
        self.write("README.md", b"The tag now points at a different commit\n")
        self.commit("Move fixture release forward")
        self.git("tag", "--force", TAG)
        self.assert_rejected(self.verify)


if __name__ == "__main__":
    unittest.main()
