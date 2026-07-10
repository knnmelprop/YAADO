FROM mcr.microsoft.com/devcontainers/python:3.9

# Environment for non-interactive apt
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies needed for scientific stack and Git LFS
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git-lfs \
    gfortran \
    liblapack-dev \
    libopenblas-dev \
    tree \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

# Upgrade pip toolchain and install Python dependencies globally
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install -r /tmp/requirements.txt

# Set up workspace
WORKDIR /workspaces
