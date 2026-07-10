#!/usr/bin/env bash
set -euo pipefail

# Gitea Actions must be enabled per-repo (Settings > Basic Settings > "Enable
# Repository Actions") and a runner registration token generated before the
# runner container in docker-compose.yml can connect.
#
# Steps:
#   1. docker compose up -d gitea
#   2. Open http://localhost:3000, finish first-run setup, create admin account
#   3. Site Administration > Actions > Runners > "Create new runner"
#   4. Copy the registration token, paste into .env as RUNNER_TOKEN
#   5. Run this script (or just: docker compose up -d runner)

if [ -z "${RUNNER_TOKEN:-}" ]; then
  echo "RUNNER_TOKEN is not set. Set it in .env, then re-run:"
  echo "  export \$(grep RUNNER_TOKEN .env) && ./scripts/register_runner.sh"
  exit 1
fi

docker compose up -d runner
echo "Runner container started. Check Site Administration > Actions > Runners in Gitea to confirm it registered."
