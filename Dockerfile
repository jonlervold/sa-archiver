FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install -r requirements.txt

# Note: gallery-dl is no longer needed as we use a custom image extractor for SA forums

# Copy the application files
COPY app.py .
COPY archive_sa_thread.py .
COPY sa_thread_parser.py .
COPY json_to_html.py .
COPY templates/ ./templates/

# Create output directory
RUN mkdir -p /app/output

# Expose port
EXPOSE 5000

# Set the entrypoint to run the Flask app
CMD ["python3", "app.py"] 