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

# Only what the app imports (26 packages), not the development environment.
COPY backend/requirements-runtime.txt /tmp/requirements.txt
# pip is needed to install and then has no job in a running container, so it
# is removed: nothing can be installed into the image afterwards, and the
# copies of other libraries that pip bundles inside itself go with it. Python
# also keeps a spare pip wheel in ensurepip; that goes too.
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m pip check \
    && rm /tmp/requirements.txt \
    && python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.14/ensurepip \
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
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
