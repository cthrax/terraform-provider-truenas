---
page_title: "truenas_service Resource - terraform-provider-truenas"
subcategory: ""
description: |-
  Updated configuration for the service.
---

# truenas_service (Resource)

Updated configuration for the service.

## Example Usage

```terraform
resource "truenas_service" "example" {
  enable = false
  start_on_create = true
}
```

## Schema

### Required

- `enable` (Required) - Whether the service should start on boot.. Type: `boolean`

### Optional

- `start_on_create` (Optional) - Start the resource immediately after creation. Default behavior: starts if not specified. Type: `boolean`

### Read-Only

- `id` (String) The ID of this resource.

## Import

Import is supported using the following syntax:

```shell
terraform import truenas_service.example <id>
```
