#!/bin/sh
# Publish site/ to Cloudflare (Workers static assets, worker "tyr-atlas"; config in wrangler.jsonc).
# Needs a wrangler login on this machine (npx wrangler login). site/.assetsignore keeps the dev README off the web;
# site/_headers sets cache headers.
set -eu
cd "$(dirname "$0")/.."
npx -y wrangler deploy
