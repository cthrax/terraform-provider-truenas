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

provider "truenas" {
  host  = var.truenas_host
  token = var.truenas_token
}

# NOTE: This is a test configuration only - DO NOT APPLY
# Requires a real support ticket number from TrueNAS support
resource "truenas_action_support_attach_ticket" "test" {
  data = jsonencode({
    ticket   = 12345
    filename = "debug.log"
  })
  file_content = base64encode("test file content")
}

output "action_id" {
  value = truenas_action_support_attach_ticket.test.action_id
}
