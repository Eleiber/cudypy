# Wireless configuration

`get_wireless_config()` returns a `ConfigurationSections` snapshot; `.raw`
exports the original firmware section dictionary.
`get_wireless_interface(section)` reads that configuration and returns a
`WirelessInterface` for a caller-selected section, or `None` when absent.
Use the actual section key from the configuration, not an assumed radio name,
SSID, or operating-system interface name. Selecting a radio section rather
than an interface section will leave interface-only fields unknown.

The model exposes `section`, `ssid`, `encryption`, `disabled`, `hidden`,
`device`, and `mode`. Boolean fields accept native booleans, 0/1 and their
string equivalents; missing fields remain `None`. These are configured
values, not proof that an interface is currently operating or reachable.
All original fields remain in `raw`. Passwords and other unknown fields are
excluded from the normal model repr, but **raw dictionaries and dataclass
serialization can expose credentials**. Do not log or persist those values.

## Configuration writes

`set_wifi_config(config)` submits `wifi.set_conf` with `[config]` and returns
the firmware result verbatim. It never automatically replays the request.
Wi-Fi changes may disconnect the controlling client. A timeout does not prove
failure: read the configuration before deciding to retry manually.

The Cudy app uses a nested object with optional `iface`, `radio`, `mld`, and
`access_filter` fields. The first three contain section-name-to-field-object
mappings; `access_filter` is an integer. For example, the following illustrates
the disabled-only interface payload:

```python
router.set_wifi_config({"iface": {selected_section: {"disabled": 1}}})
```

This is an advanced configuration API. It validates nonempty groups and
sections and finite JSON serialization, not firmware-specific channel,
encryption, password, regulatory, or cross-radio constraints. Field names,
allowed values and behavior of omitted fields depend on firmware. No merge,
default expansion, or read-modify-write is performed. Do not pass the flat
`get_wireless_config()` result directly; it is not the write schema. Empty
section objects are rejected rather than used as an implicit deletion request.
Multi-SSID add/delete operations use separate APK methods and are not mapped
onto this helper.

The write payload has offline test coverage. Wi-Fi configuration writes have
not been checked on the test routers; read availability does not establish
write support.
