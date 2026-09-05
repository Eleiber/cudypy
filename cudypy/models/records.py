"""Detached response models for firmware-dependent reads.

Known domain fields have explicit properties. Unmapped fields remain accessible
as recursively converted records, without pretending their schemas are verified.
"""

from collections.abc import Iterator, Mapping
from copy import deepcopy
from typing import Any, Dict, Generic, Optional, Tuple, Type, TypeVar, Union

from .status import _boolean, _integer, _text

ResponseValue = Union[None, bool, int, float, str, "FirmwareRecord", Tuple["ResponseValue", ...]]


def deserialize(value: Any) -> ResponseValue:
    """Map JSON objects to records and arrays to tuples; preserve scalar values."""
    if isinstance(value, dict):
        return FirmwareRecord(value)
    if isinstance(value, list):
        return tuple(deserialize(item) for item in value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise ValueError("Expected a JSON response value")


class FirmwareRecord(Mapping[str, Any]):
    """Read-only view of an object with safe repr and lossless raw export.

    Attribute access is a convenience for non-reserved firmware field names.
    Indexing always addresses the wire key, including names such as ``items``
    or ``raw``. Missing dynamic attributes raise AttributeError, not None.
    """

    __slots__ = ("_data",)
    _data: Dict[str, Any]

    def __init__(self, data: Dict[str, Any]):
        if not isinstance(data, dict) or not all(isinstance(key, str) for key in data):
            raise ValueError("Expected a response object with text keys")
        object.__setattr__(self, "_data", deepcopy(data))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Response records are read-only snapshots")

    @property
    def raw(self) -> Dict[str, Any]:
        """Return a detached original response; may contain credentials."""
        return deepcopy(self._data)

    def __getitem__(self, key: str) -> Any:
        return deserialize(self._data[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name) from None

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"


class WorkMode(FirmwareRecord):
    @property
    def mode(self) -> Optional[str]:
        return _text(self._data.get("mode"))

    @property
    def name(self) -> Optional[str]:
        return _text(self._data.get("name"))


class ClientName(FirmwareRecord):
    @property
    def mac_address(self) -> Optional[str]:
        return _text(self._data.get("macaddr"))

    @property
    def name(self) -> Optional[str]:
        return _text(self._data.get("name"))


class ClientTraffic(FirmwareRecord):
    """Native client counters, without inferred accounting direction or periods."""

    @property
    def mac_address(self) -> Optional[str]:
        return _text(self._data.get("macaddr"))

    @property
    def upload_bytes_per_second(self) -> Optional[int]:
        return _integer(self._data.get("upspeed"))

    @property
    def download_bytes_per_second(self) -> Optional[int]:
        return _integer(self._data.get("downspeed"))

    @property
    def reported_inbytes(self) -> Optional[int]:
        return _integer(self._data.get("inbytes"))

    @property
    def reported_outbytes(self) -> Optional[int]:
        return _integer(self._data.get("outbytes"))

    @property
    def reported_upbytes(self) -> Optional[int]:
        return _integer(self._data.get("upbytes"))

    @property
    def reported_downbytes(self) -> Optional[int]:
        return _integer(self._data.get("downbytes"))


class AccessPoint(FirmwareRecord):
    @property
    def ssid(self) -> Optional[str]:
        return _text(self._data.get("ssid"))


class WdsStatus(FirmwareRecord):
    @property
    def is_up(self) -> Optional[bool]:
        return _boolean(self._data.get("up"))


class ParentalGroup(FirmwareRecord):
    @property
    def name(self) -> Optional[str]:
        return _text(self._data.get("name"))


class ProviderCatalog(FirmwareRecord):
    @property
    def providers(self) -> Optional[Tuple[str, ...]]:
        value = self._data.get("providers")
        if value is None:
            return None
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("Expected provider identifiers")
        return tuple(value)


T = TypeVar("T", bound=FirmwareRecord)


class ResponsePage(FirmwareRecord, Generic[T]):
    """One explicit page. Accessing entries never fetches another page."""

    __slots__ = ("_entries", "_total_count")
    _entries: Tuple[T, ...]
    _total_count: Optional[int]

    def __init__(self, data: Dict[str, Any], entries_key: str, count_key: str, model: Type[T]):
        super().__init__(data)
        entries = data.get(entries_key)
        if not isinstance(entries, list):
            raise ValueError("Expected page entries")
        count = data.get(count_key)
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("Expected a nonnegative page count")
        object.__setattr__(self, "_entries", tuple(model(item) for item in entries))
        object.__setattr__(self, "_total_count", count)

    @property
    def entries(self) -> Tuple[T, ...]:
        return self._entries

    @property
    def total_count(self) -> Optional[int]:
        return self._total_count


class Configuration(FirmwareRecord):
    """Firmware-defined configuration; nested fields have no inferred schema."""


class ConfigurationSections(FirmwareRecord):
    """A dynamic section-name mapping; keys are never hardcoded."""

    def section(self, name: str) -> Optional[Configuration]:
        if name not in self._data:
            return None
        return Configuration(self._data[name])


def validate_record(record: T) -> T:
    """Validate declared properties eagerly; never defer errors to display time."""
    for cls in type(record).__mro__:
        if cls in (FirmwareRecord, Mapping, object):
            continue
        for name, descriptor in vars(cls).items():
            if isinstance(descriptor, property):
                getattr(record, name)
    if isinstance(record, ResponsePage):
        for entry in record.entries:
            validate_record(entry)
    return record
