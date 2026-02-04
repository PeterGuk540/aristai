#!/usr/bin/env bash
set -euo pipefail

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

docker compose down --remove-orphans
docker compose build --pull
docker compose up -d
docker compose ps
