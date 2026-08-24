#!/bin/sh
set -eu

rm -f "${BOT_READINESS_FILE:-/tmp/cafe-collection-bot.ready}"
exec python -m cafe_collection
