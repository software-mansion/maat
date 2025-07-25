FROM node:23.11.0 AS nodejs-builder
WORKDIR /nodejs
ADD nodejs /nodejs
RUN npm ci
RUN npm run build


FROM fedora:42
LABEL maintainer="Software Mansion <contact@swmansion.com>"

ARG MAAT_CACHE
ENV MAAT_CACHE="$MAAT_CACHE"
ARG MAAT_WORKBENCH
ENV MAAT_WORKBENCH="$MAAT_WORKBENCH"

ENV RUSTUP_HOME=/opt/rustup
ENV CARGO_HOME=/opt/cargo
ENV SCARB_CACHE="$MAAT_CACHE/scarb"
ENV ASDF_DATA_DIR=/opt/asdf

# Adding /root/.local/bin because universal-sierra-compiler installer is hardcoded to this path.
# And we will reuse it for asdf install just because.
ENV PATH="$ASDF_DATA_DIR/shims:$CARGO_HOME/bin:/root/.local/bin:$PATH"

# Install some build essentials and rustup-init.
RUN dnf install -y gcc-c++ git make ripgrep rustup && dnf clean all

# Preconfigure Git to allow commiting from within the agent.
RUN <<EOF
git config --system init.defaultBranch main
git config --system user.email "contact@swmansion.com"
git config --system user.name "Ma'at"
EOF

# Install Rust, this will use RUSTUP_TOOLCHAIN from environment.
ENV RUST_BACKTRACE=1
ARG RUSTUP_TOOLCHAIN=1.86
ENV RUSTUP_TOOLCHAIN="$RUSTUP_TOOLCHAIN"
RUN rustup-init -y --no-modify-path && cargo --version

# Install UV and Python.
COPY --from=ghcr.io/astral-sh/uv:0.6.13 /uv /uvx /root/.local/bin/
RUN uv python install 3.13

# Install ASDF.
ARG ASDF_VERSION=0.16.7
ENV ASDF_VERSION="$ASDF_VERSION"
RUN <<EOF
set -eux
mkdir -p /root/.local/bin
export ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/' -e 's/i[3-6]86/386/')
export DL_URL="https://github.com/asdf-vm/asdf/releases/download/v$ASDF_VERSION/asdf-v$ASDF_VERSION-linux-$ARCH.tar.gz"
curl --proto '=https' --tlsv1.2 -sSfL "$DL_URL" | tar -xz --strip-components=0 -C /root/.local/bin asdf
asdf --version

asdf plugin add scarb
asdf plugin add starknet-foundry
EOF

# Install Node.js.
ARG ASDF_NODEJS_VERSION=23.11.0
ENV ASDF_NODEJS_VERSION="$ASDF_NODEJS_VERSION"
RUN <<EOF
set -eux
asdf plugin add nodejs
asdf install nodejs
node --version
npm --version
EOF

# Install Scarb.
ARG ASDF_SCARB_VERSION
ENV ASDF_SCARB_VERSION="$ASDF_SCARB_VERSION"
LABEL maat.scarb.version="$ASDF_SCARB_VERSION"
RUN <<EOF
set -eux
if [ -z "$ASDF_SCARB_VERSION" ]; then
  echo "ERROR: ASDF_SCARB_VERSION must be specified"
  exit 1
fi
asdf install scarb
scarb --version
EOF

# Install Starknet Foundry.
# We try to normalize name of the environment variable controlling it because, well, LOL.
ARG ASDF_STARKNET_FOUNDRY_VERSION
ENV ASDF_STARKNET_FOUNDRY_VERSION="$ASDF_STARKNET_FOUNDRY_VERSION"
ENV ASDF_STARKNET-FOUNDRY_VERSION="$ASDF_STARKNET_FOUNDRY_VERSION"
LABEL maat.foundry.version="$ASDF_STARKNET_FOUNDRY_VERSION"
RUN <<EOF
set -eux
if [ -z "${ASDF_STARKNET-FOUNDRY_VERSION}" ]; then
  echo "ERROR: ASDF_STARKNET_FOUNDRY_VERSION must be specified"
  exit 1
fi
asdf install starknet-foundry
snforge --version
sncast --version
EOF

# Add all agent binaries to /root/.local/bin.
ADD --chmod=0755 bin/* /root/.local/bin
COPY --from=nodejs-builder /nodejs/out/maat-test-ls.js /root/.local/bin/maat-test-ls
