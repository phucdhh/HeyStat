#!/bin/bash
# Cloudflare Tunnel Setup Script for HeyStat
# This script configures Cloudflare Tunnel for heystat.truyenthong.edu.vn

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
TUNNEL_NAME="heystat"
DOMAIN="heystat.truyenthong.edu.vn"
LOCAL_SERVICE="http://localhost:8082"
HTTP_HOST_HEADER="heystat.truyenthong.edu.vn:42337"

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if cloudflared is installed
check_cloudflared() {
    if ! command -v cloudflared &> /dev/null; then
        log_error "cloudflared is not installed"
        log_info "Install with: brew install cloudflared"
        exit 1
    fi
    log_info "cloudflared found: $(which cloudflared)"
}

# Check if logged in
check_login() {
    log_step "Checking Cloudflare authentication..."
    if cloudflared tunnel list &> /dev/null; then
        log_info "Already authenticated with Cloudflare"
        return 0
    else
        log_warn "Not authenticated with Cloudflare"
        log_info "Please run: cloudflared tunnel login"
        exit 1
    fi
}

# Create tunnel if it doesn't exist
create_tunnel() {
    log_step "Creating/checking tunnel '$TUNNEL_NAME'..."
    
    # Check if tunnel already exists
    if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
        log_info "Tunnel '$TUNNEL_NAME' already exists"
        TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
        log_info "Tunnel ID: $TUNNEL_ID"
    else
        log_info "Creating new tunnel '$TUNNEL_NAME'..."
        cloudflared tunnel create "$TUNNEL_NAME"
        TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
        log_info "Created tunnel with ID: $TUNNEL_ID"
    fi
}

# Get tunnel ID
get_tunnel_id() {
    TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
    if [ -z "$TUNNEL_ID" ]; then
        log_error "Could not find tunnel ID for '$TUNNEL_NAME'"
        exit 1
    fi
    echo "$TUNNEL_ID"
}

# Create tunnel configuration
create_config() {
    log_step "Creating tunnel configuration..."
    
    TUNNEL_ID=$(get_tunnel_id)
    CONFIG_FILE="$HOME/.cloudflared/config-heystat.yml"
    
    cat > "$CONFIG_FILE" << EOF
# Cloudflare Tunnel Configuration for HeyStat
tunnel: $TUNNEL_ID
credentials-file: $HOME/.cloudflared/$TUNNEL_ID.json

ingress:
  # Route for heystat.truyenthong.edu.vn
  - hostname: $DOMAIN
    service: $LOCAL_SERVICE
    originRequest:
      # CRITICAL: Must match JAMOVI_HOST_A in docker-compose.yaml
      httpHostHeader: $HTTP_HOST_HEADER
      noTLSVerify: false
      connectTimeout: 60s
      # WebSocket support
      disableChunkedEncoding: true
  
  # Catch-all rule (required)
  - service: http_status:404
EOF
    
    log_info "Configuration saved to: $CONFIG_FILE"
    cat "$CONFIG_FILE"
}

# Setup DNS
setup_dns() {
    log_step "Setting up DNS route..."
    
    TUNNEL_ID=$(get_tunnel_id)
    
    # Check if route already exists
    if cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN" 2>&1 | grep -q "already exists"; then
        log_info "DNS route for $DOMAIN already exists"
    else
        cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN"
        log_info "DNS route created: $DOMAIN -> $TUNNEL_NAME"
    fi
}

# Test the tunnel
test_tunnel() {
    log_step "Testing tunnel (Ctrl+C to stop)..."
    
    CONFIG_FILE="$HOME/.cloudflared/config-heystat.yml"
    
    log_info "Starting tunnel in test mode..."
    log_info "If successful, you should be able to access: https://$DOMAIN"
    log_warn "Press Ctrl+C to stop the test"
    
    cloudflared tunnel --config "$CONFIG_FILE" run "$TUNNEL_NAME"
}

# Install as service
install_service() {
    log_step "Installing tunnel as a system service..."
    
    CONFIG_FILE="$HOME/.cloudflared/config-heystat.yml"
    
    # Create a separate plist for HeyStat tunnel
    PLIST_FILE="/Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist"
    
    sudo tee "$PLIST_FILE" > /dev/null << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.cloudflared.heystat</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>--config</string>
        <string>$CONFIG_FILE</string>
        <string>run</string>
        <string>$TUNNEL_NAME</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>StandardOutPath</key>
    <string>/Users/mac/HeyStat/logs/cloudflared-heystat.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/mac/HeyStat/logs/cloudflared-heystat-error.log</string>
    
    <key>ProcessType</key>
    <string>Interactive</string>
</dict>
</plist>
EOF
    
    sudo chown root:wheel "$PLIST_FILE"
    sudo chmod 644 "$PLIST_FILE"
    
    log_info "Service plist created: $PLIST_FILE"
    
    # Load the service
    sudo launchctl load -w "$PLIST_FILE"
    
    log_info "Tunnel service installed and started"
}

# Stop service
stop_service() {
    log_step "Stopping HeyStat tunnel service..."
    
    PLIST_FILE="/Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist"
    
    if [ -f "$PLIST_FILE" ]; then
        sudo launchctl unload "$PLIST_FILE" 2>/dev/null || true
        log_info "Tunnel service stopped"
    else
        log_warn "Service plist not found"
    fi
}

# Show status
show_status() {
    log_step "Checking tunnel status..."
    
    # List tunnels
    echo ""
    log_info "Tunnels:"
    cloudflared tunnel list | grep -E "(ID|$TUNNEL_NAME)" || log_warn "Tunnel not found"
    
    # Check if service is running
    echo ""
    log_info "Service status:"
    if sudo launchctl list | grep -q "com.cloudflare.cloudflared.heystat"; then
        log_info "HeyStat tunnel service is running"
    else
        log_warn "HeyStat tunnel service is not running"
    fi
    
    # Show recent logs
    echo ""
    log_info "Recent logs (last 10 lines):"
    if [ -f "/Users/mac/HeyStat/logs/cloudflared-heystat.log" ]; then
        tail -n 10 "/Users/mac/HeyStat/logs/cloudflared-heystat.log"
    else
        log_warn "No logs found"
    fi
}

# Uninstall
uninstall() {
    log_warn "Uninstalling HeyStat tunnel..."
    
    # Stop service
    stop_service
    
    # Remove plist
    PLIST_FILE="/Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist"
    sudo rm -f "$PLIST_FILE"
    
    # Remove DNS route
    TUNNEL_ID=$(get_tunnel_id)
    cloudflared tunnel route dns delete "$DOMAIN" 2>/dev/null || true
    
    # Optionally delete the tunnel (commented out for safety)
    # cloudflared tunnel delete "$TUNNEL_NAME"
    
    log_info "Tunnel uninstalled (tunnel itself not deleted, use 'cloudflared tunnel delete $TUNNEL_NAME' to remove completely)"
}

# Show usage
usage() {
    cat << EOF
${GREEN}Cloudflare Tunnel Setup for HeyStat${NC}

${YELLOW}Usage:${NC} $0 [command]

${YELLOW}Commands:${NC}
    setup       - Complete setup (create tunnel, config, DNS, service)
    create      - Create tunnel only
    config      - Create configuration file only
    dns         - Setup DNS route only
    test        - Test tunnel connection (interactive)
    install     - Install as LaunchDaemon service
    start       - Start the tunnel service
    stop        - Stop the tunnel service
    restart     - Restart the tunnel service
    status      - Show tunnel status and logs
    uninstall   - Remove tunnel service (keeps tunnel)

${YELLOW}Setup Steps:${NC}
    1. First time: cloudflared tunnel login
    2. Run: $0 setup
    3. Check: $0 status
    4. Access: https://$DOMAIN

${YELLOW}Configuration:${NC}
    Tunnel Name: $TUNNEL_NAME
    Domain: $DOMAIN
    Local Service: $LOCAL_SERVICE
    HTTP Host Header: $HTTP_HOST_HEADER

${YELLOW}Examples:${NC}
    $0 setup        # Complete setup
    $0 test         # Test tunnel before installing
    $0 status       # Check if tunnel is working
    $0 stop         # Stop the tunnel

EOF
}

# Main script logic
case "${1:-}" in
    setup)
        check_cloudflared
        check_login
        create_tunnel
        create_config
        setup_dns
        install_service
        log_info "✓ Setup complete!"
        log_info "Access HeyStat at: https://$DOMAIN"
        log_info "Check status with: $0 status"
        ;;
    create)
        check_cloudflared
        check_login
        create_tunnel
        ;;
    config)
        check_cloudflared
        create_config
        ;;
    dns)
        check_cloudflared
        check_login
        setup_dns
        ;;
    test)
        check_cloudflared
        check_login
        create_config
        test_tunnel
        ;;
    install)
        check_cloudflared
        install_service
        ;;
    start)
        sudo launchctl load -w "/Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist"
        log_info "Tunnel service started"
        ;;
    stop)
        stop_service
        ;;
    restart)
        stop_service
        sleep 2
        sudo launchctl load -w "/Library/LaunchDaemons/com.cloudflare.cloudflared.heystat.plist"
        log_info "Tunnel service restarted"
        ;;
    status)
        check_cloudflared
        show_status
        ;;
    uninstall)
        check_cloudflared
        check_login
        uninstall
        ;;
    *)
        usage
        exit 1
        ;;
esac
