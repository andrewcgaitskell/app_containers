FROM python:3.11-slim

# Install required packages
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Get Blockly static files
RUN git clone --depth 1 https://github.com/google/blockly.git /blockly

# Install Quart
RUN pip install quart

# Create app directory
WORKDIR /app

# Copy backend
COPY backend.py /app/backend.py

# Copy custom index.html to override Blockly demo page
COPY index.html /blockly/demos/code/index.html

# Expose port
EXPOSE 5000

CMD ["quart", "run", "--host=0.0.0.0", "--port=5000", "--app=backend:app"]
