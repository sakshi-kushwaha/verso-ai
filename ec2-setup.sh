#!/bin/bash
# Verso AI — EC2 Setup & Sync Script (Idempotent)
# Target: Ubuntu 24.04, 8 GB RAM, CPU-only
#
# Usage:
#   bash ec2-setup.sh           # Full setup (fresh server)
#   bash ec2-setup.sh --deploy  # Deploy mode (skip Ollama, used by CI/CD)
#
# Safe to run multiple times. Every step checks before acting.
#
# ⚠️  MAINTAINERS: When adding a new system dependency, pip package, TTS model,
#     or data directory — add it HERE. This is the single source of truth.
#     The deploy workflow (deploy.yml) calls this script with --deploy.

set -e

DEPLOY_MODE=false
if [ "$1" = "--deploy" ]; then
    DEPLOY_MODE=true
fi

APP_DIR="/root/verso-ai"
MODELS_DIR="${APP_DIR}/backend/tts/models"
VENV_DIR="${APP_DIR}/backend/venv"
HF_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en"

# ─────────────────────────────────────────────
# Single source of truth: add new deps here
# ─────────────────────────────────────────────
SYSTEM_PACKAGES="python3-pip python3-venv git curl espeak-ng ffmpeg fonts-dejavu-core"

PIPER_MODELS=(
  "en_GB/jenny_dioco/medium:en_GB-jenny_dioco-medium"
  "en_US/libritts_r/medium:en_US-libritts_r-medium"
)

DATA_DIRS=(
  "${APP_DIR}/data/audio_cache"
  "${APP_DIR}/data/video_cache"
  "${APP_DIR}/data/embeddings"
  "${APP_DIR}/data/temp"
  "${MODELS_DIR}"
)
# ─────────────────────────────────────────────

if [ "$DEPLOY_MODE" = true ]; then
    echo "=== Verso AI — Deploy Sync ==="
else
    echo "========================================="
    echo "  Verso AI — Full EC2 Setup (Idempotent)"
    echo "========================================="
fi

# 1. System packages
echo ""
echo "[1] System packages..."
apt update -qq
apt install -y ${SYSTEM_PACKAGES} -qq

# 2. Ollama (skip in deploy mode — already installed)
if [ "$DEPLOY_MODE" = false ]; then
    echo ""
    echo "[2] Ollama..."
    if command -v ollama &> /dev/null; then
        echo "  Already installed"
    else
        curl -fsSL https://ollama.com/install.sh | sh
    fi

    echo "  Waiting for Ollama..."
    sleep 2
    until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
        sleep 3
    done

    # Configure for low memory
    mkdir -p /etc/systemd/system/ollama.service.d
    cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF
    systemctl daemon-reload
    systemctl restart ollama
    sleep 3

    ollama pull qwen2.5:1.5b
    ollama pull qwen2.5:3b
    ollama pull nomic-embed-text
fi

# 3. Data directories
echo ""
echo "[3] Data directories..."
for DIR in "${DATA_DIRS[@]}"; do
    mkdir -p "$DIR"
done
echo "  Done"

# 4. Piper TTS voice models
echo ""
echo "[4] Piper TTS models..."
for MODEL in "${PIPER_MODELS[@]}"; do
    PATH_PART="${MODEL%%:*}"
    NAME="${MODEL##*:}"
    for EXT in ".onnx" ".onnx.json"; do
        DEST="${MODELS_DIR}/${NAME}${EXT}"
        if [ ! -f "$DEST" ]; then
            echo "  Downloading ${NAME}${EXT}..."
            curl -sL "${HF_BASE}/${PATH_PART}/${NAME}${EXT}" -o "$DEST"
        else
            echo "  Already exists: ${NAME}${EXT}"
        fi
    done
done

# 5. Python venv + packages
echo ""
echo "[5] Python packages..."
if [ ! -d "$VENV_DIR" ]; then
    echo "  Creating venv..."
    cd "${APP_DIR}/backend"
    python3 -m venv venv
fi
source "${VENV_DIR}/bin/activate"
pip install --upgrade -r "${APP_DIR}/backend/requirements.txt" --quiet
echo "  Done"

# 6. Deployment diagnostics
echo ""
echo "[6] Deployment diagnostics..."
echo "  Git commit: $(cd ${APP_DIR} && git rev-parse --short HEAD) ($(cd ${APP_DIR} && git log -1 --format='%s'))"
if [ -f "${APP_DIR}/backend/static/index.html" ]; then
    ASSET_HASH=$(grep -oP 'index-[A-Za-z0-9]+\.js' "${APP_DIR}/backend/static/index.html" | head -1)
    echo "  Frontend asset: ${ASSET_HASH:-unknown}"
    echo "  Static dir last modified: $(stat -c '%y' ${APP_DIR}/backend/static/index.html 2>/dev/null || stat -f '%Sm' ${APP_DIR}/backend/static/index.html 2>/dev/null)"
else
    echo "  WARNING: backend/static/index.html not found — frontend may not be deployed"
fi

# Summary
echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Verify:"
echo "  ffmpeg -version"
echo "  python3 -c \"import edge_tts; print('edge-tts ok')\""
echo "  ls ${MODELS_DIR}/*.onnx"
if [ "$DEPLOY_MODE" = false ]; then
    echo "  curl http://localhost:11434/api/tags"
    echo ""
    echo "To run the backend:"
    echo "  cd ${APP_DIR}/backend"
    echo "  source venv/bin/activate"
    echo "  uvicorn main:app --host 0.0.0.0 --port 8000"
    echo ""
    echo "Ports needed: 22 (SSH), 8000 (API + Frontend)"
fi
echo "========================================="
