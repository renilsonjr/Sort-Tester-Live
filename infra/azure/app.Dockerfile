# Production image: the whole app on one origin (issue #76).
# FastAPI serves /api and the frontend (index.html, src/, assets/).
# Build from the repository root:
#   docker build --file infra/azure/app.Dockerfile --tag sort-tester-live-app .
# The allowlist of copied files is infra/azure/app.Dockerfile.dockerignore.
FROM python:3.14.10-alpine@sha256:a18b20ad69e74df6cf6d2e1b1a260d7a1ecf5380fd83b310f83ba88c461cf894

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m pip install --no-cache-dir --upgrade 'setuptools==78.1.1' 'msgpack==1.2.3' \
    && python -m pip check \
    && rm /tmp/requirements.txt \
    && adduser -D -u 10001 appuser

# Files stay owned by root: the app user can read them but not change them.
COPY index.html /app/index.html
COPY src /app/src
COPY assets /app/assets
COPY backend /app/backend

USER 10001:10001
EXPOSE 8000
# Migrations are a separate, explicit step:
#   python -m backend.db.upgrade_app --confirm <database>
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-server-header"]
