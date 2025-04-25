FROM alpine:latest
LABEL maintainer="Software Mansion <contact@swmansion.com>"

ARG ASDF_VERSION=0.16.7
ENV ASDF_VERSION="$ASDF_VERSION"
ENV ASDF_DATA_DIR=/opt/asdf
ENV PATH="$ASDF_DATA_DIR/shims:/root/.local/bin:$PATH"

RUN <<EOF
set -eux
apk add --no-cache bash curl git

mkdir -p /root/.local/bin
export ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/' -e 's/i[3-6]86/386/')
export DL_URL="https://github.com/asdf-vm/asdf/releases/download/v$ASDF_VERSION/asdf-v$ASDF_VERSION-linux-$ARCH.tar.gz"
curl --proto '=https' --tlsv1.2 -sSfL "$DL_URL" | tar -xz --strip-components=0 -C /root/.local/bin asdf
asdf --version

asdf plugin add scarb
asdf plugin add starknet-foundry
EOF

ENTRYPOINT ["/root/.local/bin/asdf"]
