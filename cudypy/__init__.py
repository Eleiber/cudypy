"""
CudyPy - Python API Wrapper for Cudy Routers

This package provides a clean, object-oriented interface for interacting with Cudy routers
through their local API.
"""

from .core.router import CudyRouter
from .models.device import Device
from .models.status import (
    EthernetPort,
    InterfaceStatus,
    LanConfig,
    RateLimit,
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
    "CudyRouter",
    "Device",
    "EthernetPort",
    "LanConfig",
    "WirelessInterface",
    "SystemStatus",
    "InterfaceStatus",
    "RateLimit",
    "CudyAPIError",
    "CudyAuthError",
    "CudyDiscoveryError",
    "CudyUnsupportedError",
]
