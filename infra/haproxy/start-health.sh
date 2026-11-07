#!/bin/bash
set -euo pipefail
: "${CREDENTIALS_DIRECTORY:?systemd credentials directory is missing}"
set -a
. "${CREDENTIALS_DIRECTORY}/backend-env"
set +a
: "${SPACECUBE_BACKEND_DIR:?set backend directory in health-deploy.conf}"
: "${SPACECUBE_VENV_DIR:?set venv directory in health-deploy.conf}"
test -f "${SPACECUBE_BACKEND_DIR}/app/__init__.py"
test -x "${SPACECUBE_VENV_DIR}/bin/uvicorn"
export PYTHONPATH="${SPACECUBE_BACKEND_DIR}"
exec "${SPACECUBE_VENV_DIR}/bin/uvicorn" health_app:app --app-dir /opt/spacecube/deploy/health --host 127.0.0.1 --port 8001 --workers 1 --timeout-keep-alive 1 --no-access-log
