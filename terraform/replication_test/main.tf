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

# Test replication with schedule (JSON object)
resource "truenas_replication" "test" {
  name            = "test-replication"
  direction       = "PUSH"
  transport       = "LOCAL"
  source_datasets = ["${var.pool_name}/test"]
  target_dataset  = "${var.pool_name}/test-backup"
  recursive       = false
  auto            = true
  
  # name_regex or
  # also_include_naming_schema = ["%Y-%m-%d_%H-%M"]
  
  schedule = jsonencode({
    minute = "0"
    hour   = "2"
    dom    = "*"
    month  = "*"
    dow    = "*"
    begin  = "00:00"
    end    = "23:59"
  })
  
  retention_policy = "NONE"
}

output "replication_id" {
  value = truenas_replication.test.id
}
