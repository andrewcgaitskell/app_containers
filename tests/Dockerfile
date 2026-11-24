# Test runner image for quart_app.
# Build context is quart_app/ (only requirements files are copied in).
# Tests and app code are mounted read-only at run time by tests/run-tests-docker.sh.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /work

COPY requirements.txt requirements-dev.txt /tmp/req/
RUN pip install -r /tmp/req/requirements-dev.txt && rm -rf /tmp/req

ENTRYPOINT ["python", "-m", "pytest", "-p", "no:cacheprovider", "-v", "-rA"]
