FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download latest Blockly bundle (includes Python generator)
RUN mkdir -p /app/static/blockly \
    && curl -L -o /app/static/blockly/blockly_compressed.js https://unpkg.com/blockly@12.3.1/blockly_compressed.js \
    && curl -L -o /app/static/blockly/blocks_compressed.js https://unpkg.com/blockly@12.3.1/blocks_compressed.js \
    && curl -L -o /app/static/blockly/msg_en.js https://unpkg.com/blockly@12.3.1/msg/en.js \
    && curl -L -o /app/static/blockly/python_compressed.js https://unpkg.com/blockly@12.3.1/python_compressed.js

# Copy Python requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and static assets
COPY main.py ./
COPY index.html ./
COPY favicon.ico ./

# Expose port
EXPOSE 5001

CMD ["python", "main.py"]
