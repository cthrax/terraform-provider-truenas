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

resource "truenas_action_mail_send" "test_email" {
  message = jsonencode({
    subject = "Test from Terraform Provider"
    text    = "This is a test email sent via the uploadable action resource."
    to      = ["root@localhost"]
  })
}

output "action_result" {
  value = {
    action_id = truenas_action_mail_send.test_email.action_id
    state     = truenas_action_mail_send.test_email.state
    result    = truenas_action_mail_send.test_email.result
  }
}
