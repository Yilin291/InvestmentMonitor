#!/bin/sh
set -eu
npm --prefix frontend ci
VITE_API_PREFIX=/sb-api/functions/v1/watchlist-api npm --prefix frontend run build
