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

locals {
  storage_vlan_tag    = 9
  storage_vlan_parent = "eno1"
  storage_vlan_cidr   = "10.10.80.10/24"
}

# VLAN interface for Storage network
resource "truenas_interface" "storage_vlan" {
  name        = "vlan9"
  type        = "VLAN"
  description = "Storage VLAN for NFS traffic"

  vlan_parent_interface = local.storage_vlan_parent
  vlan_tag              = local.storage_vlan_tag

  # Parse CIDR and convert to API format
  aliases = [
    jsonencode({
      type    = "INET"
      address = split("/", local.storage_vlan_cidr)[0]
      netmask = tonumber(split("/", local.storage_vlan_cidr)[1])
    })
  ]
}

output "interface_id" {
  value = truenas_interface.storage_vlan.id
}
