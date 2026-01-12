---
page_title: "truenas_action_pool_dataset_unlock Resource - terraform-provider-truenas"
subcategory: "Actions"
description: |-
  Unlock dataset `id` (and its children if `unlock_options.recursive` is `true`).
---

# truenas_action_pool_dataset_unlock (Resource)

Unlock dataset `id` (and its children if `unlock_options.recursive` is `true`).

This is an action resource that executes the `pool.dataset.unlock` operation. Actions are triggered on resource creation and cannot be undone on destroy.

## Example Usage

```terraform
resource "truenas_action_pool_dataset_unlock" "example" {
  id = "value"
}
```

## Schema

### Input Parameters

- `id` (String, Required) The dataset ID (full path) to unlock.
- `options` (String, Optional) Options for unlocking including force settings, recursion, and dataset-specific keys.

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
