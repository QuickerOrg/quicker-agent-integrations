"""Build and verify every release asset from one immutable Git tag snapshot."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = 'scripts/release-packages.json'
NUMBER = r'(?:0|[1-9][0-9]*)'
PRERELEASE_ID = r'(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)'
VERSION = NUMBER + r'\.' + NUMBER + r'\.' + NUMBER + r'(?:-' + PRERELEASE_ID + r'(?:\.' + PRERELEASE_ID + r')*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?'


def git(repo, *args, data=None):
    result = subprocess.run(['git', '-C', str(repo), *args], input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip())
    return result.stdout


def relative_path(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError(f'Invalid relative path: {value!r}')
    parts = value.split('/')
    if any(part in ('', '.', '..') for part in parts) or PurePosixPath(value).is_absolute():
        raise ValueError(f'Invalid relative path: {value!r}')
    return value


def snapshot(repo, tag):
    match = re.fullmatch('v?(' + VERSION + ')', tag)
    if not match:
        raise ValueError('Use a SemVer tag, for example v0.2.2.')
    commit = git(repo, 'rev-parse', '--verify', 'refs/tags/' + tag + '^{commit}').decode().strip()
    entries = []
    for entry in git(repo, 'ls-tree', '-r', '-z', commit).split(b'\0'):
        if not entry:
            continue
        header, raw_path = entry.split(b'\t', 1)
        mode, kind, oid = header.decode('ascii').split()
        path = relative_path(raw_path.decode('utf-8'))
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError(f'Release requires ordinary tracked files: {path}')
        if path.split('/')[0] in ('.temp', 'dist', '.quicker', '.venv', '__pycache__'):
            raise ValueError(f'Temporary or personal data is tracked in the tag: {path}')
        entries.append((path, mode, oid))
    oids = list(dict.fromkeys(oid for _, _, oid in entries))
    batch = io.BytesIO(git(repo, 'cat-file', '--batch', data=('\n'.join(oids) + '\n').encode()))
    blobs = {}
    for expected in oids:
        oid, kind, length = batch.readline().decode('ascii').strip().split()
        contents = batch.read(int(length))
        if oid != expected or kind != 'blob' or len(contents) != int(length) or batch.read(1) != b'\n':
            raise ValueError('Invalid Git object stream.')
        blobs[oid] = contents
    files = {path: (blobs[oid], int(mode, 8)) for path, mode, oid in entries}
    return commit, match.group(1), files


def read_json(files, path):
    if path not in files:
        raise ValueError(f'Missing tracked file: {path}')
    try:
        return json.loads(files[path][0])
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError(f'Invalid JSON: {path}') from error


def release_plan(repo, tag):
    commit, version, files = snapshot(repo, tag)
    inventory = read_json(files, INVENTORY)
    if not isinstance(inventory, dict) or inventory.get('schemaVersion') != 1 or not isinstance(inventory.get('packages'), list) or not inventory['packages']:
        raise ValueError('Release inventory must contain schemaVersion 1 and all packages.')
    if 'LICENSE' not in files:
        raise ValueError('The tag must contain the repository LICENSE.')
    if not isinstance(inventory.get('sharedFiles'), list) or not inventory['sharedFiles']:
        raise ValueError('Release inventory must declare the required shared files.')
    shared = [relative_path(path) for path in inventory['sharedFiles']]
    paths, ids = set(), set()
    full_root = f'quicker-agent-integrations-{version}/'
    plan = [({'file': f'quicker-agent-integrations-{version}.zip', 'kind': 'source', 'root': full_root}, files)]
    for package in inventory['packages']:
        package_id, path = package['id'], relative_path(package['path'])
        if not re.fullmatch('[a-z][a-z0-9-]*', package_id) or package_id in ids:
            raise ValueError(f'Invalid or duplicate package id: {package_id}')
        if not re.fullmatch('plugins/[a-z0-9-]+', path) or path in paths:
            raise ValueError(f'Invalid or duplicate package path: {path}')
        ids.add(package_id)
        paths.add(path)
        manifest_path = relative_path(package['manifest'])
        manifest = read_json(files, path + '/' + manifest_path)
        package_version = manifest.get('version')
        if not isinstance(package_version, str) or not re.fullmatch(VERSION, package_version):
            raise ValueError(f'Missing or invalid package version: {path}')
        if not isinstance(manifest.get('name'), str) or not manifest['name']:
            raise ValueError(f'Missing package name: {path}')
        required = ['README.md', manifest_path, *shared]
        if package.get('mcpConfig'):
            required.append(relative_path(package['mcpConfig']))
        for relative in required:
            if path + '/' + relative not in files:
                raise ValueError(f'Missing required package file: {path}/{relative}')
        for relative in shared:
            if 'shared/' + relative not in files or files[path + '/' + relative][0] != files['shared/' + relative][0]:
                raise ValueError(f'Shared source drift: {path}/{relative}')
        if package.get('marketplace'):
            marketplace = read_json(files, relative_path(package['marketplace']))
            sources = []
            for entry in marketplace.get('plugins', []):
                source = entry.get('source')
                source = source.get('path') if isinstance(source, dict) else source
                sources.append((entry.get('name'), source))
            if (manifest['name'], './' + path) not in sources:
                raise ValueError(f'Marketplace does not expose the package: {path}')
        package_files = {name[len(path) + 1:]: value for name, value in files.items() if name.startswith(path + '/')}
        if 'LICENSE' in package_files and package_files['LICENSE'][0] != files['LICENSE'][0]:
            raise ValueError(f'Package LICENSE differs from the repository notice: {path}')
        package_files['LICENSE'] = files['LICENSE']
        plan.append(({
            'file': f'quicker-{package_id}-{version}.zip', 'kind': 'plugin', 'root': 'quicker/',
            'id': package_id, 'path': path, 'manifest': manifest_path,
            'packageName': manifest['name'], 'packageVersion': package_version,
        }, package_files))
    tracked_packages = {'/'.join(path.split('/')[:2]) for path in files if path.startswith('plugins/') and path.count('/') >= 2}
    if paths != tracked_packages:
        raise ValueError(f'Inventory must cover all tracked packages; missing={sorted(tracked_packages - paths)}, absent={sorted(paths - tracked_packages)}')
    return commit, version, plan


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def asset_metadata(descriptor, path):
    contents = path.read_bytes()
    return {**descriptor, 'sha256': hashlib.sha256(contents).hexdigest(), 'size': len(contents)}


def expected_manifest(tag, commit, version, artifacts):
    return {'schemaVersion': 1, 'tag': tag, 'sourceCommit': commit, 'releaseVersion': version, 'artifacts': artifacts}


def checksums(output, names):
    return ''.join(hashlib.sha256((output / name).read_bytes()).hexdigest() + '  ' + name + '\n' for name in sorted(names))


def build_release(repo, tag, output):
    output = Path(output)
    commit, version, plan = release_plan(repo, tag)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be empty; existing release assets will not be overwritten.')
    output.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for descriptor, files in plan:
        target = output / descriptor['file']
        with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            for path, (contents, mode) in sorted(files.items()):
                info = zipfile.ZipInfo(descriptor['root'] + path, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = mode << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, contents)
        artifacts.append(asset_metadata(descriptor, target))
    manifest = expected_manifest(tag, commit, version, artifacts)
    (output / 'release-manifest.json').write_bytes(json_bytes(manifest))
    names = [artifact['file'] for artifact in artifacts] + ['release-manifest.json']
    (output / 'SHA256SUMS.txt').write_bytes(checksums(output, names).encode('utf-8'))
    return verify_release(repo, tag, output)


def verify_release(repo, tag, output):
    output = Path(output)
    commit, version, plan = release_plan(repo, tag)
    names = {descriptor['file'] for descriptor, _ in plan}
    expected = names | {'release-manifest.json', 'SHA256SUMS.txt'}
    if not output.is_dir() or {path.name for path in output.iterdir()} != expected:
        raise ValueError('Release assets are missing or unexpected; every package ZIP, source ZIP, manifest and checksums are required.')
    artifacts = []
    for descriptor, files in plan:
        target = output / descriptor['file']
        try:
            with zipfile.ZipFile(target) as archive:
                expected_names = {descriptor['root'] + path for path in files}
                if len(archive.namelist()) != len(expected_names) or set(archive.namelist()) != expected_names:
                    raise ValueError(f'ZIP entries do not match the tag: {target.name}')
                for path, (contents, mode) in files.items():
                    name = descriptor['root'] + path
                    if archive.read(name) != contents or archive.getinfo(name).external_attr >> 16 != mode:
                        raise ValueError(f'ZIP content differs from the tag: {target.name}: {path}')
        except (zipfile.BadZipFile, OSError) as error:
            raise ValueError(f'Invalid ZIP: {target.name}') from error
        artifacts.append(asset_metadata(descriptor, target))
    manifest = expected_manifest(tag, commit, version, artifacts)
    if (output / 'release-manifest.json').read_bytes() != json_bytes(manifest):
        raise ValueError('release-manifest.json does not match the tag and assets.')
    if (output / 'SHA256SUMS.txt').read_bytes() != checksums(output, names | {'release-manifest.json'}).encode('utf-8'):
        raise ValueError('SHA256SUMS.txt does not cover the exact release assets.')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True, help='Existing local SemVer tag, for example v0.2.2')
    parser.add_argument('--output-dir', type=Path, help='Defaults to dist/<tag>')
    parser.add_argument('--verify', action='store_true', help='Verify existing assets without writing')
    args = parser.parse_args()
    output = args.output_dir or ROOT / 'dist' / args.tag
    try:
        manifest = (verify_release if args.verify else build_release)(ROOT, args.tag, output)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Release packaging failed: {error}\n')
    print(f"Verified {len(manifest['artifacts'])} ZIPs for {args.tag} at {manifest['sourceCommit']}")
    for artifact in manifest['artifacts']:
        print(artifact['file'])
    print('release-manifest.json\nSHA256SUMS.txt')


if __name__ == '__main__':
    main()
