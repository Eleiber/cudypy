"""Optional browser smoke test: synthetic data, no HTTP server or router access.

Run with Playwright + Chromium installed: python dashboard/tests/browser_smoke.py
"""

import argparse
import sys
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dashboard import app as dashboard
from cudypy import Device
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screenshots", type=Path, help="Optional directory for synthetic screenshots"
    )
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    router = Mock()
    router.authenticate.return_value = True
    router.get_devices.return_value = [
        Device(
            "02:00:00:00:00:01",
            "192.0.2.10",
            device_name="Office laptop",
            connection_type="wifi",
            is_online=True,
            bandwidth_up=32000,
            bandwidth_down=240000,
            signal_strength=-48,
        ),
        Device(
            "02:00:00:00:00:02",
            "192.0.2.11",
            device_name="Media server",
            connection_type="ethernet",
            is_online=None,
            bandwidth_up=100000,
            bandwidth_down=80000,
        ),
    ]
    dashboard.router_instance = router
    client = dashboard.app.test_client()
    reads = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def route_request(route):
            request = route.request
            parsed = urlsplit(request.url)
            assert parsed.netloc == "127.0.0.1:5000", "External request blocked"
            reads.append(parsed.path)
            response = client.open(
                parsed.path,
                method=request.method,
                data=request.post_data,
                content_type=request.headers.get("content-type"),
                base_url="http://127.0.0.1:5000",
            )
            route.fulfill(
                status=response.status_code,
                body=response.data,
                headers={"content-type": response.content_type},
            )

        page.route("**/*", route_request)
        page.clock.install()
        page.goto("http://127.0.0.1:5000")
        page.wait_for_function("document.querySelectorAll('#trafficGraph circle').length === 2")
        page.locator("#clientSearch").fill("Office")
        assert page.locator(".device-card").count() == 1
        page.locator("#clientSearch").fill("")
        page.locator("#historyClient").select_option("02:00:00:00:00:01")
        assert "234.4 KiB/s" in page.locator("#historySummary").inner_text()
        page.locator("#pausePolling").click()
        count = reads.count("/api/devices")
        page.clock.fast_forward(40000)
        assert reads.count("/api/devices") == count
        page.locator("#pausePolling").click()
        page.wait_for_function("document.querySelectorAll('#trafficGraph circle').length === 4")
        # Seed a synthetic history for a readable desktop/mobile visual check.
        page.evaluate("""() => {
            trafficHistory.clear();
            for (let i = 0; i < 24; i++) trafficHistory.add([
                {mac_address: '02:00:00:00:00:01', bandwidth_up: 30000 + i*1000,
                 bandwidth_down: 100000 + (i%7)*25000}
            ], Date.now() - (23-i)*10000);
            renderHistory();
        }""")
        if args.screenshots:
            page.screenshot(path=str(args.screenshots / "dashboard-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_function(
            "document.querySelector('#trafficGraph').viewBox.baseVal.width < 390"
        )
        if args.screenshots:
            page.screenshot(path=str(args.screenshots / "dashboard-mobile.png"), full_page=True)
        page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
        page.locator("#clearHistory").click()
        assert page.locator("#trafficGraph circle").count() == 0
        assert not errors, errors
        assert "/api/refresh" not in reads
        assert not any(call[0].startswith("set_") for call in router.method_calls)
        browser.close()
        print(
            "Browser checks passed: graph, selection, search, pause/resume, clear, mobile layout; no router access"
        )


if __name__ == "__main__":
    main()
