#!/bin/bash
# Setup Colima as LaunchAgent (per-user auto-start)

SOURCE_PLIST="/Users/mac/HeyStat/launch-daemons/com.colima.plist"
AGENT_DIR="$HOME/Library/LaunchAgents"
AGENT_PLIST="$AGENT_DIR/com.colima.plist"

echo "Setting up Colima LaunchAgent..."

# Create LaunchAgents directory if not exists
mkdir -p "$AGENT_DIR"

# Copy plist
cp "$SOURCE_PLIST" "$AGENT_PLIST"

# Set permissions
chmod 644 "$AGENT_PLIST"

# Unload if already loaded
launchctl unload "$AGENT_PLIST" 2>/dev/null

# Load LaunchAgent
launchctl load -w "$AGENT_PLIST"

if [ $? -eq 0 ]; then
    echo "✓ Colima LaunchAgent loaded successfully"
    echo "  Location: $AGENT_PLIST"
    
    # Remove from LaunchDaemons if exists
    if [ -f /Library/LaunchDaemons/com.colima.plist ]; then
        echo "Removing old LaunchDaemon..."
        sudo launchctl unload /Library/LaunchDaemons/com.colima.plist 2>/dev/null
        sudo rm /Library/LaunchDaemons/com.colima.plist
        echo "✓ Old LaunchDaemon removed"
    fi
else
    echo "✗ Failed to load Colima LaunchAgent"
    exit 1
fi

echo ""
echo "LaunchAgent will start Colima automatically on user login"
