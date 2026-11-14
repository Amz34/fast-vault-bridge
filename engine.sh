#!/usr/bin/env bash
# Autonomous Enterprise Offloading Engine
# Uses environment variables or config files for queue processing.
set -e

DEST_BASE="${VAULT_DEST_BASE:-ai_vault:AI_VAULT}"
TMPDIR="${VAULT_BUFFER_DIR:-/tmp/vault_pack}"
LOG="${VAULT_LOG_FILE:-/tmp/fast_vault_engine.log}"
mkdir -p "$TMPDIR"
exec >> "$LOG" 2>&1

echo "=========================================================="
echo "=== Fast Vault Engine Stream Started: $(date) ==="
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
        
        echo "[+] $(date): Streaming $NAME.tar.zst to $DEST_BASE/$DIR/..."
        rclone copy "$ZST" "$DEST_BASE/$DIR/" --stats 10s --stats-one-line
        
        echo "[+] $(date): Transfer complete for $NAME. Purging buffer..."
        rm -f "$ZST"
    else
        echo "[-] $(date): Source path not found, skipping: $SRC"
    fi
}

# If queue config is provided, run via python CLI
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${VAULT_CONFIG:-$SCRIPT_DIR/queue.json}" ]; then
    python3 "$SCRIPT_DIR/fast_vault/cli.py" run-queue --config "${VAULT_CONFIG:-$SCRIPT_DIR/queue.json}" --dest "$DEST_BASE"
fi

echo "=========================================================="
echo "=== Fast Vault Engine Stream Completed: $(date) ==="
echo "=========================================================="
