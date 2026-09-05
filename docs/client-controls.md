# Client configuration controls

These methods **change router configuration**. They have source-backed wire
contracts and offline tests, but have not been executed on either test router.
Firmware support and actual write behavior remain unverified on hardware.
Unsupported RPCs raise `CudyUnsupportedError`; other failures raise
`CudyAPIError` (authentication failures use `CudyAuthError`).

| Python method | RPC | Parameters |
| --- | --- | --- |
| `set_client_name(mac, name, device_type="other", brand="undefined")` | `devices.set_name` | `[mac, name, device_type, brand]` |
| `set_client_internet_blocked(mac, blocked, name="")` | `devices.internet_block` | `[1 if blocked else 0, mac, name]` |
| `set_client_rate_limit(mac, download_mbps=..., upload_mbps=...)` | `devices.rate_limit` | `[mac, {"ddrate": "...", "uurate": "..."}]` |
| `clear_client_rate_limit(mac)` | `devices.rate_limit` | `[mac]` |

Arguments after the client name, and rate-limit arguments, are keyword-only.
MAC addresses are validated and normalized. Rates accept decimal strings,
`Decimal`, integers or floats, are finite and nonnegative, and support at most
three fractional decimal places in Mbps. Excess precision is rejected rather
than silently rounded. Both directions must be supplied. Zero is transmitted
literally; use the clear method to remove limits rather than assuming zero has
the same effect.

Naming also writes type and brand. Supply the existing values to preserve
metadata; omitting them sends the app defaults, not a partial update. The
optional Internet-block name is also sent as metadata. Blocking the client
you are using can interrupt access.

All methods return the firmware's `result` verbatim. A null acknowledgement is
not converted to `False`. No method automatically retries after authentication
rejection, timeout, or network failure: a lost response does not prove the
write failed. Inspect the corresponding read before deciding to retry manually.
An initial authentication may occur if the session has no token.

Example for an explicitly intended change, using an already configured router
and a deliberately selected client (not run by the read-only examples):

```python
router.set_client_rate_limit(
    selected_mac, download_mbps="25.5", upload_mbps="5"
)
limits = router.get_client_rate_limit(selected_mac)
```

## Protocol basis

The request shapes follow the Cudy app's corresponding configuration workflow.
They are covered by offline payload tests, not a guarantee of identical behavior
on every firmware. Browser configuration forms use a separate submission
mechanism; their CSRF fields do not belong in the app RPC payload.
