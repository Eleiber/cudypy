"""Models for the cudypy package."""

from .device import Device
from .records import (
    AccessPoint,
    ClientName,
    ClientTraffic,
    Configuration,
    ConfigurationSections,
    FirmwareRecord,
    ParentalGroup,
    ProviderCatalog,
    ResponsePage,
    ResponseValue,
    WdsStatus,
    WorkMode,
)
from .status import (
    EthernetPort,
    InterfaceStatus,
    LanConfig,
    RateLimit,
    ResourceUsage,
    SystemStatus,
    WirelessInterface,
)

__all__ = [
    "AccessPoint",
    "ClientName",
    "ClientTraffic",
    "Configuration",
    "ConfigurationSections",
    "FirmwareRecord",
    "ParentalGroup",
    "ProviderCatalog",
    "ResponsePage",
    "ResponseValue",
    "WdsStatus",
    "WorkMode",
    "Device",
    "EthernetPort",
    "LanConfig",
    "RateLimit",
    "ResourceUsage",
    "WirelessInterface",
    "SystemStatus",
    "InterfaceStatus",
]
