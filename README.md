[![release][release-badge]][release-url]
[![commits-since-latest][commits-badge]][commits-url]
![stars][stars-badge]
![Dynamic Regex Badge][hacs-badge]
\
![build][python-badge]
![build][hassfest-badge]
![build][hacs-valid-badge]

Settle Up Integration (SU) for Home Assistant
=====================================

This is an unofficial Settle Up integration for Home Assistant. This integration allows you to interact with your Settle Up account via the [Settle Up API]([https://docs.google.com/document/d/18mxnyYSm39cbceA2FxFLiOfyyanaBY6ogG7oscgghxU/edit?tab=t.0#heading=h.c38yf4mz8bod](https://api.settleup.io/)).

You will need to have an account on Settle Up and will need to request an API key via their tomas (at) stepuplabs.io.

Features
--------

-   A device for each group.
-   An overall sensor for the last transaction with several useful attributes.
-   A sensor for each member of the group.
-   Sensors for each pair of members (disabled by default).
-   Add a transaction.

Installation
------------

### HACS (Home Assistant Community Store)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=pineappleemperor&repository=settleup-ha&category=Integration)

### Other ways to Install

1.  Ensure that you have HACS installed in your Home Assistant instance.
2.  Add this repository to HACS as a custom repository.
3.  Search for "Settle Up" in HACS and install it.

Configuration
-------------

### Adding the Integration

1.  In Home Assistant, navigate to **Configuration** > **Devices & Services**.
2.  Click on **Add Integration** and search for "Settle Up".
3.  Enter your username, password, and API key to set up your account.

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
