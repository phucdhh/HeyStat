#!/bin/bash
# Setup HeyStat Auto-Start as LaunchAgent (runs on user login)

echo "Setting up HeyStat Auto-Start as LaunchAgent..."

# Create LaunchAgent directory
mkdir -p ~/Library/LaunchAgents

# Create LaunchAgent plist
cat > ~/Library/LaunchAgents/com.heystat.autostart.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.heystat.autostart</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/mac/HeyStat/scripts/start-heystat-complete.sh</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>StandardOutPath</key>
    <string>/Users/mac/HeyStat/logs/launchagent.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/mac/HeyStat/logs/launchagent-error.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>/Users/mac</string>
    </dict>
    
    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
EOF

# Set permissions
chmod 644 ~/Library/LaunchAgents/com.heystat.autostart.plist

# Unload old LaunchDaemon if exists
sudo launchctl unload /Library/LaunchDaemons/com.heystat.complete.plist 2>/dev/null
sudo rm -f /Library/LaunchDaemons/com.heystat.complete.plist

# Unload if already loaded
launchctl unload ~/Library/LaunchAgents/com.heystat.autostart.plist 2>/dev/null

# Load LaunchAgent
launchctl load -w ~/Library/LaunchAgents/com.heystat.autostart.plist

if [ $? -eq 0 ]; then
    echo "✓ HeyStat LaunchAgent loaded successfully"
    echo "  Location: ~/Library/LaunchAgents/com.heystat.autostart.plist"
    echo ""
    echo "LaunchAgent will:"
    echo "  - Start automatically on user login"
    echo "  - Keep Colima and HeyStat running"
    echo "  - Restart services if they crash"
else
    echo "✗ Failed to load HeyStat LaunchAgent"
    exit 1
fi
