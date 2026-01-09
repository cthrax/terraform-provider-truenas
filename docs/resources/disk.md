---
page_title: "truenas_disk Resource - terraform-provider-truenas"
subcategory: ""
description: |-
  Updated disk configuration data.
---

# truenas_disk (Resource)

Updated disk configuration data.

## Example Usage

```terraform
resource "truenas_disk" "example" {
  hddstandby = "ALWAYS ON"
  advpowermgmt = "DISABLED"
}
```

## Schema

### Required

- None

### Optional

- `number` (Optional) - Numeric identifier assigned to the disk.. Type: `integer`
- `lunid` (Optional) - Logical unit number identifier or `null` if not applicable.. Type: `string`
- `description` (Optional) - Human-readable description of the disk device.. Type: `string`
- `hddstandby` (Optional) - Hard disk standby timer in minutes or `ALWAYS ON` to disable standby. Valid values: `ALWAYS ON`, `5`, `10`. Type: `string`
- `advpowermgmt` (Optional) - Advanced power management level or `DISABLED` to turn off power management. Valid values: `DISABLED`, `1`, `64`. Type: `string`
- `bus` (Optional) - System bus type the disk is connected to.. Type: `string`
- `enclosure` (Optional) - Physical enclosure information or `null` if not in an enclosure.. Type: `string`
- `pool` (Optional) - Name of the storage pool this disk belongs to. `null` if not part of any pool.. Type: `string`
- `passwd` (Optional) - Disk encryption password (masked for security).. Type: `string`

### Read-Only

- `id` (String) The ID of this resource.

## Import

Import is supported using the following syntax:

```shell
terraform import truenas_disk.example <id>
```
