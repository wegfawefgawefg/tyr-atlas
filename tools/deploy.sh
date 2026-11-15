#!/bin/sh
# Publish site/ to Cloudflare Pages (project tyr-atlas -> https://tyr-atlas.pages.dev/).
# Needs a wrangler login on this machine (npx wrangler login). Copies site/ to a staging folder without the dev README,
# adds cache headers, and uploads it as a production deploy.
set -eu
cd "$(dirname "$0")/.."
STAGE=$(mktemp -d /tmp/tyr-deploy.XXXXXX)
trap 'rm -r "$STAGE"' EXIT
cp -r site/. "$STAGE"/
rm -f "$STAGE/README.md"
cat > "$STAGE/_headers" <<'EOF'
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
/art/*
  Cache-Control: public, max-age=86400
/maps/*
  Cache-Control: public, max-age=86400
/img/*
  Cache-Control: public, max-age=604800
EOF
npx -y wrangler pages deploy "$STAGE" --project-name tyr-atlas --branch main --commit-dirty=true
