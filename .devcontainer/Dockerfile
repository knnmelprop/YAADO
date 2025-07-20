FROM python:3.9-slim

# Set environment variables for better Codespaces compatibility
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies including Git LFS
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    git-lfs \
    wget \
    curl \
    ca-certificates \
    gfortran \
    liblapack-dev \
    libopenblas-dev \
    sudo \
    vim \
    tree \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create rsvscode user (to match .devcontainer.json)
RUN groupadd --gid 1000 rsvscode \
    && useradd --uid 1000 --gid rsvscode --shell /bin/bash --create-home rsvscode \
    && echo "rsvscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/rsvscode \
    && chmod 0440 /etc/sudoers.d/rsvscode

# Switch to rsvscode user
USER rsvscode
WORKDIR /home/rsvscode

# Create symbolic links to ensure python/python3 commands use Python 3.9
RUN sudo ln -sf /usr/local/bin/python3.9 /usr/local/bin/python \
    && sudo ln -sf /usr/local/bin/python3.9 /usr/local/bin/python3

# Upgrade pip and install build tools
RUN python -m pip install --upgrade pip setuptools wheel

# Set Python path for user installations
ENV PATH="/home/rsvscode/.local/bin:${PATH}"

# Pre-install core scientific packages (community-verified versions for SUAVE 2.5.2)
RUN pip install --user \
    numpy>=1.21.6,<1.25.0 \
    scipy>=1.7.3,<1.11.0 \
    matplotlib>=3.5.0,<3.8.0

# Copy and install requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip install --user -r /tmp/requirements.txt

# Set up workspace
WORKDIR /workspaces
