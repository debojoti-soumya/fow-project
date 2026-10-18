#!/usr/bin/env bash
set -euo pipefail
rm -rf dist
mkdir -p dist/server
cp site/worker.js dist/server/index.js
cp -R site/migrations dist/drizzle
