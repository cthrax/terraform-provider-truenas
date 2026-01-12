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

# Test action resource - pool scrub
resource "truenas_action_pool_scrub" "test" {
  id     = 1  # Pool ID
  action = "START"
}

output "scrub_job_id" {
  value = truenas_action_pool_scrub.test.job_id
}

output "scrub_state" {
  value = truenas_action_pool_scrub.test.state
}

output "scrub_progress" {
  value = truenas_action_pool_scrub.test.progress
}
