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
  # Stream stderr live (keeping its order relative to stdout) while also
  # capturing it, so the rate-limit check below can inspect it. pipefail makes
  # rc reflect gcloud's exit code rather than tee's.
  { gcloud compute ssh "$vm_name" --zone="$zone" --tunnel-through-iap \
      --command="$remote_command" 2>&1 1>&3 3>&- | tee "$stderr_file" >&2; } 3>&1 || rc=$?
  if [ "$rc" -eq 0 ] || ! grep -q 'RESOURCE_EXHAUSTED' "$stderr_file"; then
    exit "$rc"
  fi
  echo "::warning::OS Login rate limit hit (attempt $attempt), retrying..." >&2
  sleep $((attempt * 15))
done
exit "$rc"
