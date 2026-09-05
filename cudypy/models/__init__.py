"""Models for the cudypy package."""

from .device import Device
from .status import (
    EthernetPort,
    InterfaceStatus,
    LanConfig,
    RateLimit,
    SystemStatus,
    WirelessInterface,
)

__all__ = [
    "Device",
    "EthernetPort",
    "LanConfig",
    "RateLimit",
    "WirelessInterface",
    "SystemStatus",
    "InterfaceStatus",
]
