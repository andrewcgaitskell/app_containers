FROM python:3.11-slim

# Install required packages
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Get Blockly static files
RUN git clone --depth 1 https://github.com/google/blockly.git /blockly

# Install latest Quart and asyncio-mqtt
RUN pip install --no-cache-dir 'quart>=0.19' asyncio-mqtt

# Debug: check Quart CLI and version
RUN which quart && quart --version

# Debug: list installed Python packages
RUN pip list

# Create app directory
WORKDIR /app

# Copy backend
COPY backend.py /app/backend.py

# Copy custom index.html to override Blockly demo page
COPY index.html /blockly/demos/code/index.html

# Debug: show backend.py exists and print first 10 lines
RUN ls -lh /app && head -10 /app/backend.py

# Debug: show directory structure for blockly
RUN ls -lhR /blockly/demos/code

# Expose port
EXPOSE 5001

CMD ["quart", "run", "--host=0.0.0.0", "--port=5001", "--app=backend:app"]

