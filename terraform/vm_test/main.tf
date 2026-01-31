terraform {
  required_providers {
    truenas = {
      source = "bmanojlovic/truenas"
    }
  }
}

provider "truenas" {
  host  = var.truenas_host
  token = var.truenas_token
}

variable "truenas_host" {}
variable "truenas_token" { sensitive = true }
variable "truenas_pool" {}

resource "truenas_vm" "test" {
  name        = "tftestvirt"
  description = "Terraform test VM"
  vcpus       = 1
  memory      = 1024  # 1GB
  autostart   = false
}

# Create zvol for VM disk
resource "truenas_pool_dataset" "vmdisk" {
  name    = "${var.truenas_pool}/vmdisk"
  type    = "VOLUME"
  volsize = 10737418240  # 10GB
}

# Add NIC device
resource "truenas_vm_device" "nic" {
  vm = truenas_vm.test.id
  
  attributes = jsonencode({
    dtype = "NIC"
    type = "VIRTIO"
  })
}

# Add disk device  
resource "truenas_vm_device" "disk" {
  vm = truenas_vm.test.id
  
  attributes = jsonencode({
    dtype = "DISK"
    path = "/dev/zvol/${truenas_pool_dataset.vmdisk.name}"
    type = "VIRTIO"
  })
  
  depends_on = [truenas_pool_dataset.vmdisk]
}

output "vm_id" {
  value = truenas_vm.test.id
}

output "vm_name" {
  value = truenas_vm.test.name
}
