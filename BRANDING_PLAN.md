# HeyStat Branding Changes - Action Plan

## Overview
This document outlines all changes needed to rebrand jamovi to HeyStat for public GitHub release.

## ✅ Completed

### 1. Legal & Licensing
- [x] Created [FORK_NOTICE.md](FORK_NOTICE.md) - Fork attribution and license compliance
- [x] Preserved original [LICENSE.md](LICENSE.md) - AGPL3/GPL2+ licenses intact
- [x] Preserved [CONTRIBUTING.md](CONTRIBUTING.md) - Original contribution guidelines

## 🔄 In Progress

### 2. Logo & Visual Assets

#### Primary Logos (CRITICAL - User facing)
- [ ] `/client/assets/logo-v.svg` - Main jamovi logo → HeyStat logo
- [ ] `/client/assets/logo-v-naked.svg` - Naked logo variant
- [ ] `/client/public/favicon.ico` - Browser favicon

#### Secondary Logos (Optional)
- [ ] `/client/assets/logo-store.svg` - Store logo (if used)
- [ ] `/client/assets/logo-osf.png` - OSF integration logo (if used)

**Action**: 
1. Design simple HeyStat logo (text-based or simple icon)
2. Generate SVG and ICO formats
3. Replace logo files
4. Alternatively: Use temporary placeholder text logo

### 3. Application Name in UI

#### HTML Files
- [ ] `/client/index.html`:
  - Line 2: `<html aria-label="jamovi">` → `"HeyStat"`
  - Line 5: `<title>jamovi</title>` → `<title>HeyStat</title>`
  - Line 9: Unsupported browser redirect URL (update or remove)
  - Line 20: `jamovi<span>` → `HeyStat<span>`

- [ ] `/client/resultsview.html` - Check for "jamovi" references
- [ ] `/client/analysisui.html` - Check for "jamovi" references

#### TypeScript/JavaScript Source Files
Search and replace in:
- [ ] `/client/main/*.ts` - Window titles, app names
- [ ] `/client/common/*.ts` - Shared constants
- [ ] `/electron/app/*.js` - Electron app name, window titles

**Command to find all references**:
```bash
grep -r "jamovi" client/main/ client/common/ --include="*.ts" --include="*.js"
```

### 4. Main README.md

Replace `/README.md` with:

```markdown
# HeyStat

**HeyStat** is a web-based statistical analysis platform, forked from [jamovi](https://www.jamovi.org).

## About

HeyStat provides:
- ✅ Web-based statistical analysis (no installation required)
- ✅ Familiar interface for SPSS users
- ✅ Vietnamese-friendly deployment
- ✅ Educational focus for Vietnamese institutions

**Built on jamovi 2.7.6** - See [FORK_NOTICE.md](FORK_NOTICE.md) for attribution.

## Quick Access

🌐 **Live Instance**: https://heystat.truyenthong.edu.vn

## Features

- Descriptive statistics
- T-tests, ANOVA, regression
- Data visualization
- CSV/SPSS/SAS file import
- Real-time analysis updates

## For Users

### Access HeyStat
Visit: https://heystat.truyenthong.edu.vn

No installation required - works in any modern browser.

### Documentation
- Based on jamovi - see [jamovi user manual](https://www.jamovi.org/user-manual.html)
- All jamovi analyses and features are available

## For Developers

### Deployment
See [deployment documentation](docs/) for:
- Docker deployment (Colima on macOS)
- Nginx reverse proxy setup
- Cloudflare Tunnel configuration
- Auto-start configuration

### Building from Source
```bash
# Clone repository
git clone https://github.com/[your-org]/HeyStat.git
cd HeyStat

# Build with Docker
docker-compose build
docker-compose up
```

Access at: http://localhost:42337

### Key Differences from jamovi

**Deployment**:
- Optimized for ARM64 macOS (Apple Silicon)
- Custom port configuration (42337-42339)
- Cloudflare Tunnel integration
- Auto-start LaunchDaemon

**Branding**:
- Application name: HeyStat
- Custom visual identity
- Vietnamese localization

See [FORK_NOTICE.md](FORK_NOTICE.md) for complete fork information.

## License

HeyStat is licensed under AGPL3/GPL2+, same as jamovi.

Copyright (C) 2025 HeyStat Team  
Copyright (C) 2016-2024 The jamovi team

See [LICENSE.md](LICENSE.md) for full license text.

## Acknowledgments

HeyStat is built on [jamovi](https://www.jamovi.org) by The jamovi team.

We are grateful to:
- The jamovi team for excellent open-source software
- The R Project and R package developers
- The open-source community

## Links

- **Original jamovi**: https://www.jamovi.org
- **jamovi Source**: https://github.com/jamovi/jamovi
- **HeyStat Live**: https://heystat.truyenthong.edu.vn
```

### 5. Package Metadata

Update all `package.json` files:

#### `/client/package.json`
```json
{
  "name": "heystat-client",
  "description": "HeyStat client (forked from jamovi)",
  "author": "HeyStat Team (original: jamovi team)",
  "homepage": "https://heystat.truyenthong.edu.vn",
  "repository": {
    "type": "git",
    "url": "https://github.com/[your-org]/HeyStat.git"
  }
}
```

Files to update:
- [ ] `/client/package.json`
- [ ] `/electron/package.json`
- [ ] `/i18n/package.json`
- [ ] `/jamovi-compiler/package.json`
- [ ] `/jmv/package.json`
- [ ] `/chrome-test/package.json`

### 6. Docker & Configuration

Already updated:
- [x] `docker-compose.yaml` - Container name, domain, ports
- [x] `heystat-nginx-mac.conf` - Domain configuration
- [x] LaunchDaemon configurations

### 7. Documentation Files

Create new docs:
- [x] `FORK_NOTICE.md` - Legal attribution
- [x] `AUTOSTART_FIX.md` - Auto-start troubleshooting
- [x] `README_MAC_DEPLOYMENT.md` - Mac deployment guide
- [ ] Update `CONTRIBUTING.md` - Point to HeyStat repo for contributions

Keep original:
- [x] `LICENSE.md` - Preserve original licenses
- [x] `SETUP_NOTES.md` - Keep original setup notes

## 📋 Testing Checklist

After all changes:

### Visual Testing
- [ ] Open https://heystat.truyenthong.edu.vn
- [ ] Verify browser tab shows "HeyStat" title
- [ ] Verify browser favicon (if changed)
- [ ] Check header shows "HeyStat" not "jamovi"
- [ ] Check About dialog (if exists)
- [ ] Verify no jamovi logo visible in UI

### Functional Testing
- [ ] Load CSV file - works
- [ ] Run analysis (e.g., descriptives) - works
- [ ] Save .omv file - works
- [ ] Reload page - state persists

### Legal Compliance
- [ ] FORK_NOTICE.md present and complete
- [ ] Original LICENSE.md preserved
- [ ] All original copyright notices intact
- [ ] HeyStat copyright added to modified files

### Repository Hygiene
- [ ] `.gitignore` updated (logs/, Documents/, credentials)
- [ ] No sensitive data (access keys, passwords)
- [ ] No personal data in Documents/
- [ ] README.md clearly identifies as fork

## 🚀 Quick Start Commands

### 1. Simple Text Logo (No design needed)
```bash
# Use text-based placeholder logo
echo "Use 'HeyStat' text in UI instead of logo temporarily"
```

### 2. Find all "jamovi" references
```bash
grep -r "jamovi" client/ --include="*.html" --include="*.ts" --include="*.js" | grep -v node_modules
```

### 3. Update HTML titles
```bash
# Will be done with multi_replace_string_in_file
```

### 4. Rebuild client
```bash
cd /Users/mac/HeyStat
docker compose build
docker compose up -d
```

## Priority Order

### HIGH PRIORITY (Must do before GitHub push)
1. ✅ FORK_NOTICE.md
2. Update README.md
3. Update HTML titles (index.html)
4. Update package.json metadata
5. Test visual changes

### MEDIUM PRIORITY (Can do logo later)
6. Replace logos with HeyStat branding
7. Update About dialog
8. Search/replace "jamovi" in source

### LOW PRIORITY (Optional improvements)
9. Custom CSS styling
10. Vietnamese translations
11. Additional documentation

---

**Next Steps**: Start with HTML title changes and README.md update.
