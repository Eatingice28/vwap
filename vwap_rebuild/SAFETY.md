# Safety Boundaries

## Why the Webull credential belongs only on the VPS

The Webull **app key** and **app secret** can authenticate an application. They must therefore be treated as sensitive credentials, even when this particular collector is limited to market data. The completed values belong only in `/etc/webull-feed.env` on your VPS, with restrictive file permissions. They must not be put into the Streamlit application, Streamlit secrets, GitHub, browser storage, screenshots, logs, or chat messages.

The dashboard receives only a sanitized JSON document through HTTPS. That document contains symbol names, bar data, status information, and a generated timestamp. It deliberately contains no app key, app secret, account identifier, token file, or brokerage client. A separate random **feed access token** protects the JSON endpoint; it is not a Webull credential and may be stored in Streamlit secrets.

> The collector is designed as a **read-only market-data service**. Its source imports only the maintained SDK's market-data client and common market-data enums. It does not import a trading, order, account, asset, position, or portfolio client, and it contains no code path that can place, modify, or cancel a trade.

## Operational boundaries

Run the collector as its own Linux user, virtual environment, directory, systemd service, and output folder. Do not put it in the existing trading bot directory. Do not copy that bot's configuration, environment file, credential file, dependency lockfile, or source code into this project.

The supplied service binds the collector to `127.0.0.1`. A separate HTTPS reverse proxy may publish only `/feed.json`; the supplied proxy template returns `404` for other paths. Keep the feed token private and rotate it in both locations if it is exposed.

## What the dashboard does and does not do

The dashboard presents descriptive, educational VWAP and premarket-range context. It can label readings as bullish, bearish, mixed, neutral, or a watch area, but it does not provide forecasts, promises, or instructions to take action. Demo mode uses made-up data and requires no credential.
