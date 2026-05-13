[![release][release-badge]][release-url]
[![commits-since-latest][commits-badge]][commits-url]
![stars][stars-badge]
![Dynamic Regex Badge][hacs-badge]
\
![build][python-badge]
![build][hassfest-badge]
![build][hacs-valid-badge]

# Settle Up Integration for Home Assistant

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
