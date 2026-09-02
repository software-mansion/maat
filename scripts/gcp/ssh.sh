#!/usr/bin/env bash
# Runs a command on the experiment VM over the IAP-tunneled SSH connection.
# Every workflow step that talks to the VM goes through this instead of
# repeating the gcloud invocation, so call sites read as one line.
#
# Usage: scripts/gcp/ssh.sh <vm-name> <zone> <remote-command>

set -euo pipefail

vm_name="$1"
zone="$2"
remote_command="$3"

gcloud compute ssh "$vm_name" --zone="$zone" --tunnel-through-iap --command="$remote_command"
