# Jamovi Reverse Proxy Setup Notes

## Fixes Applied

### 1. Client-side URL Construction (`client/main/host.ts`)
**Problem**: `resolveUrl()` was prepending protocol to URLs that already had protocol, causing `https://https//` double protocol bug.

**Fix**: Modified `resolveUrl()` to check if URL already contains `://` before prepending protocol.

```typescript
function resolveUrl(root) {
    // If root already contains a protocol, use it directly
    if (root.includes('://')) {
        let v = root;
        if (!v.endsWith('/'))
            v += '/';
        return v;
    }
    // Root is just domain/host, construct full URL
    let v = `${ window.location.protocol }//${ root }`;
    if (new URL(v).port === '' && window.location.port !== '')
        v += `:${ window.location.port }`;
    v += '/';
    return v;
}
```

**After fix**: Run `cd /root/jamovi/client && npm run build`

### 2. Server-side URL Construction (`server/jamovi/server/public_roots.py`)
**Problem**: 
- URLs returned without trailing slash caused issues
- URLs included port `:41337` causing same-origin policy violations

**Fix**: Modified `build_public_roots()` to ensure trailing slash.

```python
if proto:
    url = f'{ proto }://{ fwd_host }{ path }'
else:
    url = f'{ fwd_host }{ path }'

# Ensure trailing slash for consistency with browser expectations
if not url.endswith('/'):
    url += '/'

new_roots.append(url)
```

**After fix**: Copy to container:
```bash
docker cp /root/jamovi/server/jamovi/server/public_roots.py jamovi:/usr/lib/jamovi/server/jamovi/server/public_roots.py
docker restart jamovi
```

### 3. Nginx Configuration (`/etc/nginx/sites-available/jamovi`)
**Critical settings**:
- `proxy_set_header Host jamovi.truyenthong.edu.vn:41337` - Must match JAMOVI_HOST_A for security
- `proxy_set_header X-Forwarded-Proto https` - Server returns https:// URLs
- `proxy_set_header X-Forwarded-Host jamovi.truyenthong.edu.vn` - **NO PORT** to avoid same-origin violations

### 4. Cloudflare Tunnel Configuration
**In Cloudflare Zero Trust Dashboard**:
- Service: `http://127.0.0.1:80`
- HTTP Host Header: `jamovi.truyenthong.edu.vn:41337`

**In Cloudflare DNS Dashboard**:
- Type: CNAME
- Name: jamovi
- Content: [tunnel-id].cfargotunnel.com
- Proxy status: Proxied (orange cloud)

## Docker Compose Configuration

```yaml
environment:
  JAMOVI_HOST_A: 'jamovi.truyenthong.edu.vn:41337'
  JAMOVI_HOST_B: 'jamovi.truyenthong.edu.vn:41338'
  JAMOVI_HOST_C: 'jamovi.truyenthong.edu.vn:41339'
  JAMOVI_ACCESS_KEY: ''  # Empty = auto-generate

volumes:
  - ./server/jamovi/server/public_roots.py:/usr/lib/jamovi/server/jamovi/server/public_roots.py:ro
```

## Verifying Setup

```bash
# Check config.js returns correct URLs
curl -s https://jamovi.truyenthong.edu.vn/config.js

# Expected output:
# window.config = {"client":{"roots":["https://jamovi.truyenthong.edu.vn/","https://jamovi.truyenthong.edu.vn/","https://jamovi.truyenthong.edu.vn/"]}}

# Check WebSocket upgrade works
curl -I https://jamovi.truyenthong.edu.vn/
# Should get HTTP 101 Switching Protocols or 302 redirect

# Check jamovi logs
docker logs jamovi --tail 20
```

## Known Non-Critical Warnings

1. **Cloudflare Insights CSP**: Cloudflare analytics script blocked by CSP
   - Fix: Dashboard → Speed → Optimization → Web Analytics → OFF
   
2. **iframe sandbox warning**: Browser security warning, doesn't affect functionality

3. **404 /{instanceId}/{analysisId}/**: Normal when no analyses created yet

## Troubleshooting

If getting "Connection failed" after changes:
1. Purge Cloudflare cache: Dashboard → Caching → Purge Everything
2. Clear browser cache: Ctrl+Shift+Delete
3. Hard refresh: Ctrl+Shift+R
4. Test in Incognito mode

If volume mount doesn't persist:
```bash
# Manual copy after container restart
docker cp /root/jamovi/server/jamovi/server/public_roots.py jamovi:/usr/lib/jamovi/server/jamovi/server/public_roots.py
docker restart jamovi
```
