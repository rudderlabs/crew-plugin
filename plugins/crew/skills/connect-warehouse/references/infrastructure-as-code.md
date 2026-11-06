# The sync in Terraform or rudder-cli

Both create the same three things as the RudderStack app: a Reverse ETL source (a SQL model or a table), a Webhook destination pointed at the RudderCrew webhook, and the connection between them. Neither can start a sync: the first one is **Sync now** in the app, on the connection's page.

Both name the warehouse account by id. `list_sources` with `retl_type: "all"` on the RudderStack MCP shows it as `accountId` on any existing Reverse ETL source; a new account is added in the app, because it holds the warehouse credentials.

Column names are matched exactly. Snowflake returns unquoted names in upper case (`ACCOUNT_ID`), so `primary_key`, `identifiers.from` and `mappings.from` use that case there.

## Terraform

Provider `rudderlabs/rudderstack` 5.x. It reads its token from `RUDDERSTACK_ACCESS_TOKEN` (a service access token for the workspace, which the user creates and sets in their own environment).

```hcl
terraform {
  required_providers {
    rudderstack = {
      source  = "rudderlabs/rudderstack"
      version = "~> 5.0"
    }
  }
}

provider "rudderstack" {}

variable "crew_webhook_url" {
  type = string
}

variable "crew_webhook_token" {
  type      = string
  sensitive = true
}

resource "rudderstack_retl_source_model" "account_health" {
  name                   = "RudderCrew: account health"
  source_definition_name = "snowflake"
  account_id             = "<warehouse account id>"

  config {
    primary_key = "ACCOUNT_ID"
    sql         = file("${path.module}/account_health.sql")
  }
}

resource "rudderstack_destination_webhook" "crew_account_health" {
  name = "RudderCrew: account health"

  config {
    webhook_url    = var.crew_webhook_url
    webhook_method = "POST"
    headers = [
      {
        from = "Authorization"
        to   = "Bearer ${var.crew_webhook_token}"
      }
    ]
  }
}

resource "rudderstack_retl_connection" "account_health_to_crew" {
  source_id      = rudderstack_retl_source_model.account_health.id
  destination_id = rudderstack_destination_webhook.crew_account_health.id
  sync_behaviour = "full" # or "upsert" (SKILL.md step 5)

  schedule {
    type = "manual" # until the first sync passes; then basic (every_minutes) or cron (cron_expression)
  }

  event {
    type = "track"
    name = "Account Health Snapshot"
  }

  identifiers {
    from = "ACCOUNT_ID"
    to   = "user_id"
  }

  mappings {
    from = "PLAN"
    to   = "properties.plan"
  }

  mappings {
    from = "ACTIVE_USERS_7D"
    to   = "properties.active_users_7d"
  }

  # One mappings block per column the Agent reads.
}
```

Set the two variables from the saved file without printing them:

```bash
set -a; . ~/crew-lists/webhooks/<webhookId>.env; set +a
export TF_VAR_crew_webhook_url="$CREW_WEBHOOK_URL" TF_VAR_crew_webhook_token="$CREW_WEBHOOK_TOKEN"
terraform plan
```

What the provider does that the app does not show:

- **`identifiers.to` is `user_id` or `anonymous_id`.** The provider refuses anything else at plan time, including `userId`, which its own track-to-webhook example uses.
- **`event`, `sync_behaviour` and `cursor_column` replace the connection when changed**, and `source_id` and `destination_id` do too. A plan that says the connection "must be replaced" means a new connection whose first sync sends every row again.
- **`headers` is marked sensitive**, so the plan hides it, but the state file holds it in plain text. Keep state in the team's protected remote backend.
- **`schedule.every_minutes` is at least 5.** There is no time-zone field; a cron schedule runs in UTC.
- **`cursor_column`** (Upsert only) reads just the rows whose cursor value is newer than the last run's. It suits a table that only grows; a row whose other columns change without moving the cursor is not sent again.
- A table instead of a model: `rudderstack_retl_source_table`, with `schema` and `table` in `config` in place of `sql`.

## rudder-cli

Version 1.x, inside a project that already manages this workspace. Three specs:

```yaml
version: rudder/v1
kind: retl-source-sql-model
metadata:
  name: account-health-model
spec:
  id: account-health-model
  display_name: "RudderCrew: account health"
  account_id: "<warehouse account id>" # or account: "#account:<spec id>" when the project manages the account
  source_definition: snowflake
  primary_key: ACCOUNT_ID
  enabled: true
  sql: |
    SELECT ...
---
version: rudder/v1
kind: destination
metadata:
  name: crew-account-health
spec:
  id: crew-account-health
  display_name: "RudderCrew: account health"
  type: webhook
  definition_version: 1
  enabled: true
  config:
    webhook_url: https://<the RudderCrew host>/webhook/<webhookId>/events
    webhook_method: POST
    headers:
      - from: Authorization
        to: "{{ .CREW_WEBHOOK_AUTHORIZATION }}"
    connection_mode:
      warehouse: cloud
---
version: rudder/v1
kind: retl-connections
metadata:
  name: account-health-to-crew
spec:
  connections:
    - id: account-health-to-crew
      source: "#retl-source-sql-model:account-health-model"
      destination: "#destination:crew-account-health"
      enabled: true
      config:
        sync_behaviour: full # or upsert
        schedule:
          type: manual
        event:
          type: track
          name: Account Health Snapshot
        identifiers:
          - from: ACCOUNT_ID
            to: user_id
        mappings:
          - from: PLAN
            to: properties.plan
          - from: ACTIVE_USERS_7D
            to: properties.active_users_7d
```

The header value is one variable holding the whole `Bearer <token>`, supplied from the environment with a `RUDDER_` prefix:

```bash
set -a; . ~/crew-lists/webhooks/<webhookId>.env; set +a
export RUDDER_CREW_WEBHOOK_AUTHORIZATION="Bearer $CREW_WEBHOOK_TOKEN"
rudder-cli validate
rudder-cli apply --dry-run
```

What rudder-cli enforces:

- **Every header value is a secret.** Write each as a single `{{ .VAR }}` reference; `validate` warns on a literal. In this destination `from` is the header's name and `to` its value, the reverse of the HTTP Webhook destination.
- **`connection_mode: { warehouse: cloud }`** on the destination, or a Reverse ETL source cannot connect to it.
- **One Reverse ETL source per destination**, and never an event-stream source on the same destination.
- **Mirror is refused** on a Reverse ETL connection, and a basic or cron schedule runs at most every 5 minutes, in UTC.
- **`sync_behaviour`, `event` and `cursor_column` cannot change** on an existing connection: `apply` fails. Changing `source` or `destination` makes a new connection, whose first sync sends every row again.
- rudder-cli cannot start or report on syncs: Sync now in the app, then `get_retl_source_syncs` on the RudderStack MCP.
