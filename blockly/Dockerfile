FROM python:3.11-slim

WORKDIR /app

# Install required OS packages
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Get Blockly static files
RUN git clone --depth 1 https://github.com/google/blockly.git /blockly

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Quart application
COPY main.py ./

# Copy custom index.html to override Blockly demo page
COPY index.html /blockly/demos/code/index.html

COPY favicon.ico /app/favicon.ico

# Optionally: Show debug info
RUN ls -lh /app && head -10 /app/main.py && ls -lh /blockly/demos/code

EXPOSE 5001

CMD ["python", "main.py"]
