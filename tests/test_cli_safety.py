import asyncio

import pytest

from backend.agents.swarm import ChallengeSwarm
from backend.cli import main


def test_cli_defaults_to_manual_flag_submission():
    submit_option = next(parameter for parameter in main.params if parameter.name == "submit")
    assert submit_option.default is False
    assert "--submit" in submit_option.opts
    assert "--no-submit" in submit_option.secondary_opts


@pytest.mark.asyncio
async def test_swarm_manual_mode_blocks_submission_before_platform_client():
    swarm = object.__new__(ChallengeSwarm)
    swarm.no_submit = True
    swarm._flag_lock = asyncio.Lock()

    message, confirmed = await swarm.try_submit_flag("CTF{candidate}", "google/test-model")

    assert message.startswith("DRY RUN")
    assert "upload it manually" in message
    assert confirmed is False
