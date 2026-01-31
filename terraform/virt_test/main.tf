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

resource "truenas_vm" "test_vm" {
  name        = "tftestvirt"
  description = "Terraform test VM"
  vcpus       = 1
  memory      = 1024
  autostart   = false
}

output "vm_id" {
  value = truenas_virt_instance.test_vm.id
}

output "vm_name" {
  value = truenas_virt_instance.test_vm.name
}
