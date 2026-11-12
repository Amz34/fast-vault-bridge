#!/bin/bash
# Enterprise Fast Vault Streamer
set -e

DEST_BASE="ai_vault:AI_VAULT"
TMPDIR="/tmp/vault_pack"
mkdir -p "$TMPDIR"

stream_payload() {
    SRC="$1"
    NAME="$2"
    CATEGORY="$3"
    
    if [ -e "$SRC" ]; then
        ZST="$TMPDIR/${NAME}.tar.zst"
        echo "[BRIDGE] Packing $SRC -> ${NAME}.tar.zst..."
        tar --exclude="node_modules" --exclude=".venv" --exclude="venv" --exclude="__pycache__" \
            -cf - -C "$(dirname "$SRC")" "$(basename "$SRC")" \
            | zstd -1 -T4 -o "$ZST"
        
        echo "[BRIDGE] Streaming to $DEST_BASE/$CATEGORY/..."
        rclone copy "$ZST" "$DEST_BASE/$CATEGORY/" --stats 10s --stats-one-line
        
        echo "[BRIDGE] Verifying and cleaning local buffer..."
        rm -f "$ZST"
        echo "[BRIDGE] Completed $NAME successfully."
    fi
}

echo "=== Fast Vault Bridge Operational ==="
