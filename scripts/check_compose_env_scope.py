"""Verify that the level-bot write token reaches only the Discord bot."""

import json
import os
import subprocess
from pathlib import Path

project_directory = Path(__file__).resolve().parents[1]
result = subprocess.run(
    [
        "docker",
        "compose",
        "-f",
        "docker-compose.coolify.yml",
        "config",
        "--no-interpolate",
        "--format",
        "json",
    ],
    cwd=project_directory,
    env=os.environ,
    check=True,
    capture_output=True,
    text=True,
)
services = json.loads(result.stdout)["services"]
assert services["bot"]["environment"]["LEVEL_BOT_API_TOKEN"] == (
    "${LEVEL_BOT_API_TOKEN:-}"
)
assert services["api"]["environment"]["LEVEL_BOT_API_TOKEN"] is None, (
    "LEVEL_BOT_API_TOKEN leaked into api"
)
