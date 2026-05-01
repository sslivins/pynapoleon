# pynapoleon

Standalone Python library for Napoleon Astound-series fireplaces.

Napoleon's cloud is the [Ayla Networks](https://www.aylanetworks.com/) IoT
platform, so this library is a thin Napoleon-property mapping layer on top of
[`ayla-iot-unofficial`](https://pypi.org/project/ayla-iot-unofficial/) (the
same package the Shark vacuum Home Assistant integration uses).

> **Status:** alpha — under active reverse-engineering. APIs will change.

## Features (planned)

- Async login / token refresh (delegated to `ayla-iot-unofficial`)
- Discover fireplaces on the account
- Read state: power, flame, heater, setpoint, ember/top RGB lights, schedules
- Write state via batch datapoints (single round-trip)
- Apply favourites (`partytime`, `campfirewarmth`, `summerday`, `glowingsunset`)
- Celsius-native (with helpers for Fahrenheit display)

## Installation

```
pip install pynapoleon
```

## Usage

```python
import asyncio
from pynapoleon import NapoleonClient

async def main():
    async with NapoleonClient(
        email="you@example.com",
        password="...",
        # app_id / app_secret default to the Napoleon mobile app values;
        # override only if you've registered your own Ayla app.
    ) as client:
        await client.login()
        for fp in await client.fireplaces():
            await fp.refresh()
            print(fp.name, "power:", fp.power, "flame:", fp.flame_speed)
            await fp.set_setpoint_c(20)

asyncio.run(main())
```

## CLI

A small CLI is provided for manual testing:

```
python -m pynapoleon login
python -m pynapoleon list
python -m pynapoleon state <DSN>
python -m pynapoleon set <DSN> power_on_off=1
```

## Security note

Like any Ayla-based device, talking to the cloud requires an `app_id` and
`app_secret`. This library ships the values used by the Napoleon mobile app
as defaults; they are **not secrets** in the cryptographic sense (any
mitmproxy capture exposes them), but the project does not endorse abuse.

Do **not** commit credential files, tokens, or mitmproxy captures.

## Reverse-engineering notes

See [`docs/protocol.md`](docs/protocol.md) for the property catalog and
write-command details derived from app traffic.

## License

MIT — see [`LICENSE`](LICENSE).
