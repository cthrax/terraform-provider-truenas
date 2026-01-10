# Cloud-Init ISO Generator

This example generates a cloud-init ISO and uploads it to TrueNAS using the provider's file upload capability.

## Prerequisites

- `mkisofs` or `genisoimage` installed locally
- TrueNAS API token with filesystem write permissions

## Usage

```bash
# Create terraform.tfvars
cat > terraform.tfvars <<EOF
truenas_host   = "192.168.1.100"
truenas_token  = "your-api-token"
pool_name      = "tank"
ssh_public_key = "ssh-rsa AAAA..."
vm_hostname    = "myvm"
vm_ip          = "192.168.1.50"
EOF

# Initialize and apply
terraform init
terraform apply
```

## What It Does

1. **Generates cloud-init files** (`user-data`, `meta-data`)
2. **Creates ISO** using `mkisofs` or `genisoimage`
3. **Encodes to base64** for Terraform transport
4. **Uploads to TrueNAS** via HTTP multipart API

## Outputs

- `iso_path` - Path on TrueNAS where ISO is stored
- `vm_ip` - Configured IP address
- `vm_hostname` - Configured hostname

## Next Steps

Use the `iso_path` output to attach the cloud-init ISO to a VM:

```hcl
resource "truenas_vm_device" "cloud_init" {
  vm = truenas_vm.myvm.id
  attributes = jsonencode({
    dtype = "CDROM"
    path  = module.cloud_init.iso_path
  })
  order = 1007
}
```
