"""Materialize shared sources into self-contained client packages."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("quicker", "quicker-cursor", "quicker-claude", "quicker-mcp")
FILES = ("scripts/quicker-mcp.ps1", "skills/write-action/SKILL.md", "skills/write-action/references/connection.md")


def sync(check=False):
    stale = []
    for package in PACKAGES:
        for relative in FILES:
            source = (ROOT / "shared" / relative).read_bytes()
            target = ROOT / "plugins" / package / relative
            if not target.exists() or target.read_bytes() != source:
                stale.append(str(target.relative_to(ROOT)))
                if not check:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source)
    if check and stale:
        raise SystemExit("Run python scripts/sync-packages.py: " + ", ".join(stale))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    sync(parser.parse_args().check)
