# Deployment Guide (MobaXterm + Nginx) — NeoFi MikroTik Hotspot Manager

This guide covers full deployment from zero to production-style setup:
- Linux backend (`uvicorn` as systemd service)
- Nginx reverse proxy
- MikroTik hotspot portal file (`login.html`)
- Required walled-garden rules

## 1) Requirements

- Linux server (Ubuntu 22.04/24.04 recommended)
- MikroTik RouterOS v7 with Hotspot enabled
- Windows PC with MobaXterm (SSH + SFTP)
- Domain name (recommended for HTTPS), or server IP

## 2) Connect to Linux via MobaXterm

1. Open **MobaXterm**
2. Click **Session** > **SSH**
3. **Remote host**: `SERVER_IP`
4. **Username**: `root` or a sudo user
5. **Port**: `22`
6. Connect

When connected, use the left SFTP panel for drag-and-drop file upload.

## 3) Prepare Server Packages

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install python3 python3-venv python3-pip git ufw nginx
```

Create app directory:

```bash
sudo mkdir -p /opt/neofi
sudo chown -R $USER:$USER /opt/neofi
```

## 4) Upload Project Using MobaXterm SFTP

- In SFTP panel, go to `/opt/neofi/`
- Drag and drop your `neofi_mikrotik_base` folder

Expected paths:
- `/opt/neofi/neofi_mikrotik_base/backend`
- `/opt/neofi/neofi_mikrotik_base/mikrotik_hotspot/login.html`

## 5) Create Python Environment and Install

```bash
cd /opt/neofi/neofi_mikrotik_base/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6) Configure Environment Variables

```bash
sudo mkdir -p /etc/neofi
sudo nano /etc/neofi/neofi.env
```

Put your values:

```bash
DATABASE_URL=sqlite:///./data/app.db
SESSION_SECRET=change-this-to-long-random-secret
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-password

# Optional: MikroTik REST auto-provision
MIKROTIK_BASE_URL=https://MIKROTIK_IP
MIKROTIK_USERNAME=admin
MIKROTIK_PASSWORD=yourpass
MIKROTIK_VERIFY_TLS=false
```

## 7) Test Backend Once (Before Service)

```bash
cd /opt/neofi/neofi_mikrotik_base/backend
source .venv/bin/activate
export $(grep -v '^#' /etc/neofi/neofi.env | xargs)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Test:
- `http://SERVER_IP:8000/api/health` (temporary direct test)

Stop with `CTRL+C`.

## 8) Create systemd Service

```bash
sudo nano /etc/systemd/system/neofi.service
```

Paste:

```ini
[Unit]
Description=NeoFi MikroTik Hotspot Manager
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/neofi/neofi_mikrotik_base/backend
EnvironmentFile=/etc/neofi/neofi.env
ExecStart=/opt/neofi/neofi_mikrotik_base/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Enable/start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable neofi
sudo systemctl start neofi
sudo systemctl status neofi --no-pager
```

Live logs:

```bash
sudo journalctl -u neofi -f
```

## 9) Configure Nginx Reverse Proxy

Create Nginx site:

```bash
sudo nano /etc/nginx/sites-available/neofi
```

If using domain (recommended), use this:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

If using IP only, replace `server_name` with your server IP.

### Optional: Domain + www + Forced HTTPS + Rate Limit for `/api/portal/claim`

Use this block if you want:
- `your-domain.com` and `www.your-domain.com`
- forced redirect from `http://` to `https://`
- basic rate limiting for `/api/portal/claim` to reduce spam/poll abuse

Replace `your-domain.com` with your real domain.

```nginx
limit_req_zone $binary_remote_addr zone=portal_claim:10m rate=10r/m;

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://your-domain.com$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    location = /api/portal/claim {
        limit_req zone=portal_claim burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Notes:
- The `listen 443 ssl` server needs certificates. Use the Certbot step below.
- If you want stricter/looser rate limit, adjust `rate=10r/m` and `burst=5`.

Enable config and test:

```bash
sudo ln -s /etc/nginx/sites-available/neofi /etc/nginx/sites-enabled/neofi
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

Now test:
- `http://your-domain.com/api/health` or `http://SERVER_IP/api/health`

## 10) Optional HTTPS (Certbot)

If you have a domain pointed to server IP:

```bash
sudo apt -y install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

Then test:
- `https://your-domain.com/api/health`

## 11) Firewall (UFW) with Nginx

With Nginx, open only SSH + web ports:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

Note: You no longer need to expose port `8000` publicly when Nginx is used.

## 12) Update Portal `API_BASE`

Edit:
`/opt/neofi/neofi_mikrotik_base/mikrotik_hotspot/login.html`

Find:

```js
var API_BASE = "http://YOUR-LINUX-SERVER:8000";
```

Change to:
- `https://your-domain.com` (recommended)
- or `http://SERVER_IP`

## 13) Upload Portal to MikroTik Hotspot Folder

- In MikroTik **Files**, upload `login.html` into `hotspot/`
- Ensure hotspot profile uses:
  - `html-directory=hotspot`

## 14) MikroTik Walled Garden Rules

Add allow rules so captive users can reach your API:

- If domain + HTTPS:
  - dst-host = `your-domain.com`
  - protocol = `tcp`
  - dst-port = `443`
- If IP + HTTP:
  - dst-host = `SERVER_IP`
  - protocol = `tcp`
  - dst-port = `80`

## 15) Client Flow (Insert Coin)

1. Client connects to hotspot
2. MikroTik shows `login.html`
3. Client clicks **Start Insert Coin**
4. Portal polls backend `POST /api/portal/claim` using `$(mac)` and `$(server-name)`
5. When credit is available, portal auto-logins the client

## 16) Troubleshooting

- Nginx failed config:
  - `sudo nginx -t`
- Nginx logs:
  - `sudo tail -f /var/log/nginx/error.log`
- Backend service logs:
  - `sudo journalctl -u neofi -f`
- Portal cannot reach API:
  - verify `API_BASE`
  - verify MikroTik walled-garden rules
  - verify DNS/domain resolution

