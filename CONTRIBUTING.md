# Contributing to codagent

Thanks for your interest. This project is small and pragmatic; please
keep contributions in the same spirit.

## Where to focus

The highest-value contributions land in two extension points:

### New `HarnessSource` adapter

Wrap a rule format from elsewhere in the OSS ecosystem so users can
import it into codagent. Examples:

- A new markdown variant (e.g. `.continuerules` parser with section splits)
- A wrapper around a third-party policy library (e.g. `from_constitutional_ai`)
- A team's internal YAML/JSON spec format

To add one:

1. Create `src/codagent/adapters/<name>.py`.
2. Subclass `codagent._abc.HarnessSource`. Implement `load()` returning
   a list of `Contract` instances.
3. Re-export from `src/codagent/adapters/__init__.py` (guard with
   `try/except ImportError` if it depends on an optional package).
4. Add a test under `tests/test_adapters.py` that does not require the
   network — use `tmp_path` for local files or `monkeypatch` to fake
   URL fetches.
5. Update README "Architecture" section with one line for your adapter.

### New `ApplyTarget`

Write the harness into a runtime codagent does not yet support.
Examples: Aider's `CONVENTIONS.md` + `.aider.conf.yml`, Windsurf's
`.windsurfrules`, JetBrains AI Assistant config, etc.

To add one:

1. Create `src/codagent/targets/<name>.py`.
2. Subclass `_FileApplyTarget` (for file-writing targets) or
   `ApplyTarget` directly (for in-memory targets like `wrap_openai`).
3. Set `relative_path` and optionally `file_header` on a file target.
4. Re-export from `src/codagent/targets/__init__.py`.
5. Add a `tmp_path` test under `tests/test_targets.py`.
6. Add to `_TARGET_REGISTRY` in `src/codagent/cli.py` if it should be
   reachable from the CLI.

## Style

- Keep new dependencies optional. Anything heavier than the standard
  library belongs behind an extras group in `pyproject.toml`.
- Prefer plain functions and small dataclasses over framework-style
  abstractions.
- Tests live next to the file they cover (`test_adapters.py`,
  `test_targets.py`). Use `pytest` only — no fixture magic.
- Keep public API small: anything in `__all__` of a module is a
  promise.

## Running the test suite

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
pytest
```

The full suite must pass before opening a PR.

## Commit / PR conventions

- Commit messages in English, imperative mood. Keep the subject under
  72 characters; explain "why" in the body if non-obvious.
- One topic per PR. Bundling unrelated changes makes review harder.
- If your PR adds a new adapter or target, the README "Architecture"
  block should be updated in the same PR.

## Reporting bugs

Open an issue at https://github.com/rlaope/codagent/issues with:

- Your Python version and OS
- Minimal reproduction (10-30 lines is ideal)
- What you expected vs. what happened

## License

By contributing, you agree your changes are released under the project's
MIT license.
