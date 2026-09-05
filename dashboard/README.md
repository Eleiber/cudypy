# Local monitoring dashboard

A local read-only monitoring UI using Flask and browser-native SVG. No frontend
build, CDN, external fonts or charting service is needed. It works without
Internet access once the Python dependencies are installed.

## Start

From the repository root, after installing the library:

```sh
python -m pip install -r dashboard/requirements.txt
# Set ROUTER_URL and either ROUTER_TOKEN or ROUTER_PASSWORD in your environment.
python dashboard/app.py
```

Open `http://127.0.0.1:5000`. The server binds to loopback, disables debug mode
and handles one request at a time. Host/Origin checks restrict local browser
access. Do not expose it publicly or share its router client across a threaded
deployment. The server needs a working route to the router.

## Monitoring

- Upload/download history for all reported clients or one selected client.
- Timestamp axes, point hover tooltips, latest rates and observed peak.
- Up to 180 observations per tab, about 10 seconds after each completed read:
  roughly 30 minutes, longer when requests are slow.
- Explicit gaps for failed polls, missing rates, absent clients and long pauses.
  Aggregates are unknown if any client lacks that rate, not silently partial.
- Pause/resume, clear history and suspension while the tab is hidden.
- Search by name/IP/MAC; sort by name, upload/download rate or signal strength.
- Activity cards and on-demand system/WAN status views.

Graphs show reported client byte rates, **not WAN throughput**, speed tests or
trustworthy cumulative Internet usage. Activity is a heuristic, not a connectivity
test. No history database, cross-tab sharing or multi-router timeline is provided.

History exists only in tab memory: reload, close, or saving settings clears it.
Nothing is stored in localStorage or server history. Failed polls preserve prior
samples with a stale-data message. Data requests do not overlap within a tab.

Refresh now reads a snapshot without replacing the router session. Settings
change the dashboard connection, not router configuration. Changing targets
requires new credentials and clears history. Tokens are replaced by restarting
with a fresh environment value. The UI exposes no library mutation controls.

Compared with the inspected stock pages, this adds tab-local historical
exploration over snapshot polling. It is not full panel replacement or a claim
that no Cudy firmware offers similar visualizations.

## Tests

```sh
python -m pytest tests/test_dashboard.py
node --test dashboard/tests/history.test.cjs
node --check dashboard/static/js/app.js
```

Tests use mocked router responses and synthetic samples.

An optional full-browser check is available after installing Playwright and its
Chromium runtime: `python dashboard/tests/browser_smoke.py`. It intercepts all
page requests with Flask's test client, supplies synthetic devices, and makes no
router requests. It checks graphs, selection, search, pause/resume, clearing and
mobile overflow, and optionally writes synthetic screenshots to a caller-selected directory.
