# Dockerfile for GenePhenExtract Nextflow pipeline

FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app/

# Install GenePhenExtract
RUN pip install --no-cache-dir -e ".[all-llms]"

# Install additional dependencies for pipeline
RUN pip install --no-cache-dir \
    pandas \
    matplotlib \
    seaborn

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "--version"]
