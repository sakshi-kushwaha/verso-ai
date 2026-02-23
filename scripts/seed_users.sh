#!/bin/bash
# Verso AI — Seed Users & Upload PDFs (Idempotent)
# Runs directly on EC2 server (no Docker)
#
# Usage:  bash ~/verso-ai/scripts/seed_users.sh
#
# PDF folders expected:
#   backend/explorer/      → Sanika (explorer/learning)
#   backend/student/       → Esha (student/exam)
#   backend/professional/  → Sakshi (professional/work)

set -e

API="http://localhost:8000"
APP_DIR="/root/verso-ai"
BACKEND_DIR="${APP_DIR}/backend"
DB_PATH="${BACKEND_DIR}/data/verso.db"
VENV="${BACKEND_DIR}/venv/bin/python3"

# ─────────────────────────────────────────────
# User definitions:  name|password|use_case|folder
# ─────────────────────────────────────────────
USERS=(
  "Sanika|Test@123|learning|explorer"
  "Esha|Test@123|exam|student"
  "Sakshi|Test@123|work|professional"
)

echo "========================================="
echo "  Verso AI — Seed Users & Uploads"
echo "========================================="

for ENTRY in "${USERS[@]}"; do
    IFS='|' read -r NAME PASSWORD USE_CASE FOLDER <<< "$ENTRY"

    echo ""
    echo "── ${NAME} (${USE_CASE}) ── folder: ${FOLDER}/"

    # 1. Signup or login
    echo -n "  [1] Auth... "
    RESP=$(curl -s -X POST "${API}/auth/signup" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"${NAME}\", \"password\": \"${PASSWORD}\"}")
    TOKEN=$(echo "$RESP" | $VENV -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
    REFRESH=$(echo "$RESP" | $VENV -c "import sys,json; print(json.load(sys.stdin).get('refresh_token',''))" 2>/dev/null)

    if [ -z "$TOKEN" ]; then
        RESP=$(curl -s -X POST "${API}/auth/login" \
            -H "Content-Type: application/json" \
            -d "{\"name\": \"${NAME}\", \"password\": \"${PASSWORD}\"}")
        TOKEN=$(echo "$RESP" | $VENV -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
        REFRESH=$(echo "$RESP" | $VENV -c "import sys,json; print(json.load(sys.stdin).get('refresh_token',''))" 2>/dev/null)
        if [ -z "$TOKEN" ]; then
            echo "FAILED"
            echo "  $RESP"
            continue
        fi
        echo "logged in (exists)"
    else
        echo "signed up"
    fi

    # Helpers: refresh token proactively (rotate access+refresh)
    last_refresh_ts=$(date +%s)
    refresh_tokens() {
        if [ -z "$REFRESH" ]; then
            return
        fi
        local R
        R=$(curl -s -X POST "${API}/auth/refresh" \
            -H "Content-Type: application/json" \
            -d "{\"refresh_token\": \"${REFRESH}\"}")
        local NEWTOK NEWREF
        NEWTOK=$(echo "$R" | $VENV -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
        NEWREF=$(echo "$R" | $VENV -c "import sys,json; print(json.load(sys.stdin).get('refresh_token',''))" 2>/dev/null)
        if [ -n "$NEWTOK" ] && [ -n "$NEWREF" ]; then
            TOKEN="$NEWTOK"
            REFRESH="$NEWREF"
            last_refresh_ts=$(date +%s)
        fi
    }

    ensure_fresh_token() {
        # Refresh every 25 minutes to avoid hitting the 30-minute access token expiry
        local now ts_diff
        now=$(date +%s)
        ts_diff=$((now - last_refresh_ts))
        if [ $ts_diff -ge 1500 ]; then
            refresh_tokens
        fi
    }

    # 2. Set use_case preference directly in DB
    echo -n "  [2] Preferences... "
    $VENV -c "
import sqlite3
conn = sqlite3.connect('${DB_PATH}')
conn.execute(
    'UPDATE user_preferences SET use_case = ? WHERE user_id = (SELECT id FROM users WHERE name = ?)',
    ('${USE_CASE}', '${NAME}')
)
conn.commit()
conn.close()
print('${USE_CASE} set')
"

    # 3. Get already-uploaded filenames
    ensure_fresh_token
    EXISTING=$(curl -s "${API}/uploads" -H "Authorization: Bearer ${TOKEN}" | \
        $VENV -c "
import sys,json
try:
    for u in json.load(sys.stdin): print(u.get('filename',''))
except: pass
" 2>/dev/null)

    # 4. Upload PDFs
    PDF_DIR="${BACKEND_DIR}/${FOLDER}"
    if [ ! -d "$PDF_DIR" ]; then
        echo "  [3] No folder ${PDF_DIR}, skipping"
        continue
    fi

    PDF_COUNT=$(ls "$PDF_DIR"/*.pdf 2>/dev/null | wc -l | tr -d ' ')
    echo "  [3] Uploading ${PDF_COUNT} PDFs from ${FOLDER}/"

    for PDF in "$PDF_DIR"/*.pdf; do
        [ ! -f "$PDF" ] && continue
        BASENAME=$(basename "$PDF")

        if echo "$EXISTING" | grep -qF "$BASENAME"; then
            echo "      skip  ${BASENAME} (already uploaded)"
            continue
        fi

        ensure_fresh_token
        echo -n "      up    ${BASENAME}... "
        UP_RESP=$(curl -s -X POST "${API}/upload" \
            -H "Authorization: Bearer ${TOKEN}" \
            -F "file=@${PDF}")

        UP_ID=$(echo "$UP_RESP" | $VENV -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)

        if [ -z "$UP_ID" ]; then
            echo "FAILED: ${UP_RESP}"
            continue
        fi
        echo "id=${UP_ID}, pipeline running"

        # Wait for pipeline (one upload at a time per user)
        echo -n "            waiting... "
        WAITED=0
        # Also periodically refresh access token while waiting
        while [ $WAITED -lt 1200 ]; do
            sleep 10
            WAITED=$((WAITED + 10))
            # proactive refresh every 5 minutes
            if [ $((WAITED % 300)) -eq 0 ]; then
                ensure_fresh_token
            fi

            RAW=$(curl -s "${API}/upload/status/${UP_ID}" -H "Authorization: Bearer ${TOKEN}")
            # If token expired, rotate and retry once
            if echo "$RAW" | grep -q "Token expired"; then
                refresh_tokens
                RAW=$(curl -s "${API}/upload/status/${UP_ID}" -H "Authorization: Bearer ${TOKEN}")
            fi
            STATUS=$(echo "$RAW" | $VENV -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null)

            if [ "$STATUS" = "done" ]; then
                REELS=$(curl -s "${API}/upload/status/${UP_ID}" \
                    -H "Authorization: Bearer ${TOKEN}" | \
                    $VENV -c "import sys,json; print(json.load(sys.stdin).get('reels_generated',0))" 2>/dev/null)
                echo "done (${REELS} reels, ${WAITED}s)"
                break
            elif [ "$STATUS" = "error" ]; then
                echo "error (${WAITED}s)"
                break
            fi

            [ $((WAITED % 30)) -eq 0 ] && echo -n "${WAITED}s "
        done

        [ $WAITED -ge 1200 ] && echo "timeout (1200s)"
        # After each upload (done/timeout/error), refresh tokens for safety
        refresh_tokens
    done
done

echo ""
echo "========================================="
echo "  Done!"
echo "========================================="
