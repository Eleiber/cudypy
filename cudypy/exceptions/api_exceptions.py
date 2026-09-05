"""Exceptions for the CudyPy package."""

from typing import Optional


class CudyAPIError(Exception):
    """Base exception for Cudy API errors."""

    def __init__(self, *args, code: Optional[int] = None):
        super().__init__(*args)
        self.code = code


class CudyAuthError(CudyAPIError):
    """Exception for authentication failures."""

    pass


class CudyDiscoveryError(CudyAPIError):
    """Exception for mDNS discovery failures."""

    pass


class CudyUnsupportedError(CudyAPIError):
    """The firmware explicitly reported that an RPC method does not exist."""
