# Device observations and uncertainty

## Activity is not reachability

`Device.recently_active` names the inherited heuristic accurately:
`inactive < 30`. The legacy `is_online` field contains the same value. Neither
is a ping result or proof that a client is connected or has Internet access.
The 30-unit threshold and the inactivity field's unit have not been independently
validated against firmware behavior. A quiet or sleeping client can fail an
activity cutoff without being disconnected.

Both values are now optional booleans. Missing, malformed, negative, boolean,
or fractional inactivity data produces `None` (unknown), not `True` or `False`.
This is an intentional compatibility change: callers should use `is True`,
`is False`, and `is None` when they need all three states. `get_online_devices()`
retains its name but returns only clients passing the heuristic, excluding
unknown activity. The dashboard uses activity labels rather than Online/Offline.

`has_internet` reflects the firmware's client Internet-permission field, not
a reachability check. Its legacy missing-field default remains `True`; consult
`raw` if distinguishing missing permissions is important.

## Duration

The Cudy app formats `online` as an elapsed duration in days, hours, minutes
and seconds.
This establishes elapsed seconds, not a Unix timestamp or online boolean.
`reported_online_seconds` preserves that duration. `connected_since` estimates
the start by subtracting it from the local observation time; it is not a
router-provided wall clock. Invalid durations remain unknown. An unrepresentably
large duration stays available as an integer without constructing a timestamp.

## Rates and counters

The APK speed display multiplies `upspeed` and `downspeed` by eight before
formatting bit rates. The wrapper exposes these as bytes/s and formats them
with binary prefixes (`KiB/s`, `MiB/s`).

The native cumulative fields remain distinct:

| Native field | Explicit Python name | Legacy alias |
| --- | --- | --- |
| `inbytes` | `reported_inbytes` | `bytes_received` |
| `outbytes` | `reported_outbytes` | `bytes_sent` |
| `upbytes` | `reported_upbytes` | — |
| `downbytes` | `reported_downbytes` | — |

Direction relative to the client versus router, reset interval, offload effects,
and whether these represent identical accounting domains remain unverified.
Do not derive lifetime upload/download totals by assuming these fields are
interchangeable. Invalid or negative counters/rates remain unknown. The legacy
aliases preserve their original field mappings without asserting their names
describe the actual viewpoint.

`Device.raw` preserves all original fields, including unrecognized values.
It is excluded from repr but may contain private client identifiers and
configuration. Dataclass serialization includes it; do not log or save it
indiscriminately.

## Interpretation limits

The Cudy app's display behavior supports the duration, rate and signal
conversions above. It does not establish the inactivity cutoff as a connectivity
test or prove the byte counters' accounting domains. No controlled traffic or
disconnection experiment is implied by the parser's field mappings.
