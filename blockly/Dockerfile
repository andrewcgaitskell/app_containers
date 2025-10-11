FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install required packages
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Get Blockly static files
RUN git clone --depth 1 https://github.com/google/blockly.git /blockly

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Debug: check Quart version and CLI
RUN quart --version || echo "Quart CLI not found"
RUN pip show quart

# Copy application code
COPY main.py ./

# Copy custom index.html to override Blockly demo page
COPY index.html /blockly/demos/code/index.html

# Optional: Check that files are in place
RUN ls -lh /app && head -10 /app/main.py && ls -lh /blockly/demos/code

# Expose port
EXPOSE 5001

CMD ["python", "main.py"]
