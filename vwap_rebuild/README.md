# Educational VWAP & Premarket Context Rebuild

**Author:** Manus AI  
**Purpose:** A read-only, educational dashboard for VWAP and premarket-range context. It does not place, modify, or cancel trades; does not import a brokerage client into the dashboard; and does not provide forecasts or instructions for action.

## What changed

The prior dashboard depended on Polygon/Massive directly from Streamlit. This rebuild retains that compatibility path and the self-contained Demo mode, but adds a separate **Webull real-time** path. The new path keeps the Webull app key and app secret only on your VPS in a small collector service. The Streamlit app sees only a credential-free JSON feed over HTTPS.

| Component | Where it runs | What it contains | What it must never contain |
| --- | --- | --- | --- |
| **Collector** | Your VPS | Webull market-data SDK, app key/secret in an environment file, 1-minute bar polling, local JSON file and localhost-only HTTP service | Trading/account/order code, your separate trading bot’s files, dashboard code |
| **HTTPS proxy** | Your VPS | TLS termination and a narrow `/feed.json` route to `127.0.0.1:8088` | Webull credentials or a listener exposed directly on port 8088 |
| **Dashboard** | Streamlit Community Cloud | VWAP/premarket calculations, Demo mode, optional Polygon/Massive mode, sanitized Webull feed URL and feed token | `WEBULL_APP_KEY`, `WEBULL_APP_SECRET`, a Webull SDK, or any trade capability |

> The collector imports only `ApiClient`, `DataClient`, `Category`, and `Timespan` from the maintained Webull SDK. Its only SDK request is `get_batch_history_bar` for 1-minute `PRE` and `RTH` bars. The SDK’s official market-data guide documents the `DataClient` historical-bars workflow and its batch variant. [1]

## Repository layout — verified real directories

```text
vwap_rebuild/
├── README.md
├── SAFETY.md
├── validation_notes.md
├── collector/
│   ├── requirements.txt
│   ├── webull-feed.env.example
│   ├── caddy/
│   │   └── Caddyfile.example
│   ├── systemd/
│   │   └── webull-feed.service
│   └── webull_feed/
│       ├── __init__.py
│       ├── app.py
│       ├── config.py
│       └── market_data.py
├── dashboard/
│   ├── requirements.txt
│   ├── streamlit_app.py
│   ├── .streamlit/
│   │   ├── config.toml
│   │   └── secrets.toml.example
│   └── vwap_dashboard/
│       ├── __init__.py
│       ├── config.py
│       ├── context.py
│       ├── data_sources.py
│       ├── demo_data.py
│       └── indicators.py
└── tests/
    └── static_and_simulated_checks.py
```

The `.streamlit/` and Python-package folders are actual directories, not flattened file names. Place the **contents of `dashboard/` at the root** of the GitHub repository used by Streamlit. Keep `collector/` on the VPS and out of the dashboard repository.

## Step 1 — Copy the collector to a new VPS-only directory

Do not touch, inspect, or merge this project into the existing trading-bot directory. Copy only the local `collector/` directory to a new folder such as `/opt/webull-feed` on the VPS. The final VPS folder should contain `requirements.txt`, `webull-feed.env.example`, `webull_feed/`, `systemd/`, and `caddy/`.

On the VPS, run the following commands. Replace `/path/to/collector` with the location where you uploaded the collector directory.

```bash
sudo useradd --system --home /opt/webull-feed --shell /usr/sbin/nologin webullfeed
sudo mkdir -p /opt/webull-feed /var/lib/webull-feed
sudo cp -a /path/to/collector/. /opt/webull-feed/
sudo chown -R webullfeed:webullfeed /opt/webull-feed /var/lib/webull-feed
sudo chmod 750 /opt/webull-feed /var/lib/webull-feed
```

Create a separate virtual environment. This keeps the collector independent of any existing Python environment.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
sudo -u webullfeed python3 -m venv /opt/webull-feed/.venv
sudo -u webullfeed /opt/webull-feed/.venv/bin/python -m pip install --upgrade pip
sudo -u webullfeed /opt/webull-feed/.venv/bin/python -m pip install -r /opt/webull-feed/requirements.txt
```

The official SDK documentation currently lists `webull-openapi-python-sdk` as the Python package and documents its market-data support. [2] If the final install complains that `grpcio-tools` needs a C++ compiler, install the build prerequisites and retry **only the last install command**:

```bash
sudo apt install -y build-essential python3-dev
sudo -u webullfeed /opt/webull-feed/.venv/bin/python -m pip install --upgrade 'setuptools<81' wheel
sudo -u webullfeed /opt/webull-feed/.venv/bin/python -m pip install --no-build-isolation -r /opt/webull-feed/requirements.txt
```

This fallback was necessary in the build sandbox because the SDK’s legacy `grpcio-tools==1.51.1` dependency had no compatible prebuilt wheel for that Python environment. It may not be necessary on your VPS. Do not copy any credential from the separate trading system while resolving an installation issue.

## Step 2 — Create the VPS-only credential and settings file

Copy the template to `/etc`, set restrictive permissions, and edit it with a terminal editor.

```bash
sudo cp /opt/webull-feed/webull-feed.env.example /etc/webull-feed.env
sudo chown root:root /etc/webull-feed.env
sudo chmod 600 /etc/webull-feed.env
sudo nano /etc/webull-feed.env
```

Use this completed shape. The app key and app secret are placeholders here—put your real values only in the VPS file. Confirm `WEBULL_REGION` and `WEBULL_API_ENDPOINT` against the details assigned to your Webull Securities Singapore OpenAPI application; do not assume the example `us`/`api.webull.com` values are the right production values for your account.

```dotenv
WEBULL_APP_KEY=your_real_app_key
WEBULL_APP_SECRET=your_real_app_secret
WEBULL_REGION=your_assigned_region
WEBULL_API_ENDPOINT=your_assigned_production_endpoint
WEBULL_WATCHLIST=NVDA,AMD,SPY,QQQ
WEBULL_POLL_SECONDS=20
WEBULL_HISTORY_BAR_COUNT=800
WEBULL_BIND_HOST=127.0.0.1
WEBULL_PORT=8088
WEBULL_OUTPUT_PATH=/var/lib/webull-feed/feed.json
WEBULL_FEED_ACCESS_TOKEN=replace_with_a_long_random_value
WEBULL_LOG_LEVEL=INFO
```

Generate the feed access token with the following command and paste the result in the environment file. This token protects the dashboard feed; it is **not** a Webull credential.

```bash
openssl rand -hex 32
```

The default watchlist has one main symbol plus SPY and QQQ. Add 5–10 symbols by comma-separating them, for example `NVDA,AMD,AAPL,TSLA,SPY,QQQ`. The collector sends one batch historical-bars request for the whole configured watchlist and requests `PRE` and `RTH`. The maintained SDK accepts a `trading_sessions` list for this call. [1]

## Step 3 — Install and start the independent systemd service

Copy the supplied unit file, then enable and start it. The unit uses a dedicated Linux user, a separate working directory, a separate virtual environment, restart-on-failure, and a local-only listener.

```bash
sudo cp /opt/webull-feed/systemd/webull-feed.service /etc/systemd/system/webull-feed.service
sudo systemctl daemon-reload
sudo systemctl enable --now webull-feed.service
sudo systemctl status webull-feed.service --no-pager
```

Use these commands whenever you need a status view or recent log lines. The service intentionally reports safe error categories without writing the app secret to the log.

```bash
sudo systemctl status webull-feed.service --no-pager
sudo journalctl -u webull-feed.service -n 100 --no-pager
sudo journalctl -u webull-feed.service -f
```

For the first confirmation, test on the VPS itself. Substitute the actual `WEBULL_FEED_ACCESS_TOKEN` only in your shell command; do not save it in shell history if that is a concern.

```bash
curl -i -H 'X-Feed-Token: YOUR_FEED_TOKEN' http://127.0.0.1:8088/healthz
curl -s -H 'X-Feed-Token: YOUR_FEED_TOKEN' http://127.0.0.1:8088/feed.json | python3 -m json.tool | head -80
```

A healthy response is `200` with `ok` for `/healthz`. The JSON must show `"schema_version": 1`, a `symbols` object, bar records, and no credential fields. A `stale` status means the most recent good feed is still being served but the last collection attempt failed. An `error` status means no usable feed exists yet.

## Step 4 — Publish only the feed through HTTPS

The collector must remain bound to `127.0.0.1`; do **not** open port `8088` publicly. Publish only `/feed.json` through an HTTPS reverse proxy. The supplied Caddy option is the shortest path when you have a domain or subdomain pointed at the VPS.

First, make an `A` (and, if applicable, `AAAA`) record such as `feed.example.com` point to the VPS. Ensure external ports 80 and 443 reach the VPS. Caddy obtains and renews a publicly trusted certificate automatically when its configured hostname has public DNS and ports 80/443 are reachable. [3]

Install Caddy using your normal server package policy. Caddy’s official installation guide provides Ubuntu packages and its package service setup. [4] With a standard Ubuntu package installation, the following is usually sufficient:

```bash
sudo apt update
sudo apt install -y caddy
sudo cp /opt/webull-feed/caddy/Caddyfile.example /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile
```

Replace `feed.example.com` with your real subdomain. Then validate and reload the proxy:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
```

If you use UFW, allow only standard web ports; **do not add a rule for port 8088**.

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

From a device outside the VPS, validate the HTTPS route. A response without the token should be `404`; a response with the token should be a JSON document.

```bash
curl -I https://feed.example.com/feed.json
curl -s -H 'X-Feed-Token: YOUR_FEED_TOKEN' https://feed.example.com/feed.json | python3 -m json.tool | head -80
```

Caddy passes request headers to its upstream by default, so the `X-Feed-Token` header supplied by Streamlit is preserved. Its official reverse-proxy guide documents the basic `reverse_proxy 127.0.0.1:PORT` configuration and hostname-based automatic HTTPS behavior. [3]

## Step 5 — Put the dashboard in GitHub without flattening folders

Create a clean local copy of the **contents** of `dashboard/`. Before pushing, the directory containing `streamlit_app.py` must also contain `requirements.txt`, `.streamlit/`, and `vwap_dashboard/`. A safe local sequence is:

```bash
cd /path/to/vwap_rebuild/dashboard
find . -maxdepth 3 -type f | sort
# Confirm that ./.streamlit/config.toml and ./vwap_dashboard/indicators.py appear.

git init
git add .
git status
git commit -m "Rebuild educational VWAP dashboard with isolated Webull feed"
git branch -M main
git remote add origin https://github.com/Eatingice28/vwap.git
git push -u origin main --force
```

The final `--force` is appropriate only because you explicitly described the old repository as disposable. If you prefer a rollback point, create a new repository instead, or make a GitHub backup branch before replacing `main`. Never add a completed `secrets.toml` file, `/etc/webull-feed.env`, or the collector directory to this dashboard repository.

The official Community Cloud documentation states that a `requirements.txt` file may reside in the repository root or next to the entrypoint file. This rebuild places it next to `streamlit_app.py`. [5]

## Step 6 — Deploy the dashboard in Streamlit Community Cloud

Create a new app in Streamlit Community Cloud, choose `Eatingice28/vwap`, select the `main` branch, and set the main file path to `streamlit_app.py`. In **Advanced settings** (or the deployed app’s settings), paste the following values. Replace every placeholder; do not paste the Webull app key or app secret.

```toml
app_password = "a_private_dashboard_password"

polygon_api_key = "your_polygon_or_massive_key_if_you_use_that_mode"
use_massive_host = false

webull_feed_url = "https://feed.example.com/feed.json"
webull_feed_token = "the_same_random_feed_token_from_the_VPS"
```

The `polygon_api_key` remains present only for the optional Polygon/Massive mode. The **Webull real-time** mode uses only `webull_feed_url` and `webull_feed_token`. Streamlit’s documentation recommends keeping secrets out of Git and placing them in the app settings’ secrets field. [6]

After saving the secrets, deploy the app. If newly saved settings do not appear to take effect, open the application controls and reboot/restart the app once; then reload the page. Keep the app password set if the dashboard is not intended for public viewing.

## Step 7 — Validate all three dashboard modes

| Mode | Setup required | Expected result |
| --- | --- | --- |
| **Demo mode** | Nothing | Synthetic multi-ticker cards, SPY/QQQ context, VWAP table, and chart. No network credential needed. |
| **Live mode (Polygon/Massive)** | `polygon_api_key`; set `use_massive_host = true` only when appropriate | One session per watched symbol, with an older-session fallback if present-day data is not covered. |
| **Live mode (Webull real-time)** | Working HTTPS feed URL and matching feed token | Multi-ticker cards populated from one sanitized collector feed request. The dashboard warns when feed data is stale or premarket bars are absent. |

In Webull real-time mode, make sure every sidebar watchlist symbol also appears in `WEBULL_WATCHLIST` on the VPS. SPY and QQQ are always added to the dashboard request, so they must be in the collector watchlist as well.

## Troubleshooting

| Symptom | What it generally means | Step-by-step response |
| --- | --- | --- |
| **Collector does not start** | A missing environment variable, missing package, permissions problem, or malformed unit file is likely. | Run `sudo systemctl status webull-feed.service --no-pager`, then `sudo journalctl -u webull-feed.service -n 100 --no-pager`. Confirm `/etc/webull-feed.env` exists, has mode `600`, and includes all variables. Confirm `/var/lib/webull-feed` belongs to `webullfeed`. After any fix, run `sudo systemctl restart webull-feed.service`. |
| **Service is crash-looping** | systemd is repeatedly restarting a process that immediately fails. | Run `sudo journalctl -u webull-feed.service -f` and read the first error after a restart. Check the exact Python path in the unit: `/opt/webull-feed/.venv/bin/python`. Re-run the isolated `pip install` command from Step 1. Use the optional compiler fallback only if the log identifies the legacy SDK build problem. |
| **Webull HTTP 401** | Authentication was rejected. | Check `WEBULL_APP_KEY`, `WEBULL_APP_SECRET`, `WEBULL_REGION`, and `WEBULL_API_ENDPOINT` against the details assigned to the OpenAPI application. Check for accidental spaces or quote characters. Do not paste credentials into the log, dashboard, or GitHub. Restart the service after correcting the VPS environment file. |
| **Webull HTTP 403 / entitlement message** | The key authenticated but the market-data product or extended-hours access was not allowed. | Check the account’s current OpenAPI market-data entitlement and whether it includes U.S. stocks/ETFs and extended-hours bars. The official Webull market-data guide notes that U.S. stock and ETF data requires an active market-data subscription and identifies 403 as a likely subscription issue. [1] Keep the dashboard in Demo mode while the entitlement is resolved. |
| **Premarket bars are missing** | The feed received regular-session bars but no 4:00–9:30 AM ET bars. | Confirm the collector’s `trading_sessions=["PRE", "RTH"]` is still present in the deployed source. Confirm the current time/session is appropriate. Inspect `/feed.json` for `"premarket_data_available": false`. If it stays false during a session when bars should exist, treat it as an entitlement or provider-availability question; the dashboard will show the limitation instead of inventing premarket levels. |
| **Dashboard says feed is stale** | The JSON exists, but its `generated_at` time is more than two minutes old or the collector reported a failed recent poll. | On the VPS, check `systemctl status` and `journalctl`. Test `curl` against `127.0.0.1:8088/feed.json`, then test the HTTPS URL with the feed token. Check DNS, Caddy status, and whether the output timestamp advances after the poll interval. |
| **Dashboard rejects feed URL/token** | The URL, token, proxy route, or Caddy hostname is incorrect. | Confirm the Streamlit `webull_feed_url` ends in `/feed.json`. Confirm `webull_feed_token` exactly matches `WEBULL_FEED_ACCESS_TOKEN`. Test a valid external `curl` request using the header. A `404` without the header is expected. |
| **A watched symbol has no card in Webull mode** | It is absent from the VPS collector watchlist or no usable bars came back. | Add the symbol to `WEBULL_WATCHLIST`, restart the collector, and wait for one polling cycle. Keep SPY and QQQ included. Verify the symbol appears in `feed.json` before refreshing Streamlit. |
| **Streamlit does not reflect new secrets** | The app is still using the previous process configuration. | Save the TOML in the app’s settings, then reboot/restart the app from its controls and reload the browser. Confirm there are no extra spaces or malformed TOML quotes. |
| **Streamlit deployment cannot find code or dependencies** | Files were uploaded into the wrong level or a directory became flattened. | On GitHub, verify that `streamlit_app.py`, `requirements.txt`, `.streamlit/config.toml`, and `vwap_dashboard/` are all visible from the repository root. Set the main file path to `streamlit_app.py`. |

## Verification completed here

The package passed an offline compilation and simulated-feed test. The collector JSON contract was created from simulated 1-minute bars and parsed successfully by the dashboard adapter. A browser smoke test launched the Streamlit app in Demo mode and rendered the synthetic NVDA/AMD cards, SPY/QQQ context, detail table, and VWAP chart without an exception.

No Webull credential, production account, VPS, or separate trading system was accessed. Therefore, the following must be verified by you on the VPS: **SDK installation against your Python version, app authentication, account entitlement, exact assigned region/endpoint, production polling, and actual premarket-bar availability**.

## References

[1]: https://developer.webull.com/apis/docs/market-data-api/getting-started/ "Webull Market Data API — Getting Started"
[2]: https://developer.webull.com/apis/docs/sdk/ "Webull SDKs and Tools"
[3]: https://caddyserver.com/docs/quick-starts/reverse-proxy "Caddy Reverse Proxy Quick-start"
[4]: https://caddyserver.com/docs/install "Caddy Installation Documentation"
[5]: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies "Streamlit Community Cloud — App Dependencies"
[6]: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management "Streamlit Community Cloud — Secrets Management"
