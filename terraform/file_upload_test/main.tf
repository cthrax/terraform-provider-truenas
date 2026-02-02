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

resource "truenas_filesystem_put" "test_file" {
  path         = "/mnt/${var.truenas_pool}/terraform-test-upload.txt"
  file_content = base64encode("UPDATED content from Terraform!\nTimestamp: ${timestamp()}\n")
}

output "uploaded_path" {
  value = truenas_filesystem_put.test_file.path
}
