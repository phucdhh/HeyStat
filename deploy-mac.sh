#!/bin/bash
# HeyStat Deployment Script for Mac Mini M2
# This script sets up and manages HeyStat service on macOS

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/Users/mac/HeyStat"
NGINX_CONF="/opt/homebrew/etc/nginx/nginx.conf"
HEYSTAT_NGINX_CONF="$PROJECT_DIR/heystat-nginx-mac.conf"
LAUNCHDAEMON_SOURCE="$PROJECT_DIR/launch-daemons/com.heystat.docker.plist"
LAUNCHDAEMON_DEST="/Library/LaunchDaemons/com.heystat.docker.plist"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        log_error "This script must be run with sudo for system configuration"
        exit 1
    fi
}

# Create logs directory
setup_logs() {
    log_info "Creating logs directory..."
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "/opt/homebrew/var/log/nginx"
    chown -R mac:staff "$PROJECT_DIR/logs"
}

# Setup Nginx configuration
setup_nginx() {
    log_info "Setting up Nginx configuration..."
    
    # Check if nginx is installed
    if ! command -v nginx &> /dev/null; then
        log_error "Nginx is not installed. Please install with: brew install nginx"
        exit 1
    fi
    
    # Check if our config is already included
    if grep -q "heystat-nginx-mac.conf" "$NGINX_CONF"; then
        log_info "HeyStat Nginx config already included in nginx.conf"
    else
        log_info "Adding HeyStat config to nginx.conf..."
        # Add include directive before the last closing brace
        sed -i.backup '/^}$/i\    include '"$HEYSTAT_NGINX_CONF"';' "$NGINX_CONF"
        log_info "Backup created: $NGINX_CONF.backup"
    fi
    
    # Test nginx configuration
    if nginx -t 2>&1 | grep -q "successful"; then
        log_info "Nginx configuration test passed"
        
        # Reload nginx
        if brew services list | grep -q "nginx.*started"; then
            log_info "Reloading Nginx..."
            brew services restart nginx
        else
            log_info "Starting Nginx..."
            brew services start nginx
        fi
    else
        log_error "Nginx configuration test failed"
        nginx -t
        exit 1
    fi
}

# Setup Docker service
setup_docker() {
    log_info "Setting up Docker service..."
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker Desktop for Mac"
        exit 1
    fi
    
    # Copy LaunchDaemon plist
    cp "$LAUNCHDAEMON_SOURCE" "$LAUNCHDAEMON_DEST"
    chown root:wheel "$LAUNCHDAEMON_DEST"
    chmod 644 "$LAUNCHDAEMON_DEST"
    
    log_info "LaunchDaemon installed at $LAUNCHDAEMON_DEST"
}

# Build Docker images
build_docker() {
    log_info "Building Docker images..."
    cd "$PROJECT_DIR"
    
    # Build with Mac M2 architecture
    su - mac -c "cd $PROJECT_DIR && docker compose build --platform linux/arm64"
    
    log_info "Docker images built successfully"
}

# Start HeyStat service
start_service() {
    log_info "Starting HeyStat service..."
    
    # Load the LaunchDaemon
    launchctl load -w "$LAUNCHDAEMON_DEST" 2>/dev/null || true
    
    # Or start with docker compose directly
    log_info "Starting with docker compose..."
    cd "$PROJECT_DIR"
    su - mac -c "cd $PROJECT_DIR && docker compose up -d"
    
    log_info "HeyStat service started"
}

# Stop HeyStat service
stop_service() {
    log_info "Stopping HeyStat service..."
    
    # Stop docker compose
    cd "$PROJECT_DIR"
    su - mac -c "cd $PROJECT_DIR && docker compose down" || true
    
    # Unload LaunchDaemon
    launchctl unload "$LAUNCHDAEMON_DEST" 2>/dev/null || true
    
    log_info "HeyStat service stopped"
}

# Check service status
check_status() {
    log_info "Checking HeyStat status..."
    
    # Check docker containers
    docker ps --filter "name=heystat" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    # Check nginx
    if brew services list | grep -q "nginx.*started"; then
        log_info "Nginx is running"
    else
        log_warn "Nginx is not running"
    fi
    
    # Check if ports are listening
    log_info "Checking ports..."
    lsof -iTCP:42337 -sTCP:LISTEN || log_warn "Port 42337 not listening"
    lsof -iTCP:8082 -sTCP:LISTEN || log_warn "Port 8082 not listening"
}

# Uninstall HeyStat
uninstall() {
    log_warn "Uninstalling HeyStat..."
    
    # Stop service first
    stop_service
    
    # Remove LaunchDaemon
    rm -f "$LAUNCHDAEMON_DEST"
    
    # Remove nginx config include (restore backup)
    if [ -f "$NGINX_CONF.backup" ]; then
        mv "$NGINX_CONF.backup" "$NGINX_CONF"
        brew services restart nginx
    fi
    
    log_info "HeyStat uninstalled"
}

# Show usage
usage() {
    cat << EOF
HeyStat Deployment Script for Mac Mini M2

Usage: sudo $0 [command]

Commands:
    setup       - Complete setup (nginx, docker, build)
    build       - Build Docker images only
    start       - Start HeyStat service
    stop        - Stop HeyStat service
    restart     - Restart HeyStat service
    status      - Check service status
    logs        - Show Docker logs
    uninstall   - Remove HeyStat completely

Examples:
    sudo $0 setup
    sudo $0 start
    sudo $0 status
    sudo $0 logs

EOF
}

# Main script logic
case "${1:-}" in
    setup)
        check_root
        setup_logs
        setup_nginx
        setup_docker
        build_docker
        start_service
        log_info "HeyStat setup completed!"
        log_info "Access at: http://localhost:8082"
        log_info "After Cloudflare setup: https://heystat.truyenthong.edu.vn"
        ;;
    build)
        check_root
        build_docker
        ;;
    start)
        check_root
        start_service
        ;;
    stop)
        check_root
        stop_service
        ;;
    restart)
        check_root
        stop_service
        sleep 2
        start_service
        ;;
    status)
        check_status
        ;;
    logs)
        cd "$PROJECT_DIR"
        docker compose logs -f
        ;;
    uninstall)
        check_root
        uninstall
        ;;
    *)
        usage
        exit 1
        ;;
esac
