#!/usr/bin/env bash
# Extracts the uploaded Ma'at source tarball and plan into ~/maat and installs
# dependencies. Uploaded and run once by the "Upload Ma'at sources and plan"
# workflow step, before anything from the repo itself exists on the VM.

set -eux

mkdir -p ~/maat
tar -xzf ~/maat-src.tar.gz -C ~/maat
mv ~/maat-plan.json ~/maat/
cd ~/maat && uv sync
