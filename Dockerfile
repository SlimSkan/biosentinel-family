# BioSentinel Family - web app image (FastAPI + static web pages).
# Built in Azure by `az acr build` (see deploy/deploy.sh), so Docker is not needed locally.
FROM python:3.12-slim

# No .pyc files, logs straight to the console (Container Apps collects them).
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

# Install dependencies first: this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data
COPY web ./web

# Run as an unprivileged user, not root.
RUN useradd --create-home bsf
USER bsf

EXPOSE 8000
# One worker on purpose: match sessions, invites and cases live in this process's memory.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
