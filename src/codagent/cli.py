"""codagent CLI entry point.

Usage:
    codagent install --from <source> [--from <source> ...] \\
                     --to <target> [--to <target> ...] \\
                     [--project DIR] [--mode replace|append]

Source forms (any markdown rule file):
    https://...
    ./CLAUDE.md
    rlaope/quoted-andrej-karpathy           (resolves to main/CLAUDE.md)
    rlaope/quoted-andrej-karpathy:AGENTS.md (specific path)

Target names:
    claude-code   → CLAUDE.md
    cursor        → .cursor/rules/codagent.mdc
    copilot       → .github/copilot-instructions.md
    agents-md     → AGENTS.md
"""

from __future__ import annotations

import argparse
import sys

from codagent._harness import Harness
from codagent.adapters.markdown import from_markdown
from codagent.targets.agents_md import apply_to_agents_md
from codagent.targets.claude_code import apply_to_claude_code
from codagent.targets.copilot import apply_to_copilot
from codagent.targets.cursor import apply_to_cursor


_TARGET_REGISTRY = {
    "claude-code": apply_to_claude_code,
    "cursor": apply_to_cursor,
    "copilot": apply_to_copilot,
    "agents-md": apply_to_agents_md,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codagent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    install = sub.add_parser("install", help="install harness sources to targets")
    install.add_argument(
        "--from", dest="sources", action="append", required=True,
        metavar="SOURCE",
        help="markdown source: URL, path, or 'owner/repo[:path]' (repeatable)",
    )
    install.add_argument(
        "--to", dest="targets", action="append", required=True,
        metavar="TARGET",
        choices=list(_TARGET_REGISTRY.keys()),
        help=f"target: one of {', '.join(_TARGET_REGISTRY)} (repeatable)",
    )
    install.add_argument("--project", default=".", help="project root (default: cwd)")
    install.add_argument("--mode", default="replace", choices=("replace", "append"))

    args = parser.parse_args(argv)

    if args.cmd == "install":
        return _do_install(args)
    return 2


def _do_install(args) -> int:
    sources = [from_markdown(s) for s in args.sources]
    harness = Harness.compose(*sources)

    print(f"codagent install — composed {len(harness.contracts)} contract(s)")
    print(f"  project: {args.project}")
    print(f"  mode:    {args.mode}")
    print(f"  sources: {len(sources)}")
    for s in sources:
        print(f"    - {s.source}")
    print(f"  targets: {len(args.targets)}")

    for target_name in args.targets:
        cls = _TARGET_REGISTRY[target_name]
        target = cls(project_root=args.project, mode=args.mode)
        harness.apply(target)
        print(f"    ✓ {target_name} → {target._full_path()}")

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
