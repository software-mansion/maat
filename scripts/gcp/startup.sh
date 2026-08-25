#!/usr/bin/env bash
# VM startup script. Runs as root on first boot, before any experiment work.
# Installs Docker and uv. Writes /var/lib/maat-ready on success; the workflow
# blocks on that file before doing anything else.

set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg

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
#
# Unlike the Docker install above, there is no GPG/checksum verification here --
# astral.sh does not publish a pinned checksum for install.sh itself. Downloading
# it separately from executing it at least means a tampered script is not
# invisible: its hash lands in this VM's serial console output (captured by
# `gcloud compute instances get-serial-port-output`) for after-the-fact audit,
# even though nothing here blocks on it matching a known-good value.
export UV_INSTALL_DIR=/usr/local/bin
export UV_UNMANAGED_INSTALL=1
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/uv-install.sh
echo "uv installer sha256: $(sha256sum /tmp/uv-install.sh | cut -d' ' -f1)"
sh /tmp/uv-install.sh
rm -f /tmp/uv-install.sh

touch /var/lib/maat-ready
echo "maat VM ready"
