#!/usr/bin/env bash
# Launches `maat run-plan` detached from the calling SSH session, so a dropped
# IAP tunnel kills only that connection, not the multi-hour run itself. Writes
# run-plan.log and run-plan.exit_code in ~/maat; the workflow polls for the
# latter to know when the run is done.
#
# Usage: scripts/gcp/launch-run-plan.sh <partition> <maat-commit>

set -euo pipefail

partition="$1"
maat_commit="$2"

cd "$(dirname "$0")/../.."
rm -f run-plan.exit_code run-plan.log

nohup bash -c "
  MAAT_COMMIT='$maat_commit' ./maat run-plan --partition '$partition' --jobs 1 maat-plan.json
  echo \$? > run-plan.exit_code
" >run-plan.log 2>&1 </dev/null &
disown
