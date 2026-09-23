# Stage 1: scaffold and build the Blockly app (Blockly needs Node >= 22)
FROM node:22-alpine AS build
WORKDIR /work
RUN npx --yes @blockly/create-package app blockly-app --typescript
WORKDIR /work/blockly-app
RUN npm run build

# Stage 2: serve the built files with nginx
FROM nginx:alpine

# Keep a copy of the build outside the web root (a volume will cover the web root)
COPY --from=build /work/blockly-app/dist /opt/blockly-app-default

# nginx runs executable .sh files in this folder every time the container starts
COPY --chmod=755 seed-blockly-app.sh /docker-entrypoint.d/40-seed-blockly-app.sh

