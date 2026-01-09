locals {
  truenas_iso_path = var.truenas_iso_path != "" ? var.truenas_iso_path : "/mnt/fast/iso-store/TrueNAS-SCALE-${var.truenas_version}.iso"
  truenas_iso_url  = var.truenas_iso_url != "" ? var.truenas_iso_url : "https://download.sys.truenas.net/TrueNAS-SCALE-Goldeye/${var.truenas_version}/TrueNAS-SCALE-${var.truenas_version}.iso"
}
