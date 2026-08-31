# User Guide — LucidFence

This guide covers the basic usage of LucidFence for English-speaking users.

## Table of Contents

1. [Installation](./installation.md)
2. [Quick Start](./quickstart.md)
3. [Configuration](./configuration.md)
4. [Geofencing Policies](./policies.md)
5. [UEM Adapters](./adapters.md)
6. [Dashboard](./dashboard.md)
7. [Troubleshooting](./troubleshooting.md)

## Getting Started

### Prerequisites

- Python 3.11+
- Access to your UEM platform (Applivery, Intune, Jamf, etc.)
- OIDC provider for authentication (optional but recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/adrimg3196/lucidfence.git
cd lucidfence

# Install dependencies
pip install -e .

# Initialize configuration
lucidfence init
```

### First Run

```bash
# Start the server
lucidfence server --config config.yaml

# Open the dashboard
open http://localhost:8765
```

## Architecture

LucidFence consists of:

- **Core engine**: Geofencing logic and risk policy evaluation
- **UEM adapters**: Connectors to your device management platforms
- **CLI**: Command-line interface for administration
- **Dashboard**: Web UI for monitoring and management

## Contributing

See [contributing/DEVELOPMENT.md](../contributing/DEVELOPMENT.md) for development guidelines.

## Support

For issues and questions, please use the GitHub issue tracker.
