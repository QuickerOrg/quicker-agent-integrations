# Repository guide

This repository maintains integrations that let external agents use Quicker. Start with README.md and docs/接入约定.md. For a new platform, read docs/新增平台.md and its current official plugin documentation.

## Boundaries

- Keep installable packages under plugins/ and make each directory self-contained. The Codex marketplace currently exposes plugins/quicker; DSH uses plugins/quicker-dsh as a cordis bundle. Declare each future platform's source path in its own catalog.
- Quicker owns action execution, step knowledge, permissions, approvals and Catalog state. Discover runtime knowledge instead of copying a static module catalog here.
- Do not add Quicker product source, private repository dependencies, personal configuration, client grants, credentials or machine-specific paths.
- Add shared source when a second real consumer needs it. Copy required runtime files into each distributable package; do not use symlinks or paths outside the installed package.
- Do not claim support for a platform that only has planning documentation. Keep docs/兼容性.md accurate.

## Workflow

- Check git status before editing and preserve unrelated changes. Use one writer for Git mutations.
- User-facing communication and documentation are Chinese. Code and Agent-facing instructions may use English.
- Write temporary output under .temp/ and distribution archives under dist/; both are ignored.
- Every release must ship every platform's standalone ZIP, the complete source/install ZIP, release-manifest.json and SHA256SUMS.txt, even when only one plugin changed. Follow docs/发布.md and scripts/release-packages.json; build and verify from the tag with scripts/package-release.py. Verify the downloaded release assets as well. Artifact filenames use the release version; plugin manifest versions remain independent.
- For transport changes, run `python -m unittest discover -s tests -v` on Windows. The tests use isolated fixtures; never point them at the user's real settings.
- Validate changed plugin manifests with that platform's current tooling. For Codex, the installed plugin-creator validator is useful locally; the package must not depend on it at runtime.
- For installation changes, verify package discovery and a local install separately from live Quicker acceptance. A mock transport test does not establish real action authoring.
- Commit/push, public publication, license changes and marketplace submission require user authorization. Publishing to GitHub does not imply permission to submit to platform marketplaces.

## Runtime invariants

- Credential discovery is read-only. Never print or copy the MCP token into artifacts or logs.
- Keep loopback-only transport, redirect/proxy refusal, complete tool-result preservation and no automatic replay of writes.
- Propagate Quicker errors and approvals. A transport timeout can leave a write outcome unknown; inspect state before retrying.
- Keep explicit action slots in calls. Multiple conversations may share a client process and a Quicker authoring session.
