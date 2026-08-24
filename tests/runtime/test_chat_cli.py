from __future__ import annotations

import pytest

from ontchatbot.cli.chat import _parse_args


def test_chat_cli_does_not_accept_a_provider_selection() -> None:
    with pytest.raises(SystemExit):
        _parse_args(["--model-dir", "generator", "--device", "cuda"])
