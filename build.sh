#!/usr/bin/env bash
# Build script for Render.com deployment
# Sets writable directories for Rust/Cargo build tools

set -e

# Set CARGO_HOME and RUSTUP_HOME to writable directories in the project
export CARGO_HOME="${PWD}/.cargo"
export RUSTUP_HOME="${PWD}/.rustup"

# Create directories if they don't exist
mkdir -p "${CARGO_HOME}"
mkdir -p "${RUSTUP_HOME}"

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

