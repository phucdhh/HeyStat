# Đánh giá 41 thay đổi từ Jamovi upstream

**Ngày phân tích**: December 15, 2025  
**Jamovi versions**: 2.7.13 → 2.7.14  
**Tổng commits**: 41

## 📊 Tóm tắt thay đổi

### Version Updates
- ✅ **v2.7.13** (commit 3923ffe4)
- ✅ **v2.7.14** (commit d955ee67) - Latest version

### Phân loại theo nhóm

#### 1. 🐛 Bug Fixes (9 commits - 22%)
- Fixed hydration issues
- Fixed module script execution
- Fixed library transitions
- Fixed HTML export issues
- Fixed misaligned results table contents
- Fixed missed translations in dialogs
- Fixed nCols and combineBelow in hydration
- Bug fix in format() function (NaN issue)

#### 2. ✨ New Features (15 commits - 37%)

**LaTeX Export** (Major feature):
- Added LaTeX document export
- Improved latexify functionality
- Added/improved latex export
- Added latex copy option

**Euro Decimal Support** (Regional formatting):
- Added euro comma to spreadsheet
- Added support for euro decimal in results tables
- Added setting for comma decimal indicator
- Added euro float conversion for column changes

**UI Improvements**:
- Added Context Splitbutton variation
- Added Copy split button
- Add gaps between labels in apps menu
- Added new icon: menu-data-copy-latex.svg

**R/jmvcore Enhancements**:
- jmvcore: Image added scale coefficients
- jmvcore: Html results added set methods

#### 3. 🔄 Refactoring & Improvements (12 commits - 29%)
- Moved hydrations tests (better organization)
- Moved latexify et al. from common to main
- Updates to hydration (3 commits)
- Improvements to hydration (2 commits)
- Updated references
- Simplified hydrate
- Compiler improvements to value plumbing

#### 4. 🧹 Cleanup (5 commits - 12%)
- Removed rmarkdown
- Little latex tidy-up
- Adjustments (server-side utils)

## ⚠️ Phân tích Conflicts với HeyStat

### Files HeyStat đã modify:
1. `.gitignore` - Added logs/, Documents/
2. `README.md` - HeyStat documentation
3. `client/index.html` - Branding (title, aria-label, header)
4. `client/package.json` - Name, repo URL
5. `docker-compose.yaml` - Ports, domain, platform
6. `server/jamovi/server/server.py` - Proxy headers
7. `server/jamovi/server/__main__.py` - Proxy headers
8. `server/tests/test_proxy_headers.py` - New test

### Files Jamovi thay đổi (overlap với HeyStat):

#### 🔴 HIGH CONFLICT RISK:
**KHÔNG CÓ!** Server files không bị Jamovi modify.

#### 🟡 MEDIUM CONFLICT RISK:
1. **client/index.html** (1 commit: "Added hydration")
   - Jamovi change: Added hydration script link (minor)
   - HeyStat change: Branding (title, labels)
   - **Resolution**: Easy - giữ HeyStat branding, accept jamovi's script addition

2. **client/package.json** (potential dependency updates)
   - Check nếu jamovi update dependencies
   - **Resolution**: Merge dependencies, giữ HeyStat name/repo

#### 🟢 LOW CONFLICT RISK:
1. **README.md** - HeyStat docs hoàn toàn khác → no conflict
2. **.gitignore** - HeyStat additions không conflict với jamovi
3. **docker-compose.yaml** - Jamovi không modify file này

### Files HeyStat KHÔNG modify - Safe to merge:
- `client/common/*` - Many changes (formatting, utils, i18n)
- `client/main/*` - UI improvements, new features
- `client/resultsview/*` - Bug fixes
- `client/assets/*` - New icons
- `server/jamovi/server/instance.py` - Utils improvements
- `server/jamovi/server/utils/*` - CSV/HTML parser improvements
- `server/jamovi/common/*` - Column handling improvements
- `jmvcore/*` - R package enhancements
- `jmv`, `plots` submodules - Updated

## 📋 Khuyến nghị

### ✅ NÊN MERGE - Highly Recommended

**Lý do merge**:
1. **Bug fixes quan trọng**: 9 bug fixes sẽ cải thiện stability
2. **New features hữu ích**: LaTeX export, Euro decimal support
3. **Low conflict risk**: Chỉ 1-2 files có conflict, dễ resolve
4. **Version updates**: v2.7.13 → v2.7.14 (2 versions newer)
5. **No server conflicts**: HeyStat proxy headers không bị ảnh hưởng

**Benefits cho HeyStat users**:
- ✅ LaTeX export cho academic users
- ✅ Euro decimal support (useful for Vietnamese số thập phân)
- ✅ Better hydration (performance improvement)
- ✅ UI improvements (split buttons, better copy)
- ✅ Bug fixes (more stable)

### ⚠️ Lưu ý khi merge

**Critical files cần review**:
1. `client/index.html` - Giữ HeyStat branding
2. `client/package.json` - Giữ HeyStat metadata
3. Test thoroughly sau khi merge

**Không merge nếu**:
- ❌ Không có thời gian test kỹ (2-3 hours)
- ❌ Đang có production issues cần fix
- ❌ Không comfortable với git conflict resolution

## 🔄 Merge Plan

### Phase 1: Preparation (15 mins)
```bash
# Backup current state
git branch backup-before-jamovi-merge

# Create test branch
git checkout -b test-jamovi-2.7.14-merge

# Ensure clean state
/Users/mac/HeyStat/scripts/check-status.sh
```

### Phase 2: Merge (30 mins)
```bash
# Fetch latest
git fetch upstream

# Merge with no-commit (review first)
git merge upstream/main --no-commit --no-ff

# Check conflicts
git status
```

### Phase 3: Resolve Conflicts (45 mins)

**client/index.html**:
```bash
# Keep HeyStat branding, accept structural changes
# Manual edit to merge both
vim client/index.html

# Ensure these stay as HeyStat:
# - <html aria-label="HeyStat">
# - <title>HeyStat - Statistical Analysis</title>
# - header-text: HeyStat
```

**client/package.json**:
```bash
# Merge dependencies, keep HeyStat metadata
vim client/package.json

# Keep: name, description, author, repository, homepage
# Accept: New/updated dependencies
```

**Other files**:
```bash
# Accept jamovi changes for files HeyStat didn't modify
git checkout --theirs [file]
```

### Phase 4: Build & Test (60 mins)
```bash
# Rebuild client
cd client
npm install  # Install any new dependencies
npm run build

# Restart container
cd ..
docker compose restart

# Test checklist:
# 1. UI loads: https://heystat.truyenthong.edu.vn
# 2. Branding correct: Title = "HeyStat - Statistical Analysis"
# 3. Header shows "HeyStat"
# 4. Load CSV file
# 5. Run descriptive statistics
# 6. Test new LaTeX export feature
# 7. Test copy/paste
# 8. Check console for errors
```

### Phase 5: Commit (10 mins)
```bash
git add .
git commit -m "Merge jamovi v2.7.14 updates

Merged jamovi commits from v2.7.13 to v2.7.14:
- 9 bug fixes for improved stability
- LaTeX export feature
- Euro decimal support
- UI improvements (split buttons, context menus)
- Hydration performance improvements

Preserved HeyStat customizations:
- Branding (title, labels, names)
- Deployment config (ports, domain)
- Proxy headers support

Tested: UI, branding, file operations, analyses"
```

### Phase 6: Deploy (15 mins)
```bash
# Merge to main
git checkout main
git merge test-jamovi-2.7.14-merge

# Push to GitHub
git push origin main

# Monitor
/Users/mac/HeyStat/scripts/check-status.sh
tail -f /Users/mac/HeyStat/logs/heystat-complete-startup.log
```

## 📈 Risk Assessment

### Low Risk (95% confidence)
- Most changes are in files HeyStat didn't touch
- Server modifications (proxy headers) safe - jamovi didn't change server.py
- Conflicts are predictable and well-documented

### Medium Benefits
- Bug fixes improve stability
- New features add value for users
- Keeps HeyStat closer to jamovi upstream (easier future merges)

### High Confidence
- Clear merge strategy documented
- Test branch approach minimizes risk
- Easy rollback if issues (`git reset --hard backup-before-jamovi-merge`)

## 🎯 Recommendation

### ✅ **MERGE NÊN THỰC HIỆN**

**Timeline**: Next 1-2 days when có 3 hours free time

**Priority**: **HIGH** - 2 versions behind, many bug fixes

**Confidence Level**: **90%** - Low conflict risk, high benefit

**Fallback**: Easy rollback, test branch approach

## 📝 Post-Merge Tasks

1. **Update documentation**:
   - Update README.md if jamovi added new features
   - Document new LaTeX export in user guide

2. **Announce updates**:
   - List new features available in HeyStat
   - Highlight Euro decimal support

3. **Monitor**:
   - Watch for any issues in first 24-48 hours
   - Check logs: `/Users/mac/HeyStat/logs/`

4. **Next merge**:
   - Set reminder to check jamovi updates monthly
   - Easier to merge small updates frequently vs. large merges

---

## Summary Table

| Metric | Value | Risk Level |
|--------|-------|-----------|
| Total Commits | 41 | - |
| Bug Fixes | 9 (22%) | 🟢 Low |
| New Features | 15 (37%) | 🟢 Low |
| Files HeyStat Modified | 8 | - |
| Actual Conflicts | 1-2 files | 🟡 Medium |
| Server Conflicts | 0 | 🟢 None |
| Test Time Required | 2-3 hours | - |
| Overall Risk | LOW | 🟢 |
| Recommendation | **MERGE** | ✅ |

