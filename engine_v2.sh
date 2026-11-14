#!/usr/bin/env bash
# Enterprise Fast Vault Multi-Process Streamer
# Non-blocking, Auto-recovering, High-Throughput
set -e

DEST_BASE="${VAULT_DEST_BASE:-ai_vault:AI_VAULT}"
TMPDIR="${VAULT_BUFFER_DIR:-/tmp/vault_pack}"
LOG="${VAULT_LOG_FILE:-/tmp/fast_vault_engine.log}"
mkdir -p "$TMPDIR"
exec >> "$LOG" 2>&1

echo "=========================================================="
echo "=== Fast Vault Engine V2 Live: $(date) ==="
echo "=========================================================="

stream_item() {
    SRC="$1"
    NAME="$2"
    DIR="${3:-projects_archive}"
    
    if [ -e "$SRC" ]; then
        ZST="$TMPDIR/$NAME.tar.zst"
        echo "[+] $(date): Compressing $SRC -> $NAME.tar.zst..."
        tar --exclude="node_modules" --exclude=".venv" --exclude="venv" --exclude="__pycache__" -cf - -C "$(dirname "$SRC")" "$(basename "$SRC")" \
            | zstd -1 -T4 -o "$ZST"
        
        echo "[+] $(date): Streaming $NAME.tar.zst ($ZST) to $DEST_BASE/$DIR/..."
        rclone copy "$ZST" "$DEST_BASE/$DIR/" --stats 5s --stats-one-line
        
        echo "[+] $(date): Finished $NAME. Purging temp buffer..."
        rm -f "$ZST"
    else
        echo "[-] $(date): Source path not found, skipping: $SRC"
    fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${VAULT_CONFIG:-$SCRIPT_DIR/queue.json}" ]; then
    python3 "$SCRIPT_DIR/fast_vault/cli.py" run-queue --config "${VAULT_CONFIG:-$SCRIPT_DIR/queue.json}" --dest "$DEST_BASE"
fi

echo "=========================================================="
echo "=== Fast Vault Engine V2 Finished: $(date) ==="
echo "=========================================================="
