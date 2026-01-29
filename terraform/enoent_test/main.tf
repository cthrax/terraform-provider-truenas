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

# Test with API key resource
resource "truenas_api_key" "test" {
  name     = "terraform-enoent-test"
  username = "truenas_admin"
}

output "api_key_id" {
  value = truenas_api_key.test.id
}
