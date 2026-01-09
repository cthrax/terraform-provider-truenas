# TrueNAS Terraform Provider

A comprehensive Terraform provider for TrueNAS SCALE using native JSON-RPC 2.0 over WebSocket.

## Features

- ✅ **274 Generated Resources** covering the entire TrueNAS API surface
- ✅ **WebSocket JSON-RPC** for superior performance vs REST
- ✅ **Complete CRUD Operations** for all resources
- ✅ **Terraform Plugin Framework** implementation
- ✅ **Comprehensive Documentation** for all resources

## Requirements

- **TrueNAS SCALE**: Version 25.10.1 (Goldeye) or later
- **Terraform**: 0.13+

## Quick Start

### Installation

```hcl
terraform {
  required_providers {
    truenas = {
      source = "bmanojlovic/truenas"
    }
  }
}
```

### Configuration

```hcl
provider "truenas" {
  host  = "192.168.1.100"
  token = "your-api-token"
}
```

### Basic Usage

```hcl
resource "truenas_vm" "example" {
  name        = "testvm"
  description = "Test VM created by Terraform"
  vcpus       = 2
  memory      = 2048  # 2GB in megabytes
  autostart   = false
}
```

## Available Resources

This provider includes **274 resources** covering:

- **Virtual Machines** (`truenas_vm`, `truenas_vm_device`)
- **Storage** (`truenas_pool`, `truenas_pool_dataset`, `truenas_pool_snapshot`)
- **Users & Groups** (`truenas_user`, `truenas_group`)
- **Sharing** (`truenas_sharing_nfs`, `truenas_sharing_smb`)
- **Network** (`truenas_interface`, `truenas_staticroute`)
- **Services** (`truenas_service`)
- **And many more...**

## Documentation

- [Provider Configuration](docs/index.md)
- [Resource Documentation](docs/resources/)
- [Examples](examples/)

## Development

Built with:
- Go 1.21+
- Terraform Plugin Framework
- WebSocket JSON-RPC 2.0
- OpenAPI-driven code generation

## Testing

This provider uses a two-tier testing strategy:

### Unit Tests (CI/CD)

Unit tests run automatically in CI and test core logic without requiring a TrueNAS instance:
- Schema validation
- Parameter building
- Optional field handling
- Business logic

```bash
# Run unit tests locally
go test -v ./internal/...
```

### Acceptance Tests (Local Only)

Acceptance tests require a real TrueNAS instance and are skipped in CI:
- Full CRUD lifecycle testing
- Real API integration
- Resource state management

**Prerequisites:**
- TrueNAS SCALE instance (accessible via network)
- API token with appropriate permissions

**Running acceptance tests:**

```bash
# Set environment variables
export TRUENAS_HOST=192.168.1.100
export TRUENAS_TOKEN=your-api-token

# Run acceptance tests
./test-local.sh
```

Or run directly:

```bash
TRUENAS_HOST=192.168.1.100 TRUENAS_TOKEN=your-token TF_ACC=1 go test ./internal/provider -v -run TestAcc
```

**Note:** Acceptance tests create and destroy real resources on your TrueNAS instance. Use a test environment.

## License

This provider is licensed under the Mozilla Public License 2.0.
