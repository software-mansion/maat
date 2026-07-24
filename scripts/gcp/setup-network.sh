#!/usr/bin/env bash
# One-time setup of the isolated network experiment VMs run in.
#
# Experiment VMs execute arbitrary code from the Cairo ecosystem -- every
# package Ma'at builds is third-party, and `scarb build` runs build scripts and
# procedural macros. They must not be able to reach anything else in the
# project.
#
# The isolation has three parts:
#
#   1. A dedicated custom-mode VPC. VPCs do not route to each other unless
#      explicitly peered, so nothing here can reach the default network (or any
#      other) over internal IPs. Do not peer this network, and do not attach a
#      Cloud Router, VPN, or Interconnect to it.
#   2. An egress deny for all private address space, which stops VMs reaching
#      internal IPs anywhere -- including each other -- even if someone later
#      peers this network by mistake.
#   3. Ingress from the IAP range only, so nothing can connect in.
#
# Combined with `--no-service-account --no-scopes` on the instance (see the
# experiment workflow), a VM has no credentials for the GCP API either.
#
# Read the "Network isolation" section of docs/gcp-runners.md before changing
# any of this -- in particular for what this does NOT cover.
#
# Usage: ZONE=europe-west4-a scripts/gcp/setup-network.sh

set -euo pipefail

: "${ZONE:?set ZONE, e.g. ZONE=europe-west4-a}"

REGION="${ZONE%-*}"
NETWORK="${NETWORK:-maat-net}"
SUBNET="${SUBNET:-maat-subnet}"
# Any range works: this VPC is never peered, so it cannot collide with anything.
SUBNET_RANGE="${SUBNET_RANGE:-10.200.0.0/24}"
TAG="maat-runner"

exists() {
  # shellcheck disable=SC2048,SC2086
  gcloud compute $1 describe "$2" ${3:-} --format='value(name)' >/dev/null 2>&1
}

if exists networks "$NETWORK"; then
  echo "network $NETWORK already exists, skipping"
else
  gcloud compute networks create "$NETWORK" \
    --subnet-mode=custom \
    --description="Isolated network for Ma'at experiment VMs. Do not peer."
fi

if exists "networks subnets" "$SUBNET" "--region=$REGION"; then
  echo "subnet $SUBNET already exists, skipping"
else
  # Private Google Access stays off: VMs have no service account and no business
  # talking to the GCP API.
  gcloud compute networks subnets create "$SUBNET" \
    --network="$NETWORK" \
    --region="$REGION" \
    --range="$SUBNET_RANGE" \
    --no-enable-private-ip-google-access
fi

# --- Ingress ---------------------------------------------------------------

# IAP is the only way in. The range is IAP's fixed forwarding range, not a
# public one -- traffic from it is already authenticated by IAP.
if ! exists firewall-rules "${NETWORK}-allow-iap-ssh"; then
  gcloud compute firewall-rules create "${NETWORK}-allow-iap-ssh" \
    --network="$NETWORK" \
    --direction=INGRESS \
    --priority=1000 \
    --action=ALLOW \
    --rules=tcp:22 \
    --source-ranges=35.235.240.0/20 \
    --target-tags="$TAG" \
    --description="SSH from IAP only"
fi

# Redundant with the implied deny-ingress rule, but makes the intent explicit
# and survives someone adding a broad allow rule at default priority.
if ! exists firewall-rules "${NETWORK}-deny-ingress"; then
  gcloud compute firewall-rules create "${NETWORK}-deny-ingress" \
    --network="$NETWORK" \
    --direction=INGRESS \
    --priority=65000 \
    --action=DENY \
    --rules=all \
    --source-ranges=0.0.0.0/0 \
    --description="Nothing reaches experiment VMs except via IAP"
fi

# --- Egress ----------------------------------------------------------------

# Blocks every private range, which covers: other VPCs (were this network ever
# peered), on-prem over VPN/Interconnect, and the experiment VMs reaching each
# other -- partitions must stay independent. Deliberately includes this subnet's
# own range.
#
# Egress to the metadata server (169.254.169.254) is always permitted by GCP
# regardless of firewall rules, so OS Login and the startup script still work.
if ! exists firewall-rules "${NETWORK}-deny-egress-private"; then
  gcloud compute firewall-rules create "${NETWORK}-deny-egress-private" \
    --network="$NETWORK" \
    --direction=EGRESS \
    --priority=1000 \
    --action=DENY \
    --rules=all \
    --destination-ranges=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16 \
    --description="Experiment VMs cannot reach any internal address"
fi

# Public internet stays open: the run pulls the sandbox image from ghcr.io and
# dependencies from crates.io and the Scarb registry. Lower priority than the
# deny above, so the deny wins for private ranges.
if ! exists firewall-rules "${NETWORK}-allow-egress-internet"; then
  gcloud compute firewall-rules create "${NETWORK}-allow-egress-internet" \
    --network="$NETWORK" \
    --direction=EGRESS \
    --priority=2000 \
    --action=ALLOW \
    --rules=all \
    --destination-ranges=0.0.0.0/0 \
    --description="Public internet egress for image and dependency pulls"
fi

echo
echo "Done. Set these repository variables:"
echo "  GCP_NETWORK = $NETWORK"
echo "  GCP_SUBNET  = $SUBNET"
echo
echo "Rules on $NETWORK:"
gcloud compute firewall-rules list --filter="network=$NETWORK" \
  --format="table(name, direction, priority, allowed[], denied[], sourceRanges.list():label=SRC, destinationRanges.list():label=DST)"
