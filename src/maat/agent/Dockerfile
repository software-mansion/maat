FROM fedora:42
LABEL maintainer="Software Mansion <contact@swmansion.com>"

ENV RUSTUP_HOME=/opt/rustup
ENV CARGO_HOME=/opt/cargo
ENV ASDF_DATA_DIR=/opt/asdf
ENV PATH="$ASDF_DATA_DIR/shims:$CARGO_HOME/bin:$PATH"

# Install some build essentials and rustup-init.
RUN dnf install -y gcc-c++ git make rustup && dnf clean all

# Install Rust, this will use RUSTUP_TOOLCHAIN from environment.
ENV RUST_BACKTRACE=1
ARG RUSTUP_TOOLCHAIN=1.85
RUN rustup-init -y --no-modify-path && cargo --version

# Install ASDF.
ARG ASDF_VERSION=0.16.5
RUN <<EOF sh
export ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/' -e 's/i[3-6]86/386/')
export DL_URL="https://github.com/asdf-vm/asdf/releases/download/v$ASDF_VERSION/asdf-v$ASDF_VERSION-linux-\$ARCH.tar.gz"
curl -L "\$DL_URL" | tar -xz --strip-components=0 -C /usr/local/bin asdf
asdf --version
EOF

# Install Scarb.
ARG ASDF_SCARB_VERSION
RUN <<EOF sh
if [ -z "$ASDF_SCARB_VERSION" ]; then
  echo "ERROR: ASDF_SCARB_VERSION must be specified"
  exit 1
fi
asdf plugin add scarb
asdf install scarb
scarb --version
EOF

# Install Starknet Foundry.
# We try to normalize name of the environment variable controlling it because, well, LOL.
ARG ASDF_STARKNET_FOUNDRY_VERSION
ENV ASDF_STARKNET-FOUNDRY_VERSION="$ASDF_STARKNET_FOUNDRY_VERSION"
RUN <<EOF sh
if [ -z "${ASDF_STARKNET-FOUNDRY_VERSION}" ]; then
  echo "ERROR: ASDF_STARKNET_FOUNDRY_VERSION must be specified"
  exit 1
fi
asdf plugin add starknet-foundry
asdf install starknet-foundry
snforge --version
sncast --version
EOF

# Create sample snforge project and test it. This will compile snforge procmacros if needed and store it in caches.
RUN <<EOF sh
cd /tmp
snforge init just_testing
cd ./just_testing
scarb build
scarb test
cd
rm -rf /tmp/just_testing
EOF

# Add entrypoint script
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh
ENTRYPOINT ["/opt/entrypoint.sh"]
