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

variable "truenas_host" {
  type = string
}

variable "truenas_token" {
  type      = string
  sensitive = true
}

variable "truenas_pool" {
  type = string
}

# Create encrypted dataset with passphrase
resource "truenas_pool_dataset" "encrypted" {
  name = "${var.truenas_pool}/test-enc-unlock-v2"
  encryption_options = jsonencode({
    passphrase = "test-passphrase-123"
    algorithm  = "AES-256-GCM"
  })
  encryption = true
  inherit_encryption = false
}

# Unlock the dataset using passphrase
resource "truenas_pool_dataset_unlock" "unlock_dataset" {
  dataset_id = truenas_pool_dataset.encrypted.name
  options = jsonencode({
    datasets = [{
      name       = truenas_pool_dataset.encrypted.name
      passphrase = "test-passphrase-123"
    }]
  })
}

output "dataset_info" {
  value = {
    name      = truenas_pool_dataset.encrypted.name
    encrypted = truenas_pool_dataset.encrypted.encryption
    unlock_id = truenas_pool_dataset_unlock.unlock_dataset.id
  }
}
