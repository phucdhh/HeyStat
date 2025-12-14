# HeyStat Configuration Summary

## Project Information
- **Name:** HeyStat
- **Base:** Jamovi 2.7.6 (Fork)
- **Platform:** Mac Mini M2 (Apple Silicon)
- **License:** AGPL-3.0 (same as Jamovi)
- **Domain:** heystat.truyenthong.edu.vn

## Architecture Changes from Ubuntu

### 1. Docker Platform
- **Ubuntu:** `platform: linux/amd64`
- **Mac M2:** `platform: linux/arm64`

### 2. Ports (Avoid conflicts with HeyTeX/AIThink)
- **Container ports:** 42337-42339 (instead of 41337-41339)
- **Nginx port:** 8082 (instead of 80)

### 3. Container Naming
- **Ubuntu:** `container_name: jamovi`
- **Mac M2:** `container_name: heystat`

### 4. Domain Configuration
- **Ubuntu:** jamovi.truyenthong.edu.vn
- **Mac M2:** heystat.truyenthong.edu.vn

## Environment Variables

```yaml
JAMOVI_HOST_A: 'heystat.truyenthong.edu.vn:42337'
JAMOVI_HOST_B: 'heystat.truyenthong.edu.vn:42337/analyses'
JAMOVI_HOST_C: 'heystat.truyenthong.edu.vn:42337/results'
JAMOVI_ACCESS_KEY: ''  # Empty = auto-generate
JAMOVI_ALLOW_ARBITRARY_CODE: 'false'
```

## File Locations

### Configuration Files
- Docker Compose: `/Users/mac/HeyStat/docker-compose.yaml`
- Nginx Config: `/Users/mac/HeyStat/heystat-nginx-mac.conf`
- Cloudflare Config: `~/.cloudflared/config-heystat.yml`

### Service Files
- LaunchDaemon (Docker): `/Library/LaunchDaemons/com.heystat.docker.plist`
- LaunchDaemon (CF): `/Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist`

### Logs
- Docker logs: `/Users/mac/HeyStat/logs/heystat-docker*.log`
- Cloudflare logs: `/Users/mac/HeyStat/logs/cloudflared-heystat*.log`
- Nginx logs: `/opt/homebrew/var/log/nginx/heystat_*.log`

## Network Flow

```
Internet (HTTPS)
    ↓
Cloudflare Tunnel (cloudflared)
    ↓ localhost:8082
Nginx Reverse Proxy
    ↓ localhost:42337
Docker Container (HeyStat)
```

## Port Mapping

| Service | External Port | Internal Port | Protocol |
|---------|--------------|---------------|----------|
| Nginx   | 8082         | -             | HTTP     |
| HeyStat A | 42337      | 42337         | HTTP/WS  |
| HeyStat B | 42338      | 42338         | HTTP/WS  |
| HeyStat C | 42339      | 42339         | HTTP/WS  |

## Existing Ports on Mac Mini

**In Use (by other projects):**
- 3000: Node (HeyTeX/AIThink)
- 5173: Vite dev server
- 5432: PostgreSQL
- 5433-5437: Various services
- 8081: Nginx default
- 11434: Ollama

**Reserved for HeyStat:**
- 8082: Nginx (HeyStat proxy)
- 42337-42339: Docker containers

## Service Management

### Docker Service (com.heystat.docker.plist)
```bash
sudo launchctl load -w /Library/LaunchDaemons/com.heystat.docker.plist
sudo launchctl unload /Library/LaunchDaemons/com.heystat.docker.plist
```

### Cloudflare Tunnel (com.cloudflare.cloudflared.heystat.plist)
```bash
sudo launchctl load -w /Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist
sudo launchctl unload /Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist
```

### Nginx
```bash
brew services start nginx
brew services stop nginx
brew services restart nginx
```

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `quick-start.sh` | Interactive setup wizard | `./quick-start.sh` |
| `deploy-mac.sh` | Service management | `sudo ./deploy-mac.sh [command]` |
| `cloudflare-setup.sh` | Cloudflare tunnel setup | `./cloudflare-setup.sh [command]` |

## Security Notes

### Multi-Origin Architecture
HeyStat uses 3 origins for security (same as Jamovi):
- **Host A:** Main application
- **Host B:** Analysis UI (isolated)
- **Host C:** Results view (isolated)

This prevents XSS attacks between components.

### Access Control
- **Development:** `JAMOVI_ACCESS_KEY: ''` (auto-generate)
- **Production:** Set a strong key in docker-compose.yaml
- **Disable (dev only):** `JAMOVI_DISABLE_ACCESS_KEY: '1'`

### Code Execution
- `JAMOVI_ALLOW_ARBITRARY_CODE: 'false'` (blocks Rj editor)
- Enable only if you understand the security implications

## Nginx Headers (Critical for Security)

```nginx
proxy_set_header Host heystat.truyenthong.edu.vn:42337;
proxy_set_header X-Forwarded-Proto https;
proxy_set_header X-Forwarded-Host heystat.truyenthong.edu.vn;  # NO PORT!
```

These headers ensure:
1. Server returns correct origin URLs
2. HTTPS URLs are generated (not HTTP)
3. No port in X-Forwarded-Host (avoids same-origin violations)

## Cloudflare Tunnel Configuration

```yaml
tunnel: [tunnel-id]
credentials-file: ~/.cloudflared/[tunnel-id].json

ingress:
  - hostname: heystat.truyenthong.edu.vn
    service: http://localhost:8082
    originRequest:
      httpHostHeader: heystat.truyenthong.edu.vn:42337  # Must match JAMOVI_HOST_A
      connectTimeout: 60s
      disableChunkedEncoding: true  # For WebSocket
  - service: http_status:404
```

## Testing Checklist

- [ ] Docker containers running: `docker ps | grep heystat`
- [ ] Nginx listening on 8082: `lsof -iTCP:8082 -sTCP:LISTEN`
- [ ] Local access works: `curl -I http://localhost:8082`
- [ ] WebSocket upgrade: Check for "101 Switching Protocols"
- [ ] Cloudflare tunnel running: `./cloudflare-setup.sh status`
- [ ] Public access works: `curl -I https://heystat.truyenthong.edu.vn`
- [ ] No CORS errors in browser console
- [ ] Analysis UI loads in separate origin
- [ ] Results view loads in separate origin

## Common Issues

### Double Protocol Bug (`https://https://`)
- **Cause:** Incorrect URL construction in client code
- **Fixed:** Modified `resolveUrl()` in client/main/host.ts

### Same-Origin Policy Violations
- **Cause:** Port in X-Forwarded-Host header
- **Fixed:** Removed port from X-Forwarded-Host in nginx config

### WebSocket Connection Failed
- **Cause:** Buffering or timeout issues
- **Fixed:** Added WebSocket headers and disabled buffering in nginx

### Port Already in Use
- **Solution:** Check `lsof -iTCP:[port]` and stop conflicting service
- **Alternative:** Change ports in docker-compose.yaml and nginx config

## Backup and Recovery

### Backup Important Files
```bash
tar -czf heystat-config-backup.tar.gz \
  docker-compose.yaml \
  heystat-nginx-mac.conf \
  ~/.cloudflared/config-heystat.yml \
  launch-daemons/
```

### Restore from Backup
```bash
tar -xzf heystat-config-backup.tar.gz
sudo ./deploy-mac.sh setup
./cloudflare-setup.sh setup
```

## Performance Tuning

### Docker Resources
Adjust in Docker Desktop:
- **Memory:** 4GB minimum (8GB recommended)
- **CPUs:** 2 minimum (4 recommended)
- **Disk:** 20GB minimum

### Nginx Workers
In `/opt/homebrew/etc/nginx/nginx.conf`:
```nginx
worker_processes  4;  # Match CPU cores
worker_connections  1024;
```

## Monitoring Commands

```bash
# Container stats
docker stats heystat

# Nginx status
curl http://localhost:8082/nginx_status  # If enabled

# Check all HeyStat ports
lsof -iTCP -sTCP:LISTEN | grep -E '(42337|42338|42339|8082)'

# View all logs
tail -f logs/*.log /opt/homebrew/var/log/nginx/heystat*.log
```

## Next Steps

1. **Initial Setup:**
   - Run `./quick-start.sh` for guided setup
   - Or manually: `sudo ./deploy-mac.sh setup`

2. **Configure Cloudflare:**
   - Login: `cloudflared tunnel login`
   - Setup: `./cloudflare-setup.sh setup`

3. **Verify:**
   - Check status: `sudo ./deploy-mac.sh status`
   - Access: http://localhost:8082

4. **Production:**
   - Set strong JAMOVI_ACCESS_KEY
   - Review security settings
   - Setup monitoring
   - Configure backups

## Support Resources

- **Jamovi Forum:** https://forum.jamovi.org
- **Jamovi GitHub:** https://github.com/jamovi/jamovi
- **Cloudflare Docs:** https://developers.cloudflare.com
- **Docker Docs:** https://docs.docker.com
