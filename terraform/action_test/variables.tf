variable "truenas_host" {
  description = "TrueNAS host"
  type        = string
}

variable "truenas_token" {
  description = "TrueNAS API token"
  type        = string
  sensitive   = true
}
