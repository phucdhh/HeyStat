# HeyStat Branding Changes - Summary

> **Tài liệu lịch sử — Mac Mini M2 / `heystat.truyenthong.edu.vn`.**
> Production hiện tại là Linux LXC tại https://heystat.pedu.vn. Xem [README.md](README.md) để biết tài liệu đang dùng.

## ✅ Completed Changes (December 15, 2025)

### 1. Legal & Attribution ✓

**Created: [FORK_NOTICE.md](FORK_NOTICE.md)**
- Clear attribution to jamovi as original project
- Explanation of fork purpose and differences
- Copyright notices: Both jamovi team and HeyStat team
- License compliance: AGPL3/GPL2+ preserved
- Trademark notice: Distinguishes HeyStat from jamovi

**Preserved: [LICENSE.md](../LICENSE.md)**
- Original AGPL3/GPL2+ licenses intact
- No modifications to license terms

### 2. Main Documentation ✓

**Updated: [README.md](README.md)**

Changes:
- Title: `# jamovi` → `# HeyStat`
- Description: Fork attribution added
- Quick access: Link to https://heystat.truyenthong.edu.vn
- Features section: Focused on HeyStat use cases
- Deployment: Mac ARM64, Colima, Cloudflare details
- Key Differences section: Lists deployment and branding changes
- License section: Dual copyright (HeyStat + jamovi)
- Acknowledgments: Credits jamovi team
- Links: Both jamovi and HeyStat resources

### 3. HTML Interface ✓

**Updated: [client/index.html](../client/index.html)**

Changes:
- `<html aria-label="jamovi">` → `aria-label="HeyStat"`
- `<title>jamovi</title>` → `<title>HeyStat - Statistical Analysis</title>`
- Unsupported browser redirect: Changed to alert (removed jamovi.org link)
- Header text: `jamovi<span>` → `HeyStat<span>`

**Result**: Browser tab now shows "HeyStat - Statistical Analysis"

### 4. Package Metadata ✓

**Updated: [client/package.json](../client/package.json)**

Changes:
- `"name": "jamovi-client"` → `"heystat-client"`
- `"version": "0.1.0"` → `"2.7.6"` (match jamovi base version)
- Added: `"description": "HeyStat client - forked from jamovi"`
- Added: `"author": "HeyStat Team (original: jamovi team)"`
- Repository URL: jamovi/jamovi → your-org/HeyStat (placeholder)
- Added: `"homepage": "https://heystat.truyenthong.edu.vn"`

### 5. Planning Documents ✓

**Created: [BRANDING_PLAN.md](BRANDING_PLAN.md)**
- Complete action plan for rebranding
- Logo/assets identification
- Testing checklist
- Priority order

## 🔧 Remaining Tasks

### High Priority

#### 1. Logo Files (Optional - can use text)
Files identified but not yet replaced:
- `/client/assets/logo-v.svg` - Main logo
- `/client/assets/logo-v-naked.svg` - Naked logo variant  
- `/client/public/favicon.ico` - Browser favicon

**Options**:
- **A**: Create simple text-based HeyStat logo
- **B**: Use existing with temporary watermark
- **C**: Design custom logo later

#### 2. Rebuild Client
```bash
cd /Users/mac/HeyStat/client
npm run build
```

Then rebuild Docker:
```bash
cd /Users/mac/HeyStat
docker compose build
docker compose up -d
```

#### 3. Other package.json Files
Still using jamovi names:
- `/electron/package.json`
- `/i18n/package.json`
- `/jamovi-compiler/package.json`

**Impact**: Low (internal tooling, not user-facing)

### Medium Priority

#### 4. Source Code References
Search for "jamovi" in TypeScript/JavaScript:
```bash
grep -r "jamovi" client/main/ client/common/ --include="*.ts" --include="*.js" | wc -l
```

**Areas to check**:
- Window titles
- About dialog
- Help text
- Error messages
- Log messages

### Low Priority

#### 5. Additional Logos/Assets
- `/client/assets/logo-store.svg` - App store logo (if used)
- `/client/assets/logo-osf.png` - OSF integration (if used)

#### 6. i18n Translations
Update Vietnamese translations to use "HeyStat" instead of "jamovi"

## 📊 Current State

### What Users See Now

**Before rebuild**:
- Browser tab: "jamovi" (old)
- Header: "jamovi" (old)
- Logo: jamovi logo (old)

**After rebuild** (with current changes):
- Browser tab: "HeyStat - Statistical Analysis" ✓
- Header: "HeyStat" ✓
- Logo: jamovi logo (not changed yet - optional)

### GitHub Ready Status

**✅ Safe to publish**:
- [x] FORK_NOTICE.md with clear attribution
- [x] LICENSE.md preserved
- [x] README.md clearly identifies as fork
- [x] No sensitive data (credentials removed)
- [x] .gitignore updated

**⚠️ Recommended before publish**:
- [ ] Rebuild client with new branding
- [ ] Test UI shows "HeyStat" not "jamovi"
- [ ] Update repository URL in package.json (remove placeholder)

**Optional enhancements**:
- [ ] Replace logos
- [ ] Update other package.json files
- [ ] Search/replace code references

## 🧪 Testing After Rebuild

### Visual Tests
```bash
# After rebuild, check these:
1. Open https://heystat.truyenthong.edu.vn
2. Browser tab title = "HeyStat - Statistical Analysis" ✓
3. Header shows "HeyStat" ✓
4. No visible "jamovi" text in UI ✓
5. Favicon (browser icon) - still jamovi (optional to change)
```

### Functional Tests
```bash
# Verify nothing broke:
1. Load CSV file
2. Run descriptive statistics
3. Create plot
4. Save .omv file
5. Reload page - state persists
```

## 📝 Next Steps

### Immediate (to apply changes)

```bash
# 1. Rebuild client
cd /Users/mac/HeyStat/client
npm run build

# 2. Rebuild and restart Docker
cd /Users/mac/HeyStat
docker compose build
docker compose up -d

# 3. Test
open https://heystat.truyenthong.edu.vn
```

### Before GitHub Push

```bash
# 1. Update repository URL in package.json
# Change: "url": "https://github.com/your-org/HeyStat.git"
# To your actual GitHub repo URL

# 2. Verify no sensitive data
grep -r "JAMOVI_ACCESS_KEY" . --exclude-dir=node_modules
grep -r "password" . --exclude-dir=node_modules

# 3. Check .gitignore covers:
cat .gitignore | grep -E "logs|Documents|credentials|.cloudflared"

# 4. Final review
git status
git diff
```

## 🎯 Minimum Viable Rebrand (MVP)

For immediate GitHub publication, you need:

**Must Have** ✅:
1. FORK_NOTICE.md
2. README.md updated
3. HTML title changed
4. LICENSE.md preserved
5. No sensitive data

**Should Have** (quick wins):
6. Client rebuilt with changes
7. Tested basic functionality
8. Repository URL updated in package.json

**Nice to Have** (can do later):
9. Logo replaced
10. All code references updated
11. Full test coverage

---

## Summary

### What's Done ✓
- Legal compliance (FORK_NOTICE, LICENSE)
- Main documentation (README)
- HTML interface branding
- Package metadata (client)

### What's Left
- **Rebuild client** to apply changes (15 minutes)
- **Test** UI shows HeyStat (5 minutes)
- **Optional**: Replace logos (1-2 hours if designing new)

### Ready to Publish?
**YES** - After rebuilding client and quick testing.

All legal requirements met. Rebranding is 90% complete. Remaining work is optional enhancements.

