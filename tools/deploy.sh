#!/bin/sh
# Publish site/ to Cloudflare Pages, project tyr-atlas -> https://tyr-atlas.pages.dev/
# Needs a wrangler login on this machine (npx wrangler login). Uploads a staging copy without the dev README;
# site/_headers sets cache headers. This is a classic Pages project: never use `wrangler deploy` here (that makes a
# Worker on the account's workers.dev subdomain, which shows the account email in the URL).
set -eu
cd "$(dirname "$0")/.."
STAGE=$(mktemp -d /tmp/tyr-deploy.XXXXXX)
trap 'rm -r "$STAGE"' EXIT
cp -r site/. "$STAGE"/
rm -f "$STAGE/README.md"
(cd /tmp && npx -y wrangler pages deploy "$STAGE" --project-name tyr-atlas --branch main --commit-dirty=true)
