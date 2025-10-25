FROM docker.io/jupyter/base-notebook:latest

# Switch to root so we can change ownership
USER root

# Ensure workdir exists and make the jovyan home + workdir owned by root
# NOTE: changing ownership of the jovyan home to root will make the notebook
# process run as root (see USER below). This is intentional per your request.
RUN mkdir -p /home/jovyan/work \
 && chown -R root:root /home/jovyan \
 && chown -R root:root /home/jovyan/work

# Keep working directory as requested
WORKDIR /home/jovyan/work

ENV JUPYTER_ENABLE_LAB=yes
EXPOSE 8888

# Run the container processes as root (jupyter will start as root)
USER root

# Start Jupyter Lab (adjust command/flags in compose if you prefer a token)
CMD ["start.sh", "jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser"]
