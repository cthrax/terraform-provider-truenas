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

# Deploy Vaultwarden app
resource "truenas_app" "vaultwarden" {
  app_name    = "vaultwarden"
  catalog_app = "vaultwarden"
  train       = "community"
  version     = "1.3.34"
  
  values = jsonencode({
    # Vaultwarden Configuration
    TZ = "Europe/Belgrade"
    vaultwarden = {
      postgres_image = "postgres:16-alpine"
      db_password = "changeme123"
    }
    
    # User and Group
    vaultwardenRunAs = {
      user = 568
      group = 568
    }
    
    # Network
    vaultwardenNetwork = {
      webPort = 30027
    }
    
    # Storage - use ixVolume (automatic)
    vaultwardenStorage = {
      data = {
        type = "ixVolume"
      }
      pgData = {
        type = "ixVolume"
      }
    }
    
    # Resources
    resources = {
      limits = {
        cpus = 2
        memory = 4096
      }
    }
  })
}

output "app_name" {
  value = truenas_app.vaultwarden.app_name
}

output "app_id" {
  value = truenas_app.vaultwarden.id
}
