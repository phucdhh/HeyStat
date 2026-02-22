# HeyStat - Jamovi Upstream Sync Guide

## Overview

HeyStat is a proper fork of jamovi. You can safely merge updates from jamovi upstream while preserving HeyStat customizations.

## Setup Upstream Remote

```bash
cd /Users/mac/HeyStat
git remote add upstream https://github.com/jamovi/jamovi.git
git fetch upstream
```

## Check for Jamovi Updates

```bash
# See what's new in jamovi
git log HEAD..upstream/main --oneline

# See detailed changes
git log HEAD..upstream/main --stat
```

## Merge Strategy

### Option 1: Automatic Merge (Recommended for minor updates)

```bash
# Merge jamovi updates
git fetch upstream
git merge upstream/main

# If conflicts occur, resolve them (see below)
# Then commit
git commit -m "Merge jamovi upstream updates"

# Push to HeyStat
git push origin main
```

### Option 2: Rebase (For clean history, advanced)

```bash
# Rebase HeyStat changes on top of latest jamovi
git fetch upstream
git rebase upstream/main

# Resolve conflicts as they appear
# Force push (only if you understand the implications)
git push origin main --force-with-lease
```

## Conflict Resolution Rules

### Files HeyStat Modified

**Branding Files (Keep HeyStat version)**:
- `client/index.html` - Keep "HeyStat", "HeyStat - Statistical Analysis"
- `client/package.json` - Keep "heystat-client", HeyStat repo URL
- `README.md` - Keep HeyStat introduction, add jamovi updates to appropriate sections

**Deployment Config (Merge carefully)**:
- `docker-compose.yaml`:
  - Keep: ports 42337-42339, container name "heystat", platform linux/arm64
  - Keep: JAMOVI_HOST_A/B/C with heystat.truyenthong.edu.vn
  - Keep: volumes mounting ./Documents
  - Accept: New environment variables, new dependencies from jamovi
  
- `.gitignore`:
  - Keep: HeyStat additions (logs/, Documents/, *.local)
  - Accept: New patterns from jamovi

**Server Modifications (Review carefully)**:
- `server/jamovi/server/server.py`:
  - Keep: Proxy headers handling (X-Forwarded-*, X-Real-IP)
  - Keep: WebSocket Origin/Host header modifications
  - Accept: Bug fixes, new features from jamovi
  - **Action**: Manually merge both changes

- `server/jamovi/server/__main__.py`:
  - Keep: Proxy header imports and handling
  - Accept: Other jamovi changes

### Conflict Resolution Commands

```bash
# During merge conflict:

# 1. See conflicted files
git status

# 2. For each conflicted file:

# Keep HeyStat version completely
git checkout --ours path/to/file

# Keep Jamovi version completely
git checkout --theirs path/to/file

# Manual merge (recommended for important files)
# Edit the file, resolve conflicts marked with <<<<<<<, =======, >>>>>>>
vim path/to/file

# 3. Mark as resolved
git add path/to/file

# 4. Complete merge
git commit
```

## Detailed Conflict Scenarios

### Scenario 1: client/index.html conflict

```bash
# If jamovi updates HTML structure:
git checkout --ours client/index.html

# Then manually apply jamovi's structural changes while keeping HeyStat branding:
# - Keep: <title>HeyStat - Statistical Analysis</title>
# - Keep: <html aria-label="HeyStat">
# - Keep: HeyStat in header-text
# - Apply: Any new HTML elements, scripts, or structural changes from jamovi
```

### Scenario 2: docker-compose.yaml conflict

```bash
# Merge both changes:
1. git status  # See conflict
2. vim docker-compose.yaml  # Edit manually

# Keep from HeyStat:
ports:
  - '42337:42337'
  - '42338:42338'
  - '42339:42339'
container_name: heystat
platform: linux/arm64
JAMOVI_HOST_A: 'heystat.truyenthong.edu.vn:42337'

# Accept from Jamovi:
- New environment variables
- New dependencies
- Bug fixes

3. git add docker-compose.yaml
4. git commit
```

### Scenario 3: server.py conflict

```bash
# This is critical - must merge carefully:
1. Back up current version:
   cp server/jamovi/server/server.py server.py.heystat

2. Accept jamovi version:
   git checkout --theirs server/jamovi/server/server.py

3. Re-apply HeyStat proxy headers:
   # Edit server.py and add back proxy header handling:
   - X-Forwarded-Proto
   - X-Forwarded-Host
   - X-Real-IP
   - WebSocket Origin/Host modifications

4. Test thoroughly:
   docker compose restart
   curl -I https://heystat.truyenthong.edu.vn

5. Commit:
   git add server/jamovi/server/server.py
   git commit -m "Merge jamovi server updates + restore HeyStat proxy headers"
```

## Testing After Merge

```bash
# 1. Rebuild client
cd client
npm run build

# 2. Restart container
cd ..
docker compose restart

# 3. Test basic functionality
curl -I http://localhost:8082
curl -I https://heystat.truyenthong.edu.vn

# 4. Test UI
open https://heystat.truyenthong.edu.vn
# Verify:
# - Browser tab shows "HeyStat - Statistical Analysis"
# - Header shows "HeyStat"
# - Can load CSV file
# - Can run analysis
```

## Rollback if Needed

```bash
# If merge causes issues:

# Option 1: Abort merge (before commit)
git merge --abort

# Option 2: Revert merge commit (after commit)
git revert -m 1 HEAD

# Option 3: Hard reset to before merge
git reset --hard origin/main
```

## Best Practices

### Before Merging
1. **Backup**: Create a branch for testing
   ```bash
   git checkout -b test-jamovi-merge
   git merge upstream/main
   # Test thoroughly
   # If OK, merge to main
   ```

2. **Review changes**: Check what jamovi updated
   ```bash
   git diff HEAD..upstream/main
   ```

3. **Check HeyStat services**: Ensure everything running
   ```bash
   /Users/mac/HeyStat/scripts/check-status.sh
   ```

### During Merge
1. **Resolve conflicts strategically**:
   - Branding: Always keep HeyStat
   - Config: Merge both
   - Code: Review carefully, test thoroughly

2. **Test incrementally**: After each conflict resolution
   ```bash
   docker compose restart
   curl -I https://heystat.truyenthong.edu.vn
   ```

### After Merge
1. **Full testing**: All features
2. **Update documentation**: If jamovi added new features
3. **Commit with clear message**:
   ```bash
   git commit -m "Merge jamovi v2.X.X updates
   
   - Updated [list features]
   - Preserved HeyStat branding and configuration
   - Tested: [list what you tested]"
   ```

## Files That NEVER Conflict

HeyStat-only files (won't conflict with jamovi):
- `FORK_NOTICE.md`
- `AUTOSTART_FIX.md`
- `BRANDING_*.md`
- `LAUNCHDAEMONS_GUIDE.md`
- `heystat-nginx-mac.conf`
- `scripts/*`
- `launch-daemons/*`
- `Documents/`

## Example: Merge Jamovi v2.8.0

```bash
# 1. Fetch updates
git fetch upstream
git log HEAD..upstream/main --oneline

# 2. Create test branch
git checkout -b merge-jamovi-2.8.0

# 3. Merge
git merge upstream/main

# 4. Resolve conflicts (example)
# Conflict in client/index.html
git checkout --ours client/index.html  # Keep HeyStat branding

# Conflict in docker-compose.yaml
vim docker-compose.yaml  # Manually merge
# Keep HeyStat ports, domain
# Accept jamovi's new env vars
git add docker-compose.yaml

# 5. Complete merge
git commit

# 6. Test
cd client && npm run build && cd ..
docker compose restart
/Users/mac/HeyStat/scripts/check-status.sh

# 7. If OK, merge to main
git checkout main
git merge merge-jamovi-2.8.0
git push origin main

# 8. Cleanup
git branch -d merge-jamovi-2.8.0
```

## Automated Conflict Detection

Create a script to detect potential conflicts before merging:

```bash
#!/bin/bash
# scripts/check-upstream-conflicts.sh

git fetch upstream

echo "Files modified by HeyStat that might conflict:"
git diff --name-only 23a1c3b6..HEAD | \
  grep -v "^BRANDING\|^AUTOSTART\|^LAUNCHDAEMONS\|^FORK_NOTICE\|^scripts/\|^launch-daemons/"

echo ""
echo "Files changed in jamovi upstream:"
git diff --name-only HEAD..upstream/main | head -20

echo ""
echo "Potential conflicts (files modified by both):"
comm -12 \
  <(git diff --name-only 23a1c3b6..HEAD | sort) \
  <(git diff --name-only HEAD..upstream/main | sort)
```

## Summary

**HeyStat CAN safely merge Jamovi updates**:
- ✅ Conflicts are predictable and manageable
- ✅ Most changes won't conflict (jamovi updates features, HeyStat changes branding)
- ✅ Strategy: Keep HeyStat branding, merge jamovi features
- ✅ Test thoroughly after merge

**Risk Level**:
- 🟢 Low: Branding files, docs
- 🟡 Medium: docker-compose.yaml, .gitignore
- 🔴 High: server.py (if jamovi refactors server code)

**Recommendation**: 
- Merge jamovi updates **every 3-6 months**
- Always test in a branch first
- Keep detailed merge commit messages
