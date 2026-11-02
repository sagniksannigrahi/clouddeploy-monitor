#!/usr/bin/env bash
#
# deploy.sh - runs ON THE EC2 SERVER, from the folder that holds the app code.
#
# 1. Builds a new Docker image (the old container keeps serving meanwhile).
# 2. Replaces the running container with one from the new image.
# 3. Checks /health. If the new version is unhealthy, the previous one is restored.
#
# Usage:  ./deploy.sh [git-commit] [git-branch] [deployed-by]
# Called by GitHub Actions; can also be run by hand on the server.

set -euo pipefail

COMMIT="${1:-manual}"
BRANCH="${2:-main}"
DEPLOYED_BY="${3:-Manual}"

IMAGE="clouddeploy-monitor"
CONTAINER="clouddeploy-monitor"
HOST_PORT="${HOST_PORT:-80}"   # public port on the server (open in the security group)
APP_PORT=8080                 # port Gunicorn listens on inside the container (not public)
TAG="${COMMIT:0:12}"

log() { echo "[deploy] $*"; }

# ---------- Cloud details from the EC2 instance metadata service ----------
# Only non-sensitive values are read (no instance ID, IPs or credentials).
IMDS="http://169.254.169.254/latest"
TOKEN=$(curl -sf -X PUT "$IMDS/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" --max-time 2 || true)
metadata() {
  curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" --max-time 2 "$IMDS/meta-data/$1" || echo "unknown"
}
REGION=$(metadata placement/region)
ZONE=$(metadata placement/availability-zone)
INSTANCE_TYPE=$(metadata instance-type)
# shellcheck source=/dev/null
HOST_OS=$( (. /etc/os-release && echo "$PRETTY_NAME") 2>/dev/null || uname -s)

# ---------- 1. Build the new image ----------
log "Building image $IMAGE:$TAG (commit $COMMIT, branch $BRANCH)"
docker build \
  --build-arg GIT_COMMIT="$COMMIT" \
  --build-arg GIT_BRANCH="$BRANCH" \
  --build-arg BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t "$IMAGE:$TAG" .
NEW_IMAGE=$(docker image inspect --format '{{.Id}}' "$IMAGE:$TAG")

# Remember what is running now, so we can roll back to it.
PREVIOUS_IMAGE=$(docker inspect --format '{{.Image}}' "$CONTAINER" 2>/dev/null || true)

start_container() {
  docker run -d \
    --name "$CONTAINER" \
    --restart unless-stopped \
    -p "$HOST_PORT:$APP_PORT" \
    -e PORT="$APP_PORT" \
    -e CLOUD_PROVIDER="AWS EC2" \
    -e CLOUD_REGION="$REGION" \
    -e CLOUD_ZONE="$ZONE" \
    -e CLOUD_INSTANCE_TYPE="$INSTANCE_TYPE" \
    -e HOST_OS="$HOST_OS" \
    -e DEPLOYED_BY="$DEPLOYED_BY" \
    -e STATUS_PAGE_URL="${STATUS_PAGE_URL:-}" \
    --memory 300m \
    --log-opt max-size=10m --log-opt max-file=3 \
    "$1" >/dev/null
}

healthy() {
  for _ in $(seq 1 20); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$HOST_PORT/health" 2>/dev/null | grep -q '"healthy"'; then
      return 0
    fi
    sleep 2
  done
  return 1
}

# ---------- 2. Swap the containers ----------
log "Replacing the running container"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
start_container "$IMAGE:$TAG"

# ---------- 3. Verify, or roll back ----------
if healthy; then
  log "New version is healthy:"
  curl -fsS "http://127.0.0.1:$HOST_PORT/health"; echo
  docker tag "$IMAGE:$TAG" "$IMAGE:latest"   # "latest" = last version that passed
else
  log "New version FAILED its health check. Container logs:"
  docker logs --tail 50 "$CONTAINER" || true
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  docker rmi "$IMAGE:$TAG" >/dev/null 2>&1 || true   # discard the broken image
  if [ -n "$PREVIOUS_IMAGE" ]; then
    log "Rolling back to the previous version"
    start_container "$PREVIOUS_IMAGE"
    if healthy; then
      log "Previous version restored."
    else
      log "Previous version is not healthy either!"
    fi
  fi
  exit 1
fi

# ---------- Clean up old images to save disk space ----------
# Keep the new image and the previous one (for manual rollback); delete the rest.
for id in $(docker images "$IMAGE" --format '{{.ID}}' | sort -u); do
  full=$(docker image inspect --format '{{.Id}}' "$id")
  if [ "$full" != "$NEW_IMAGE" ] && [ "$full" != "$PREVIOUS_IMAGE" ]; then
    docker rmi -f "$id" >/dev/null 2>&1 || true
  fi
done
docker image prune -f >/dev/null
docker builder prune -f --filter "until=72h" >/dev/null 2>&1 || true

log "Done. Running containers:"
docker ps --filter "name=$CONTAINER" --format '  {{.Names}}  {{.Image}}  {{.Status}}  {{.Ports}}'
