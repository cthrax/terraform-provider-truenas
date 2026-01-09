# TrueNAS VM Bootstrap

This Terraform configuration creates a TrueNAS VM on TrueNAS for testing the provider.

## VM Specifications

- **Name:** testtruenas
- **CPU:** 4 vCPUs
- **Memory:** 10GB
- **Boot Disk:** 30GB
- **Data Disks:** 4x 128GB (for ZFS pool testing)

## Usage

1. Create `secrets.auto.tfvars.json` with credentials:
```json
{
  "truenas_host": "192.168.1.100",
  "truenas_token": "your-api-token-here"
}
```

2. (Optional) Override defaults in `terraform.tfvars`:
```hcl
pool_name        = "tank"
truenas_iso_path = "/mnt/tank/iso/TrueNAS-SCALE.iso"
bridge_interface = "br0"
```

3. Initialize and apply:
```bash
terraform init
terraform plan
terraform apply
```

## Post-Installation

After VM creation:
1. Start the VM from TrueNAS UI or CLI
2. Boot from ISO and install TrueNAS
3. Configure network and API access
4. Create ZFS pool with the 4x 128GB disks
5. Generate API token for nested testing

## Testing Provider Features

With nested TrueNAS running, you can test:
- Pool and dataset operations
- User and group management
- Sharing (NFS, SMB)
- Network configuration
- Service management
