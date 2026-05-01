#!/usr/bin/env bash
# Demonstrate the codagent CLI.
#
# Pulls two markdown rule sets (forrestchang's andrej-karpathy-skills and
# our quoted-andrej-karpathy) and applies them to all four file targets
# in a temporary project directory.

set -euo pipefail

TMP=$(mktemp -d)
echo "demo project root: $TMP"
echo

codagent install \
  --from forrestchang/andrej-karpathy-skills \
  --from rlaope/quoted-andrej-karpathy \
  --to claude-code \
  --to cursor \
  --to copilot \
  --to agents-md \
  --project "$TMP"

echo
echo "=== files written ==="
find "$TMP" -type f | sort
