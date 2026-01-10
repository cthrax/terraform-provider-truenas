#!/bin/bash
set -e

echo "=== TrueNAS VM Deployment ==="
echo ""

# Step 1: Generate and upload cloud-init ISO
echo "Step 1: Generating cloud-init ISO..."
cd cloud-init
terraform init
terraform apply -auto-approve
ISO_PATH=$(terraform output -raw iso_path)
echo "✓ Cloud-init ISO uploaded to: $ISO_PATH"
echo ""

# Step 2: Create VM with cloud-init
echo "Step 2: Creating VM..."
cd ../init
terraform init
terraform apply -auto-approve
echo "✓ VM created"
echo ""

# Get VM IP
cd ../cloud-init
VM_IP=$(terraform output -raw vm_ip)
echo "=== Deployment Complete ==="
echo "Web UI: https://$VM_IP"
echo "SSH: ssh admin@$VM_IP"
echo ""
echo "Note: Wait 2-3 minutes for cloud-init to complete on first boot"
