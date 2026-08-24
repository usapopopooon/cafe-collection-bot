#!/bin/sh
set -eu

exec uvicorn cafe_collection.health:app --host 0.0.0.0 --port 8000
