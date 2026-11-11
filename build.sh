#!/usr/bin/env bash
# Render build: install, collect static files, migrate, seed (seed is idempotent).
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py seed
