"""
CudyPy - Python API Wrapper for Cudy Routers

This package provides a clean, object-oriented interface for interacting with Cudy routers
through their local API.
"""

from .core.router import CudyRouter
from .models.records import (
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
from .models.device import Device
from .models.status import (
    EthernetPort,
    InterfaceStatus,
    LanConfig,
    RateLimit,
    ResourceUsage,
    SystemStatus,
    WirelessInterface,
)
from .exceptions.api_exceptions import (
    CudyAPIError,
    CudyAuthError,
    CudyDiscoveryError,
    CudyUnsupportedError,
)

__version__ = "0.1.0"

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
    "CudyRouter",
    "Device",
    "EthernetPort",
    "LanConfig",
    "WirelessInterface",
    "SystemStatus",
    "InterfaceStatus",
    "RateLimit",
    "ResourceUsage",
    "CudyAPIError",
    "CudyAuthError",
    "CudyDiscoveryError",
    "CudyUnsupportedError",
]
