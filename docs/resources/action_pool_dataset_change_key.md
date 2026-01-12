---
page_title: "truenas_action_pool_dataset_change_key Resource - terraform-provider-truenas"
subcategory: "Actions"
description: |-
  Change encryption properties for `id` encrypted dataset.
---

# truenas_action_pool_dataset_change_key (Resource)

Change encryption properties for `id` encrypted dataset.

This is an action resource that executes the `pool.dataset.change_key` operation. Actions are triggered on resource creation and cannot be undone on destroy.

## Example Usage

```terraform
resource "truenas_action_pool_dataset_change_key" "example" {
  id = "value"
}
```

## Schema

### Input Parameters

- `id` (String, Required) The dataset ID (full path) to change the encryption key for.
- `options` (String, Optional) Configuration options for changing the encryption key.

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
