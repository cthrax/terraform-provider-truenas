---
page_title: "truenas_action_mail_send Resource - terraform-provider-truenas"
subcategory: "Actions"
description: |-
  Sends mail using configured mail settings.
---

# truenas_action_mail_send (Resource)

Sends mail using configured mail settings.

This is an action resource that executes the `mail.send` operation. Actions are triggered on resource creation and cannot be undone on destroy.

## Example Usage

```terraform
resource "truenas_action_mail_send" "example" {
  message = "value"
}
```

## Schema

### Input Parameters

- `message` (String, Required) Email message content and configuration.
- `config` (String, Optional) Optional mail configuration overrides for this message.

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
