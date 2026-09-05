"""Unit tests for CudyPy exceptions."""

import pytest
from cudypy import CudyAPIError, CudyAuthError, CudyDiscoveryError


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_cudy_auth_error_inherits_from_api_error(self):
        """Test that CudyAuthError inherits from CudyAPIError."""
        assert issubclass(CudyAuthError, CudyAPIError)

    def test_cudy_discovery_error_inherits_from_api_error(self):
        """Test that CudyDiscoveryError inherits from CudyAPIError."""
        assert issubclass(CudyDiscoveryError, CudyAPIError)

    def test_cudy_api_error_inherits_from_exception(self):
        """Test that CudyAPIError inherits from Exception."""
        assert issubclass(CudyAPIError, Exception)


class TestExceptionRaising:
    """Test raising and catching exceptions."""

    def test_raise_cudy_api_error(self):
        """Test raising CudyAPIError."""
        with pytest.raises(CudyAPIError) as exc_info:
            raise CudyAPIError("Test API error")

        assert str(exc_info.value) == "Test API error"

    def test_raise_cudy_auth_error(self):
        """Test raising CudyAuthError."""
        with pytest.raises(CudyAuthError) as exc_info:
            raise CudyAuthError("Test auth error")

        assert str(exc_info.value) == "Test auth error"

    def test_raise_cudy_discovery_error(self):
        """Test raising CudyDiscoveryError."""
        with pytest.raises(CudyDiscoveryError) as exc_info:
            raise CudyDiscoveryError("Test discovery error")

        assert str(exc_info.value) == "Test discovery error"


class TestExceptionCatching:
    """Test catching exceptions at different levels."""

    def test_catch_auth_error_as_api_error(self):
        """Test that CudyAuthError can be caught as CudyAPIError."""
        with pytest.raises(CudyAPIError):
            raise CudyAuthError("Auth failed")

    def test_catch_discovery_error_as_api_error(self):
        """Test that CudyDiscoveryError can be caught as CudyAPIError."""
        with pytest.raises(CudyAPIError):
            raise CudyDiscoveryError("Discovery failed")

    def test_catch_specific_auth_error(self):
        """Test catching specific CudyAuthError."""
        try:
            raise CudyAuthError("Auth failed")
        except CudyAuthError as e:
            assert "Auth failed" in str(e)
        except CudyAPIError:
            pytest.fail("Should have caught CudyAuthError specifically")

    def test_catch_specific_discovery_error(self):
        """Test catching specific CudyDiscoveryError."""
        try:
            raise CudyDiscoveryError("Discovery failed")
        except CudyDiscoveryError as e:
            assert "Discovery failed" in str(e)
        except CudyAPIError:
            pytest.fail("Should have caught CudyDiscoveryError specifically")


class TestExceptionMessages:
    """Test exception message handling."""

    def test_api_error_with_empty_message(self):
        """Test CudyAPIError with empty message."""
        error = CudyAPIError("")
        assert str(error) == ""

    def test_api_error_with_multiline_message(self):
        """Test CudyAPIError with multiline message."""
        message = "Error occurred\nLine 2\nLine 3"
        error = CudyAPIError(message)
        assert str(error) == message

    def test_api_error_with_special_characters(self):
        """Test CudyAPIError with special characters."""
        message = "Error: 'test' failed @ 100%"
        error = CudyAPIError(message)
        assert str(error) == message
