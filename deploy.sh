#!/bin/bash
# Deployment script for Claude Astro Brain Rider
# Usage: ./scripts/deploy.sh [--restart] [--full]

set -e

# Configuration
PI_HOST="${PI_HOST:-cowboy-claude.local}"
PI_USER="${PI_USER:-cowboy}"
PI_PROJECT_DIR="${PI_PROJECT_DIR:-/home/cowboy/claude-astro-brain-rider}"

# Parse arguments
RESTART=false
FULL=false
INSTALL_DEPS=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --restart|-r)
      RESTART=true
      shift
      ;;
    --full|-f)
      FULL=true
      shift
      ;;
    --install-deps|-i)
      INSTALL_DEPS=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--restart] [--full]"
      exit 1
      ;;
  esac
done

# Validate connection
echo "🔍 Validating connection to $PI_USER@$PI_HOST..."
if ! ssh -o ConnectTimeout=5 "$PI_USER@$PI_HOST" "echo 'Connection successful'" > /dev/null 2>&1; then
  echo "❌ Cannot connect to $PI_USER@$PI_HOST"
  echo "   Please check:"
  echo "   - Pi is powered on and connected to network"
  echo "   - Hostname resolves correctly (try: ping $PI_HOST)"
  echo "   - SSH key is set up (try: ssh $PI_USER@$PI_HOST)"
  exit 1
fi

# Deploy files
if [ "$FULL" = true ]; then
  echo "🚀 Deploying all files to $PI_USER@$PI_HOST..."
  rsync -avz --progress \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude '3d-design/' \
    --exclude 'docs/' \
    --exclude '.git/' \
    --exclude '.agent/' \
    src/ config/ requirements.txt mise.toml systemd/ scripts/ \
    "$PI_USER@$PI_HOST:$PI_PROJECT_DIR/"
else
  echo "🚀 Deploying src/ to $PI_USER@$PI_HOST..."
  rsync -avz --progress \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    src/ "$PI_USER@$PI_HOST:$PI_PROJECT_DIR/src/"
fi


# Install dependencies if requested
if [ "$INSTALL_DEPS" = true ]; then
  echo "📦 Installing dependencies on $PI_USER@$PI_HOST..."
  ssh "$PI_USER@$PI_HOST" "cd $PI_PROJECT_DIR && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  echo "✅ Dependencies installed"
fi

# Restart service if requested
if [ "$RESTART" = true ]; then
  echo ""
  echo "🔄 Restarting brain-rider service..."
  
  if ssh "$PI_USER@$PI_HOST" "sudo systemctl restart brain-rider" 2>/dev/null; then
    sleep 2
    
    # Check service status
    if ssh "$PI_USER@$PI_HOST" "sudo systemctl is-active brain-rider" > /dev/null 2>&1; then
      echo "✅ Service restarted successfully"
      echo ""
      echo "📊 Service status:"
      ssh "$PI_USER@$PI_HOST" "sudo systemctl status brain-rider --no-pager -l" || true
    else
      echo "❌ Service failed to start"
      echo ""
      echo "📋 Recent logs:"
      ssh "$PI_USER@$PI_HOST" "sudo journalctl -u brain-rider -n 20 --no-pager" || true
      exit 1
    fi
  else
    echo "⚠️  Could not restart service (may not be installed yet)"
    echo "   Run setup_pi.sh on the Pi to install the systemd service"
  fi
fi

echo ""
echo "💡 Next steps:"
if [ "$RESTART" = false ]; then
  echo "   - Restart service: ssh $PI_USER@$PI_HOST 'sudo systemctl restart brain-rider'"
fi
echo "   - View logs: ssh $PI_USER@$PI_HOST 'sudo journalctl -u brain-rider -f'"
echo "   - Check status: ssh $PI_USER@$PI_HOST 'sudo systemctl status brain-rider'"
