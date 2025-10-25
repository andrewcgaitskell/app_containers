FROM dbeaver/cloudbeaver:latest

# Keep image minimal — reuse official CloudBeaver image.
WORKDIR /opt/cloudbeaver

# Expose CloudBeaver default port (the upstream image serves on 8978)
EXPOSE 8978

# Declare the workspace dir as a volume so data can be persisted by a bind-mount
VOLUME ["/opt/cloudbeaver/work"]
