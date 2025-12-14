# Deploying jamovi Server on LXC / VPS (Proxmox)

This guide walks through deploying jamovi Server inside an LXC container (Proxmox) or a generic VPS and exposing it behind an Nginx reverse proxy. It explains how to preserve and forward proxy headers (`X-Forwarded-Host`, `X-Forwarded-Proto`, `X-Forwarded-Prefix`) so the server can generate correct public-facing URLs and CSP.

Prerequisites
- A VPS or Proxmox host with networking configured.
- An LXC container (Debian/Ubuntu recommended) or a VPS with a user that can install packages.
- Docker (optional) or Python/Poetry/Node toolchains if running without Docker.
- Nginx (as reverse proxy) or Traefik; examples below use Nginx.

This guide assumes you already have the repository checked out on the target machine or built into a Docker image.

Quick summary
- Build/run jamovi in the container (prefer Docker Compose for repeatability), or run the Python server directly.
- Configure Nginx to reverse-proxy public host and forward `X-Forwarded-*` headers.
- Ensure `JAMOVI_LISTEN_PORT` is set if you want a stable internal listening port.
- Verify operation by visiting `https://your-public-host/jamovi/` (or root path).

Table of contents
- Using Docker (recommended)
- Running jamovi Server directly (Poetry / Python)
- Nginx configuration (subpath and TLS)
- Health checks and verification
- Troubleshooting

---

## 1) Using Docker (recommended)

If you prefer Docker, this is the most repeatable route.

1. Build the image locally or pull a pre-built jamovi image (if available):

```bash
# Build (if a Dockerfile exists / you have docker context)
# From the repo root
docker-compose build

# Run
docker-compose up -d
```

2. If you want jamovi to listen on a fixed internal port, set an environment variable in the container or docker-compose override:

```yaml
# docker-compose.override.yml
services:
  jamovi:
    environment:
      - JAMOVI_LISTEN_PORT=41337
    ports:
      - "127.0.0.1:41337:41337"
```

Note: Binding to `127.0.0.1` inside container may not be needed; in LXC it's common to expose container ports to host using bridge networking.

## 2) Running jamovi Server directly (Poetry / Python)

If you want to run without Docker (e.g. install Python + dependencies directly in LXC):

1. Install system deps (Ubuntu/Debian example):

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip build-essential nodejs npm nginx git
```

2. Clone the repo and install Python dependencies (Poetry):

```bash
git clone https://github.com/jamovi/jamovi.git
cd jamovi
poetry install
poetry shell
```

3. Optionally set `JAMOVI_LISTEN_PORT` to a fixed port (recommended):

```bash
export JAMOVI_LISTEN_PORT=41337
```

4. Run the server (example runs in foreground):

```bash
python3 -m server.jamovi.server.__main__ 0
```

This will start jamovi and print the ports it opened. If you set `JAMOVI_LISTEN_PORT`, the server will use that port.

## 3) Nginx reverse proxy configuration

Below are two example configurations: (A) Subpath (https://example.com/jamovi/) and (B) Root domain (https://jamovi.example.com/).

Important headers to forward:
- `X-Forwarded-Host`
- `X-Forwarded-Proto`
- `X-Forwarded-Prefix`

A) Subpath (https://example.com/jamovi/):

```nginx
server {
    listen 80;
    server_name example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    location /jamovi/ {
        proxy_pass http://127.0.0.1:41337/; # internal jamovi server
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host:$server_port;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Prefix /jamovi;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

B) Dedicated subdomain (https://jamovi.example.com/):

```nginx
server {
    listen 443 ssl;
    server_name jamovi.example.com;

    ssl_certificate /etc/letsencrypt/live/jamovi.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/jamovi.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:41337/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host:$server_port;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Prefix "";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

Notes:
- `proxy_set_header X-Forwarded-Host $host:$server_port;` will provide host:port to the server (matching how the server constructs `roots`). If you terminate TLS at the proxy, forwarding `X-Forwarded-Proto` lets jamovi include `https://...` in returned roots/CSP.
- When using subpath, `X-Forwarded-Prefix` tells jamovi to prepend `/jamovi` into paths returned in `config.js` so the client requests resources from the right subpath.

## 4) Health checks and verification

1. After proxy setup, visit: `https://example.com/jamovi/` (or `https://jamovi.example.com/`)
2. Check `config.js` from the browser (Developer Tools -> Network -> `config.js`) and verify `window.config` contains `roots` that point to `https://example.com:443/jamovi` (or `jamovi.example.com`).
3. Verify in browser console there are no CSP or History API errors.
4. If resources 404, check that the client `roots` are correct and that Nginx forwards `X-Forwarded-Prefix`.
5. To inspect headers forwarded by Nginx, you can temporarily add a debug location:

```nginx
location /_jamovi_debug_headers {
    default_type text/plain;
    return 200 "$http_x_forwarded_host|$http_x_forwarded_proto|$http_x_forwarded_prefix";
}
```

## 5) Troubleshooting

- 403 / CSP errors: ensure `X-Forwarded-Host` and `X-Forwarded-Proto` are forwarded, and that jamovi's `config.js` roots show public host with scheme.
- WebSocket fails to upgrade: ensure `proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";` and use `proxy_http_version 1.1`.
- Random port changes: set `JAMOVI_LISTEN_PORT` in env to keep internal port stable.
- If you're running jamovi in Docker inside LXC, expose container port to host and point Nginx to container host:port.

---

If you'd like, I can also generate an example `systemd` unit file to run jamovi server as a service in the container and a `docker-compose` example that sets `JAMOVI_LISTEN_PORT` and exposes the port only to `127.0.0.1` on the LXC host.

Tell me if you want `systemd` and `docker-compose` examples added to this document and I will update `docs/DEPLOY_LXC_PROXMOX.md` accordingly.
