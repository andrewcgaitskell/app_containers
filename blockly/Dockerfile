FROM python:3.11-slim

WORKDIR /app

# Install required packages
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Get Blockly static files (for demos/assets)
RUN git clone --depth 1 https://github.com/google/blockly.git /blockly

# Download Blockly dist JS files for local serving
RUN mkdir -p /app/static/blockly \
    && curl -L -o /app/static/blockly/blockly_compressed.js https://unpkg.com/blockly@10.0.0/dist/blockly_compressed.js \
    && curl -L -o /app/static/blockly/blocks_compressed.js https://unpkg.com/blockly@10.0.0/dist/blocks_compressed.js \
    && curl -L -o /app/static/blockly/python_compressed.js https://unpkg.com/blockly@10.0.0/dist/python_compressed.js \
    && curl -L -o /app/static/blockly/msg_en.js https://unpkg.com/blockly@10.0.0/dist/msg/en.js

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Quart application and app files
COPY main.py ./
COPY index.html ./index.html
COPY favicon.ico ./favicon.ico

# Expose port
EXPOSE 5001

CMD ["python", "main.py"]
