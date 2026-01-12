---
page_title: "truenas_action_core_bulk Resource - terraform-provider-truenas"
subcategory: "Actions"
description: |-
  Will sequentially call `method` with arguments from the `params` list. For example, running
---

# truenas_action_core_bulk (Resource)

Will sequentially call `method` with arguments from the `params` list. For example, running

This is an action resource that executes the `core.bulk` operation. Actions are triggered on resource creation and cannot be undone on destroy.

## Example Usage

```terraform
resource "truenas_action_core_bulk" "example" {
  method = "value"
}
```

## Schema

### Input Parameters

- `method` (String, Required) Method name to execute for each parameter set.
- `params` (List, Required) Array of parameter arrays, each representing one method call.
- `description` (String, Optional) Format string for job progress (e.g. "Deleting snapshot {0[dataset]}@{0[name]}").

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
