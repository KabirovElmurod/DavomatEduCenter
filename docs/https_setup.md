# HTTPS Setup - Domen yoki Cloudflared Tunnel

## Maqsad

Telegram Login Widget uchun HTTPS kerak. BotFather'dan `/setdomain` buyrug'i bilan domen o'rnatish shart.

## Variant 1: Cloudflared Tunnel (Sodda va Bepul)

### 1. Cloudflared'ni o'rnatish

**Windows:**
```bash
# Chocolatey
choco install cloudflared

# Yoki qo'lda yuklab olish
# https://github.com/cloudflare/cloudflared/releases
```

**Linux:**
```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

### 2. Tunnel yaratish

```bash
cloudflared tunnel login
# Brauzer ochiladi, Cloudflare account'ingizga login qiling

cloudflared tunnel create education-center
# Tunnel ID olinadi: <tunnel-id>
```

### 3. Config fayl yaratish

`cloudflared.yml`:
```yaml
tunnel: <tunnel-id>
credentials-file: ~/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

### 4. Tunnel'ni ishga tushirish

```bash
cloudflared tunnel --config cloudflared.yml run
```

### 5. DNS yozish

```bash
cloudflared tunnel route dns <tunnel-id> yourdomain.com
```

### 6. .env'ni yangilash

```env
PUBLIC_URL=https://yourdomain.com
```

## Variant 2: Domen + Caddy (Odatiy)

### 1. Domen olish

- Namecheap, GoDaddy, yoki boshqa provayder
- DNS A record: `yourdomain.com` -> VPS IP

### 2. Caddy o'rnatish

**Ubuntu:**
```bash
sudo apt install caddy
```

### 3. Caddyfile yaratish

`/etc/caddy/Caddyfile`:
```
yourdomain.com {
    reverse_proxy localhost:8000
}
```

### 4. Caddy'ni restart qilish

```bash
sudo systemctl restart caddy
```

Caddy avtomatik SSL (Let's Encrypt) o'rnatadi.

### 5. .env'ni yangilash

```env
PUBLIC_URL=https://yourdomain.com
```

## Variant 3: Nginx + Certbot (Murakkabroq)

### 1. Nginx o'rnatish

```bash
sudo apt install nginx
```

### 2. Nginx config

`/etc/nginx/sites-available/education-center`:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. Certbot o'rnatish

```bash
sudo apt install certbot python3-certbot-nginx
```

### 4. SSL olish

```bash
sudo certbot --nginx -d yourdomain.com
```

### 5. Nginx config (HTTPS)

Certbot avtomatik config'ni yangilaydi.

### 6. .env'ni yangilash

```env
PUBLIC_URL=https://yourdomain.com
```

## BotFather /setdomain

HTTPS o'rnatgandan keyin:

```
/setdomain
BotFather: Choose a bot to change domain settings.
Siz: @education_center_bot
BotFather: OK. Send me a domain name for your bot. Note that this can't be changed later.
Siz: yourdomain.com
BotFather: Success! Domain saved.
```

## Docker Compose'ga HTTPS tunnel

Agar Docker container ichida cloudflared ishlatmoqchi bo'lsangiz:

`docker-compose.yml` ga qo'shing:
```yaml
  tunnel:
    image: cloudflare/cloudflared:latest
    container_name: education_tunnel
    command: tunnel run
    environment:
      TUNNEL_TOKEN: <your-tunnel-token>
    restart: unless-stopped
```

## Test

```bash
curl https://yourdomain.com/health
# {"status":"healthy","database":"ok","redis":"ok"}
```

## Xavfsizlik

- HTTPS har doim SSL bilan bo'lishi kerak
- Bot webhook secret o'rnatish (BOT_WEBHOOK_SECRET)
- JWT_SECRET va SESSION_SECRET kuchli bo'lishi kerak
- .env faylni git'ga qo'shmang

## Local Development uchun

Local development uchun cloudflared ishlatsa bo'ladi:

```bash
cloudflared tunnel --url http://localhost:8000
# https://xxxx.trycloudflare.com -> localhost:8000
```

Bu HTTPS URL temporary bo'ladi, test uchun yaxshi.
