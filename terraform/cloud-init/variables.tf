variable "truenas_host" {
  type        = string
  description = "TrueNAS hostname or IP"
}

variable "truenas_token" {
  type        = string
  sensitive   = true
  description = "TrueNAS API token"
}

variable "pool_name" {
  type        = string
  default     = "tank"
  description = "TrueNAS pool name for ISO storage"
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key for cloud-init user"
}

variable "root_password" {
  type        = string
  sensitive   = true
  description = "Root password for web UI login"
}

variable "vm_hostname" {
  type        = string
  default     = "testtruenas"
  description = "VM hostname"
}

variable "vm_ip" {
  type        = string
  default     = "192.168.1.50"
  description = "VM IP address"
}

variable "vm_gateway" {
  type        = string
  default     = "192.168.1.1"
  description = "VM gateway IP address"
}
