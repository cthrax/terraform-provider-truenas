output "iso_path" {
  value       = truenas_filesystem_put.cloud_init_iso.path
  description = "Path to uploaded cloud-init ISO on TrueNAS"
}

output "vm_ip" {
  value       = var.vm_ip
  description = "Configured VM IP address"
}

output "vm_hostname" {
  value       = var.vm_hostname
  description = "Configured VM hostname"
}
