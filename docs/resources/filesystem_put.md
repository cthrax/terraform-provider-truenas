---
page_title: "truenas_filesystem_put Resource - truenas"
subcategory: ""
description: |-
  Upload file to TrueNAS filesystem via HTTP multipart API
---

# truenas_filesystem_put (Resource)

Upload files to TrueNAS filesystem using the `filesystem.put` API endpoint. Files must be base64-encoded.

## Example Usage

### Upload Cloud-Init ISO

```terraform
# Generate ISO locally
resource "null_resource" "cloud_init_iso" {
  provisioner "local-exec" {
    command = <<-EOT
      mkisofs -o /tmp/cloud-init.iso -V cidata -J -r /path/to/cloud-init/
      base64 -w 0 /tmp/cloud-init.iso > /tmp/cloud-init.iso.b64
    EOT
  }
}

data "local_file" "cloud_init_iso_b64" {
  depends_on = [null_resource.cloud_init_iso]
  filename   = "/tmp/cloud-init.iso.b64"
}

resource "truenas_filesystem_put" "cloud_init_iso" {
  path    = "/mnt/tank/isos/cloud-init.iso"
  content = data.local_file.cloud_init_iso_b64.content
}
```

### Upload Text File

```terraform
resource "truenas_filesystem_put" "config" {
  path    = "/mnt/tank/configs/app.conf"
  content = base64encode("key=value\nfoo=bar")
}
```

## Schema

### Required

- `path` (String) Destination path on TrueNAS filesystem
- `content` (String, Sensitive) Base64-encoded file content

### Read-Only

- `id` (String) Resource identifier (same as path)

## Notes

- Files must be base64-encoded before upload
- Use `base64encode()` function for text content
- Use external tools (`base64` command) for binary files
- The resource does not delete files on destroy (only removes from state)
