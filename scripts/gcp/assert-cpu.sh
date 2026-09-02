#!/usr/bin/env bash
# Runs on the experiment VM before run-plan. Prints the CPU the VM actually
# landed on, and fails the run if it is not the one we expect.
#
# Timings are only comparable across experiments if the silicon underneath is
# the same. Machine families like C4 are backed by a single CPU platform, so
# this should never fire — which is exactly why it is worth checking. If it does
# fire, every timing in the report is suspect and we would rather lose the run
# than publish a phantom regression.
#
# Set EXPECTED_CPU_MODEL to enforce a model. Leave it unset to observe only,
# which is what you want on the first run: read the reported value out of the
# logs, then pin it.

set -euo pipefail

actual_model="$(awk -F': ' '/^model name/ { print $2; exit }' /proc/cpuinfo)"
threads_per_core="$(lscpu | awk -F': +' '/^Thread\(s\) per core/ { print $2; exit }')"

echo "cpu model:         ${actual_model:-<unknown>}"
echo "threads per core:  ${threads_per_core}"
echo "cores available:   $(nproc)"

failed=0

# Not every architecture reports `model name` -- arm64 does not, for one. On the
# x86 families we target it is always present, so an empty value means we are
# somewhere unexpected and cannot tell what CPU this is. Refuse rather than pass
# a check we did not actually perform.
if [[ -z "${actual_model}" ]]; then
  echo "::error::Could not read a CPU model from /proc/cpuinfo." \
    "Expected an x86 machine family such as C4."
  exit 1
fi

if [[ -n "${EXPECTED_CPU_MODEL:-}" ]]; then
  if [[ "${actual_model}" != "${EXPECTED_CPU_MODEL}" ]]; then
    echo "::error::CPU mismatch: expected '${EXPECTED_CPU_MODEL}', got '${actual_model}'"
    failed=1
  fi
else
  echo "::warning::EXPECTED_CPU_MODEL is unset, so the CPU is not pinned." \
    "Set it to the model above to make timings comparable across runs."
fi

# Hyperthread siblings contend for execution ports, which shows up as
# run-to-run timing noise. The VM should have been created with
# --threads-per-core=1.
if [[ "${threads_per_core}" != "1" ]]; then
  echo "::error::SMT is enabled (${threads_per_core} threads/core)." \
    "Create the VM with --threads-per-core=1."
  failed=1
fi

exit "${failed}"
