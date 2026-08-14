#!/bin/sh
set -e

# Aplica las migraciones (idempotentes) antes de levantar el servidor.
flask db upgrade

exec gunicorn --config gunicorn-cfg.py run:app
