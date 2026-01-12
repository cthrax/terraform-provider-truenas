---
page_title: "truenas_action_docker_backup_to_pool Resource - terraform-provider-truenas"
subcategory: "Actions"
description: |-
  Create a backup of existing apps on `target_pool`.
---

# truenas_action_docker_backup_to_pool (Resource)

Create a backup of existing apps on `target_pool`.

This is an action resource that executes the `docker.backup_to_pool` operation. Actions are triggered on resource creation and cannot be undone on destroy.

## Example Usage

```terraform
resource "truenas_action_docker_backup_to_pool" "example" {
  target_pool = "value"
}
```

## Schema

### Input Parameters

- `target_pool` (String, Required) Name of the storage pool to backup Docker data to.

### Computed Outputs

- `action_id` (String) Unique identifier for this action execution
- `job_id` (Int64) Background job ID (if applicable)
- `state` (String) Job state: SUCCESS, FAILED, or RUNNING
- `progress` (Float64) Job progress percentage (0-100)
- `result` (String) Action result data
- `error` (String) Error message if action failed

## Notes

- Actions execute immediately when the resource is created
- Background jobs are monitored until completion
- Progress updates are logged during execution
- The resource cannot be updated - changes force recreation
- Destroying the resource does not undo the action
