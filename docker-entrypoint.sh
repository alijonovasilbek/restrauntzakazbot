#!/bin/sh
set -e

export PYTHONPATH=/app

alembic upgrade head
exec python -m bot.main
