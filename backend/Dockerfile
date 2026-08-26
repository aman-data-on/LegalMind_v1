# LegalMind backend — locked Step 39 (stack) and 55.1 (deployment shape).
#
# ONE image serves the API and the workers. Locked 55.1: "Workers run the same
# application image as the API; a Review's analysis is a job, not a separate service",
# and locked 55.5 explains why it matters — "API and workers deploy together because
# they share the evaluator; a version skew between them would break
# `evaluator_version` reproducibility" (45B.10 / AM-19).
#
# Locked 55.6 records the hosting platform and container orchestration as NOT YET
# SPECIFIED, so this builds an image and chooses nothing about where it runs.

FROM python:3.12-slim AS base

# Locked Step 39's document toolchain: PyMuPDF and python-docx are Python wheels;
# OCRmyPDF + Tesseract are system packages. Locked 34.8 labels OCR-derived text as
# `source_type = OCR`, so the toolchain must actually be present for that path to
# exist rather than fail closed (34.4, 34.9).
#
# `apt-get upgrade` first: the base tag floats behind Debian's security releases,
# and CI job 14's first real scan (2026-08-26) found the image shipping libssl
# 3.5.6 with 3.5.7 already published (CVE-2026-14456, HIGH). Upgrading at build
# time picks up whatever the security repo has fixed by then; the scan blocks if
# a fixed package is still missing, so the gate stays honest rather than waiting
# on the upstream tag to be rebuilt.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        ocrmypdf \
        ghostscript \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY legalmind ./legalmind
COPY alembic ./alembic
COPY alembic.ini ./

# 55.2 — the application role holds no DDL rights and migrations run under a separate
# role, so the container does not migrate on start. Nothing here runs as root either.
RUN useradd --create-home --uid 10001 legalmind
USER legalmind

# 53.1 — structured logs to stdout; the platform collects them. Locked 53.6 records
# log aggregation technology as NOT YET SPECIFIED.
ENV LEGALMIND_LOG_LEVEL=INFO

# Liveness only, and deliberately contentless — a probe must not become a
# reconnaissance endpoint (see the /health docstring).
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

EXPOSE 8000

# The API. A worker runs the same image with a different command, once the queue is
# wired — see backend/README.md on why analysis is currently synchronous.
CMD ["python", "-m", "uvicorn", "legalmind.api.app:app", \
     "--host", "0.0.0.0", "--port", "8000"]
