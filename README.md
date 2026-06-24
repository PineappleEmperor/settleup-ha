[![release][release-badge]][release-url]
[![commits-since-latest][commits-badge]][commits-url]
![stars][stars-badge]
![Dynamic Regex Badge][hacs-badge]
\
![build][python-badge]
![build][hassfest-badge]
![build][hacs-valid-badge]

# Settle Up Integration for Home Assistant

> [!NOTE]
> **AI assistance:** I'm a programmer; this project is built with AI (Claude, via Claude Code) for implementation, code review, and QA — under human direction, guided by my [`ha-integration`](https://github.com/PineappleEmperor/pineapple-claude-hacs) skill. Architecture and final review are mine; every change is human-reviewed before it merges.

This is an unofficial Settle Up integration for Home Assistant. This integration allows you to interact with your Settle Up account via the [Settle Up API](https://api.settleup.io/).

> **Prerequisite** — you need a Settle Up account and a Firebase API key. Request one from tomas (at) stepuplabs.io.

## Installation

### HACS (recommended)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pineappleemperor&repository=settleup-ha&category=Integration)

### Manual
Copy the `custom_components/settleup` directory into your Home Assistant `custom_components` folder and restart.

## Configuration

**Settings → Devices & Services → Add Integration → Settle Up**

Enter your email, password, and Firebase API key.

After setup, open the integration's **Configure** menu to change the polling interval (default 5 minutes, range 1–60 minutes).

## Removing the integration

This integration follows standard Home Assistant removal:

1. **Settings → Devices & Services → Settle Up**.
2. Open the **⋮** menu on the integration entry and choose **Delete**.
3. All Settle Up devices, entities, and the stored credentials are removed automatically.

To uninstall completely, remove the repository from HACS (or delete the
`custom_components/settleup` folder for a manual install) and restart Home Assistant.

## Sensors

One device is created per Settle Up group. Each device has:

| Sensor | Description |
|--------|-------------|
| **Last Transaction** | Timestamp of the most recent transaction. Attributes include `currency`, `members`, `debts`, `main_member`, and `recent_transactions`. |
| **Member balance** (one per member) | Net balance for that member — positive means they are owed money, negative means they owe. Attributes break down individual debts. Sensors for **inactive members are disabled by default**. |
| **Pair debt** (one per member pair, disabled by default) | Signed debt between a canonical pair sorted alphabetically by name. Positive → first owes second; negative → second owes first; zero → settled. |

## Services

### `settleup.add_transaction`

Add an expense to a group.

| Field | Required | Description |
|-------|----------|-------------|
| `group` | ✓ | The Settle Up group device |
| `purpose` | ✓ | Description of the expense |
| `amount` | ✓ | Total amount (supports templates) |
| `paid_by` | ✓ | Member who paid |
| `for_members` | ✓ | Members splitting the expense |
| `weights` | — | Relative shares, e.g. `[2, 1]` for a 2:1 split. Cannot be used with `member_amounts`. Supports templates. |
| `member_amounts` | — | Exact amount owed by each member. Cannot be used with `weights`. Supports templates. |
| `category` | — | Expense category (default: `general`). Supports templates and custom values. |
| `currency_code` | — | ISO 4217 code. Defaults to the group's currency. |

If neither `weights` nor `member_amounts` is provided, the expense is split equally.

### `settleup.settle_debt`

Record a debt settlement (transfer) between two members.

| Field | Required | Description |
|-------|----------|-------------|
| `group` | ✓ | The Settle Up group device |
| `from_member` | ✓ | Member paying |
| `to_member` | ✓ | Member being paid |
| `amount` | ✓ | Settlement amount |
| `currency_code` | — | ISO 4217 code. Defaults to the group's currency. |

## Use cases

- **Shared-household dashboard** — show each member's net balance and who owes whom at a glance.
- **Spend logging by voice or automation** — add an expense from an automation when a recurring bill is due, or via a voice assistant.
- **Settlement reminders** — notify a member when their debt in a group crosses a threshold.
- **Auto-record routine costs** — log the weekly shop, fuel, or rent split automatically on a schedule.

## How data is updated

The integration **polls** the Settle Up cloud API on a fixed interval (default **5 minutes**, configurable 1–60 minutes via the integration's **Configure** menu). Each poll fetches all groups, members, balances, debts, and recent transactions, then updates every sensor. There is no push/webhook channel, so changes made in the Settle Up app appear in Home Assistant at the next poll. Calling `settleup.add_transaction` or `settleup.settle_debt` writes immediately to Settle Up; the new state is reflected on the following poll.

## Examples

Notify when a member owes more than 50 in any group:

```yaml
automation:
  - alias: "Settle Up — debt reminder"
    trigger:
      - trigger: numeric_state
        entity_id: sensor.settle_up_holiday_alice
        below: -50
    action:
      - action: notify.mobile_app_phone
        data:
          message: "Alice's balance is {{ states('sensor.settle_up_holiday_alice') }}."
```

Log the weekly shop every Saturday, split equally:

```yaml
automation:
  - alias: "Settle Up — weekly shop"
    trigger:
      - trigger: time
        at: "10:00:00"
    condition:
      - condition: time
        weekday: [sat]
    action:
      - action: settleup.add_transaction
        data:
          group: <group device id>
          purpose: "Weekly shop"
          amount: 85.40
          paid_by: sensor.settle_up_home_alice
          for_members:
            - sensor.settle_up_home_alice
            - sensor.settle_up_home_bob
```

## Known limitations

- **Polling only** — no real-time push; updates lag by up to the configured interval.
- **One account per Home Assistant** — the integration is single-instance (`single_config_entry`).
- **Currency conversion** follows the group's configured display currency; per-transaction exchange rates are not recalculated locally.
- **A Firebase Web API key is required** and must be requested from Settle Up (see Prerequisite above).
- Member and pair-debt sensor names follow the member names in Settle Up, so they are not translatable.

## Troubleshooting

- **"Invalid email or password"** on setup — verify the email/password and that the **Firebase API key** is correct. The integration will prompt to re-authenticate if credentials stop working.
- **Sensors show `unavailable`** — the last poll failed (network or Settle Up outage). The integration retries automatically; check **Settings → System → Logs** for `custom_components.settleup`.
- **A service call fails** — the error message names the cause (e.g. wrong group device, an entity that is not a member sensor, or mismatched `weights`/`member_amounts` lengths).
- **New group or member missing** — wait for the next poll; entities for new groups/members are created automatically. Inactive members and pair-debt sensors are **disabled by default** — enable them in the entity settings.
- For more detail, raise the log level:
  ```yaml
  logger:
    logs:
      custom_components.settleup: debug
  ```

<!-- Badges -->

[commits-badge]: https://img.shields.io/github/commits-since/PineappleEmperor/settleup-ha/latest?style=flat-square
[downloads-badge]: https://img.shields.io/github/downloads/pineappleemperor/settleup-ha/total?style=flat-square
[hacs-badge]: https://img.shields.io/badge/dynamic/regex?url=https%3A%2F%2Fraw.githubusercontent.com%2Fhacs%2Fdefault%2Frefs%2Fheads%2Fmaster%2Fintegration&search=(%22PineappleEmperor%2Fsettleup-ha%22)&replace=default&style=flat-square&label=hacs&link=https%3A%2F%2Fgithub.com%2Fhacs%2Fintegration
[hacs-valid-badge]: https://img.shields.io/github/actions/workflow/status/PineappleEmperor/settleup-ha/hacs_validate.yml?style=flat-square&label=hacs%20valid
[release-badge]: https://img.shields.io/github/v/release/PineappleEmperor/settleup-ha?style=flat-square
[stars-badge]: https://img.shields.io/github/stars/PineappleEmperor/settleup-ha?style=flat-square
[hassfest-badge]: https://img.shields.io/github/actions/workflow/status/PineappleEmperor/settleup-ha/hassfest_validate.yml?style=flat-square&label=hassfest
[python-badge]: https://img.shields.io/github/actions/workflow/status/PineappleEmperor/settleup-ha/python_validate.yml?style=flat-square&label=python

<!-- References -->

[commits-url]: https://github.com/PineappleEmperor/settleup-ha/commits/main/
[hacs-url]: https://github.com/hacs/integration
[release-url]: https://github.com/PineappleEmperor/settleup-ha/releases
