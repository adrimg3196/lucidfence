# Installation — LucidFence

This guide covers how to install LucidFence on your system.

## Requirements

- Python 3.11+
- Access to at least one UEM platform (Applivery, Intune, Jamf, Fleet)
- Terminal access on macOS, Linux, or Windows

## Quick Install

```bash
# Clone the repository
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Verify installation
lucidfence --version
```

## Docker Install

```bash
docker compose up -d
```

## Verify Installation

```bash
# Check that the CLI works
lucidfence --help

# Start the server (will run in live mode if you have credentials configured)
lucidfence server
```

Then open http://localhost:8765 in your browser.

## Next Steps

See [Quick Start](./quickstart.md) to connect your first UEM provider.
