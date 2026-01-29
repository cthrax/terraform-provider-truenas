terraform {
  required_providers {
    truenas = {
      source = "bmanojlovic/truenas"
    }
    random = {
      source = "hashicorp/random"
    }
  }
}

provider "truenas" {
  host  = var.truenas_host
  token = var.truenas_token
}

resource "random_id" "cert_suffix" {
  byte_length = 4
}

# Test certificate creation with CSR type
resource "truenas_certificate" "test_csr" {
  name        = "terraform-test-csr-${random_id.cert_suffix.hex}"
  create_type = "CERTIFICATE_CREATE_CSR"
  
  # Certificate subject details
  common              = "test.example.com"
  country             = "US"
  state               = "California"
  city                = "San Francisco"
  organization        = "Test Org"
  organizational_unit = "IT"
  email               = "admin@example.com"
  
  # Key configuration
  key_type   = "RSA"
  key_length = 2048
  
  # Subject Alternative Names
  san = ["test.example.com", "www.test.example.com"]
  
  # Digest algorithm
  digest_algorithm = "SHA256"
}

output "certificate_id" {
  value       = truenas_certificate.test_csr.id
  description = "Created certificate ID"
}

output "certificate_name" {
  value       = truenas_certificate.test_csr.name
  description = "Certificate name"
}
