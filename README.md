# Genesis WP

[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]

A custom component for [Home Assistant](https://home-assistant.io/), domain `genesis_wp`, for heat pumps built on the Thermia Genesis controller platform. They are reached over Modbus TCP. The first target is the Stiebel Eltron WPE-I 07.1 Plus, which has an internal WPM-G controller.

It is built on the [genesis-wp](https://github.com/david-aggeler/genesis-wp) library, and it can be installed alongside the upstream `thermiagenesis` integration.

> **Status: in development, not released.** The integration is being moved onto the async, read-only genesis-wp library. Until that work is done, this tree still carries upstream's entities and its `pythermiagenesis` dependency. The target is a strictly read-only integration (sensor and binary_sensor) that never writes to the heat pump.

## Installation

HACS custom repository, once a release is tagged:

1. In HACS, add `https://github.com/david-aggeler/genesis-wp-ha` as a custom repository of type *Integration*.
2. Install **Genesis WP** and restart Home Assistant.
3. Go to *Settings → Devices & services → Add integration* and search for **Genesis WP**.

Manual install: copy `custom_components/genesis_wp/` into your Home Assistant `custom_components/` folder and restart.

## Configuration is done in the UI

## Contributions are welcome!

If you want to contribute, please read the [contribution guidelines](CONTRIBUTING.md).

## Credits

This is a fork of [ulrichwi/thermiagenesis](https://github.com/ulrichwi/thermiagenesis), which in turn forks [CJNE/thermiagenesis](https://github.com/CJNE/thermiagenesis) by [@cjne](https://github.com/cjne). MIT license, original copyright notice kept in [LICENSE](LICENSE).

Upstream was generated from [@oncleben31](https://github.com/oncleben31)'s [Home Assistant Custom Component Cookiecutter](https://github.com/oncleben31/cookiecutter-homeassistant-custom-component) template. The code template was mainly taken from [@Ludeeus](https://github.com/ludeeus)'s [integration_blueprint][integration_blueprint].

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/david-aggeler/genesis-wp-ha.svg?style=for-the-badge
