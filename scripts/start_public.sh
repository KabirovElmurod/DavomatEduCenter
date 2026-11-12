#!/usr/bin/env bash
# start_public.sh — public URL (cloudflared quick tunnel) ni ishga tushirish
#
# Ishlatish:  bash scripts/start_public.sh
# Natija:     https://xxx.trycloudflare.com  -> http://localhost:8000
#
# Diqqat: quick tunnel URL har safar YANGI bo'ladi.
#   - .env dagi PUBLIC_URL avtomatik yangilanadi
#   - api konteyner qayta ishga tushadi (webhook ham yangilanadi)
#   - BotFather /setdomain ni yangi domain bilan yangilash kerak
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Docker servislari..."
docker compose up -d

echo "==> Cloudflared tunnel ishga tushmoqda..."
LOG=$(mktemp)
cloudflared tunnel --url http://localhost:8000 --no-autoupdate >"$LOG" 2>&1 &
TUNNEL_PID=$!
trap 'kill $TUNNEL_PID 2>/dev/null || true' EXIT

# trycloudflare URL'ni log'dan olish (max 30 soniya)
URL=""
for _ in $(seq 1 60); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)
  [ -n "$URL" ] && break
  sleep 0.5
done

if [ -z "$URL" ]; then
  echo "XATO: tunnel URL olinmadi. Log:" >&2
  tail -20 "$LOG" >&2
  exit 1
fi
echo "==> Tunnel: $URL"

# .env dagi PUBLIC_URL'ni yangilash
if grep -q '^PUBLIC_URL=' .env; then
  sed -i "s|^PUBLIC_URL=.*|PUBLIC_URL=$URL|" .env
else
  echo "PUBLIC_URL=$URL" >> .env
fi

echo "==> api konteyner yangi PUBLIC_URL bilan..."
docker compose up -d api

echo ""
echo "TAYYOR: $URL"
echo "Tekshirish: curl $URL/api/v1/health"
echo "BotFather /setdomain: $(echo "$URL" | sed 's|https://||')"
echo ""
echo "Tunnellni to'xtatish: kill $TUNNEL_PID"
echo "(yoki: taskkill //F //PID $TUNNEL_PID)"
wait $TUNNEL_PID
