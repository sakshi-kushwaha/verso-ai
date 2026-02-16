#!/bin/bash
# Verso AI — EC2 Native Setup Script (Lightweight, No Docker, No Node.js)
# Target: Ubuntu 24.04, 8 GB RAM, CPU-only
# Run as root: bash ec2-setup.sh

set -e

echo "========================================="
echo "  Verso AI — Lightweight EC2 Setup"
echo "========================================="

# 1. System update + dependencies
echo "[1/5] Installing system dependencies..."
apt update && apt install -y python3-pip python3-venv git curl espeak-ng

# 2. Install Ollama
echo "[2/5] Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
sleep 5
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    echo "  Waiting..."
    sleep 3
done

# 3. Configure Ollama for low memory
echo "[3/5] Configuring Ollama (NUM_PARALLEL=1)..."
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
systemctl daemon-reload
systemctl restart ollama
sleep 3

# 4. Pull AI models
echo "[4/5] Pulling AI models..."
ollama pull qwen2.5:3b
ollama pull nomic-embed-text

# 5. Create data directories
echo "[5/5] Creating data directories..."
mkdir -p /root/verso-ai/data/audio_cache
mkdir -p /root/verso-ai/data/temp

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Verify:"
echo "  curl http://localhost:11434/api/tags"
echo "  python3 --version"
echo "  espeak-ng --version"
echo ""
echo "To run the backend:"
echo "  cd /root/verso-ai/backend"
echo "  python3 -m venv venv && source venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "  uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "Frontend: build locally (npm run build), copy dist/ to backend/static/"
echo "FastAPI serves it automatically — no Node.js needed on EC2."
echo ""
echo "Ports needed: 22 (SSH), 8000 (API + Frontend)"
echo "========================================="
