#!/usr/bin/env bash
# VM startup script. Runs as root on first boot, before any experiment work.
# Installs Docker and uv, and puts Docker's storage on local SSD when the
# machine shape provides one. Writes /var/lib/maat-ready on success; the
# workflow blocks on that file before doing anything else.

set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

# Put Docker's data root on local SSD when the shape has one (any *-lssd machine
# type). Step timings include container start and cache population, so disk
# latency variance lands directly in the numbers we compare across runs.
setup_local_ssd() {
  local devices=()
  # shellcheck disable=SC2207
  devices=($(ls /dev/disk/by-id/google-local-nvme-ssd-* 2>/dev/null || true))

  if [[ ${#devices[@]} -eq 0 ]]; then
    echo "no local SSD present; Docker stays on the boot disk"
    return 0
  fi

  local target
  if [[ ${#devices[@]} -eq 1 ]]; then
    target="${devices[0]}"
  else
    # GCP hands out multiple smaller NVMe devices on larger shapes. Stripe them,
    # otherwise we only ever use a fraction of the available throughput.
    mdadm --create /dev/md0 --level=0 --raid-devices="${#devices[@]}" "${devices[@]}"
    target=/dev/md0
  fi

  mkfs.ext4 -F -m 0 -E lazy_itable_init=0,lazy_journal_init=0,discard "$target"
  mkdir -p /var/lib/docker
  mount -o discard,defaults,nobarrier "$target" /var/lib/docker
}

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg mdadm

setup_local_ssd

# Docker must be installed after /var/lib/docker is mounted, so the daemon's
# storage lands on the local SSD rather than being written to the boot disk and
# then shadowed by the mount.
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  >/etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y --no-install-recommends \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin

systemctl enable --now docker

# uv, installed system-wide so it is on PATH for the SSH user. It provisions its
# own Python, so the VM image's Python version does not matter.
export UV_INSTALL_DIR=/usr/local/bin
export UV_UNMANAGED_INSTALL=1
curl -LsSf https://astral.sh/uv/install.sh | sh

touch /var/lib/maat-ready
echo "maat VM ready"
