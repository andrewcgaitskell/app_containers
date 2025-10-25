FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Minimal runtime + jupyterlab
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates build-essential \
 && pip install --no-cache-dir jupyterlab \
 && apt-get purge -y --auto-remove build-essential \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Keep workdir outside any user home and match the host bind-mount /opt/data
RUN mkdir -p /opt/data
WORKDIR /opt/data

EXPOSE 8888

# Run as root per your preference so bind-mounted /opt/data is writable by default
USER root

# Start Jupyter Lab with a simple token (change/remove token as needed)
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--NotebookApp.token=my-token" "--allow-root"]
