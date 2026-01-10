# Generate cloud-init user-data
resource "local_file" "user_data" {
  filename = "${path.module}/.terraform/cloud-init/user-data"
  content  = <<-EOF
    #cloud-config
    hostname: ${var.vm_hostname}
    
    # Set root password for web UI login
    chpasswd:
      list: |
        root:${var.root_password}
      expire: false
    
    # Enable SSH
    ssh_pwauth: true
    disable_root: false
    
    # Create admin user with SSH key
    users:
      - name: admin
        ssh_authorized_keys:
          - ${var.ssh_public_key}
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
        groups: sudo
    
    # Network configuration
    network:
      version: 2
      ethernets:
        eth0:
          addresses: [${var.vm_ip}/24]
          gateway4: ${var.vm_gateway}
          nameservers:
            addresses: [8.8.8.8, 1.1.1.1]
    
    # Enable and start SSH service
    runcmd:
      - systemctl enable ssh
      - systemctl start ssh
  EOF
}

# Generate cloud-init meta-data
resource "local_file" "meta_data" {
  filename = "${path.module}/.terraform/cloud-init/meta-data"
  content  = <<-EOF
    instance-id: ${var.vm_hostname}-001
    local-hostname: ${var.vm_hostname}
  EOF
}
