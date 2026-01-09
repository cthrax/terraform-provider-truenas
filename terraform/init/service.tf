# Enable SSH service
resource "truenas_service" "ssh" {
  id     = "ssh"
  enable = true
}
