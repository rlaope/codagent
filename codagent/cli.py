"""codagent CLI entry point.

Subcommands:
    install     install harness sources to targets (CLAUDE.md, cursor, copilot, agents-md)
    serve       run the agent-native HTTP server (requires 'server' extra)

Examples:
    codagent install --from ./CLAUDE.md --to claude-code
    codagent serve myagent:run --port 8000

For ``serve`` the target is ``module:attribute`` where attribute is an
async-generator callable ``async def fn(body) -> yields str``.
"""

from __future__ import annotations

import argparse
import sys

from codagent.harness._harness import Harness
from codagent.harness.adapters.markdown import from_markdown
from codagent.harness.targets.agents_md import apply_to_agents_md
from codagent.harness.targets.claude_code import apply_to_claude_code
from codagent.harness.targets.copilot import apply_to_copilot
from codagent.harness.targets.cursor import apply_to_cursor


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

    serve = sub.add_parser("serve", help="run the agent-native HTTP server")
    serve.add_argument(
        "target",
        metavar="MODULE:ATTR",
        help="async-generator callable to serve, e.g. 'myagent:run'",
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)

    if args.cmd == "install":
        return _do_install(args)
    if args.cmd == "serve":
        return _do_serve(args)
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


def _do_serve(args) -> int:
    import importlib

    try:
        import uvicorn
    except ImportError:
        print(
            "codagent serve requires the 'server' extra. "
            "Install with: pip install 'codagent[server]'",
            file=sys.stderr,
        )
        return 1

    if ":" not in args.target:
        print("target must be MODULE:ATTR (e.g. myagent:run)", file=sys.stderr)
        return 2
    module_name, attr = args.target.split(":", 1)
    module = importlib.import_module(module_name)
    llm_call = getattr(module, attr)

    from codagent.server import create_app

    app = create_app(llm_call=llm_call)
    print(f"codagent serve — {args.target} on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
