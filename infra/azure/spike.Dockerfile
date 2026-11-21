FROM python:3.14.10-alpine@sha256:a18b20ad69e74df6cf6d2e1b1a260d7a1ecf5380fd83b310f83ba88c461cf894

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# The runtime set, not the development one (audit M-9). The spike only ever
# serves /health, so the test client, the CLIs and their dependencies were
# attack surface it had no use for -- and the two pinned upgrades below
# existed solely to patch vulnerabilities in packages that came with that
# wider set. Install less, and there is nothing to patch.
COPY backend/requirements-runtime.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m pip check \
    && adduser -D -u 10001 appuser
COPY --chown=10001:10001 backend/main.py /app/backend/main.py
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
