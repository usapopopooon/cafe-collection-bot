"""Verify secret scope and that bot startup preserves the image's venv PATH."""

import json
import os
import subprocess
from pathlib import Path

project_directory = Path(__file__).resolve().parents[1]
for compose_file in ("docker-compose.yml", "docker-compose.coolify.yml"):
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            compose_file,
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
        f"LEVEL_BOT_API_TOKEN leaked into api in {compose_file}"
    )
    assert services["bot"]["command"][:2] == ["sh", "-c"], (
        f"login shell would discard the image's venv PATH in {compose_file}"
    )
