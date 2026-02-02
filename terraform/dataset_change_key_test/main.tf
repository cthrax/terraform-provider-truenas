terraform {
  required_providers {
    truenas = {
      source = "bmanojlovic/truenas"
    }
  }
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

provider "truenas" {
  host  = var.truenas_host
  token = var.truenas_token
}

# Create encrypted dataset with passphrase
resource "truenas_pool_dataset" "encrypted" {
  name       = "${var.truenas_pool}/test-change-key"
  type       = "FILESYSTEM"
  encryption = true
  encryption_options = jsonencode({
    generate_key = false
    passphrase   = "original-passphrase-123"
    algorithm    = "AES-256-GCM"
  })
  inherit_encryption = false
}

# Change the encryption key (passphrase -> new passphrase)
resource "truenas_pool_dataset_change_key" "test" {
  dataset_id = truenas_pool_dataset.encrypted.name
  options = jsonencode({
    passphrase = "new-passphrase-456"
  })
}

output "dataset_name" {
  value = truenas_pool_dataset.encrypted.name
}

output "change_key_id" {
  value = truenas_pool_dataset_change_key.test.id
}
