"""Run the README response demonstration without a router or credentials."""

import doctest
import re
from pathlib import Path
from unittest.mock import Mock

from cudypy import SystemStatus


def test_readme_response_example_matches_model_output():
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    section = readme.split("## Example usage and output\n", 1)[1].split("\n## ", 1)[0]
    payload = {
        "model": "Example router",
        "firmware": "example-firmware",
        "uptime": "3600",
        "memory": {"total": 128000, "available": 64000},
    }
    example = re.search(r"```pycon\n(.*?)\n```", section, re.S)[1]
    router = Mock()
    router.get_system_info.return_value = SystemStatus.from_api_response(payload)
    test = doctest.DocTestParser().get_doctest(
        example, {"router": router}, "README response", "README.md", 0
    )
    result = doctest.DocTestRunner().run(test)
    assert result.failed == 0
    assert result.attempted == 7
    router.get_system_info.assert_called_once_with()
