"""
Unit tests for edge cases in the API key service.
"""

import pytest

from mnemo.services.api_key import extract_api_key_prefix


@pytest.mark.parametrize(
    "key",
    [
        "",
        "   ",
        "_",
        "__",
        "mnm_live_",
        "mnm_badtype_payload",
        "badprefix_live_payload",
    ],
)
def test_extract_api_key_prefix_invalid_formats_raise_error(key):
    """Test that various malformed API keys raise ValueError."""
    with pytest.raises(ValueError):
        extract_api_key_prefix(key)


@pytest.mark.parametrize(
    "key, expected_prefix",
    [
        (f"mnm_live_{'a' * 64}", "mnm_live_"),
        (f"mnm_test_{'a' * 64}", "mnm_test_"),
    ],
)
def test_extract_api_key_prefix_valid_formats(key, expected_prefix):
    """Test that valid API keys return the correct prefix."""
    assert extract_api_key_prefix(key) == expected_prefix
