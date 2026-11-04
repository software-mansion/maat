#!/usr/bin/env bash
# Runs a command on the experiment VM over the IAP-tunneled SSH connection.
# Every workflow step that talks to the VM goes through this instead of
# repeating the gcloud invocation, so call sites read as one line.
#
# Retries when OS Login rate-limits key signing (HTTP 429). That happens before
# the connection is made, so the remote command has not run and retrying is safe.
#
# Usage: scripts/gcp/ssh.sh <vm-name> <zone> <remote-command>

set -euo pipefail

vm_name="$1"
zone="$2"
remote_command="$3"

stderr_file="$(mktemp)"
trap 'rm -f "$stderr_file"' EXIT

for attempt in 1 2 3 4 5; do
  rc=0
  gcloud compute ssh "$vm_name" --zone="$zone" --tunnel-through-iap \
    --command="$remote_command" 2>"$stderr_file" || rc=$?
  cat "$stderr_file" >&2
  if [ "$rc" -eq 0 ] || ! grep -q 'RESOURCE_EXHAUSTED' "$stderr_file"; then
    exit "$rc"
  fi
  echo "::warning::OS Login rate limit hit (attempt $attempt), retrying..." >&2
  sleep $((attempt * 15))
done
exit "$rc"
