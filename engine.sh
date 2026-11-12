#!/bin/bash
# Autonomous Enterprise 100GB Offloading Engine
LOG="/home/ubuntu/fast_vault_engine.log"
exec >> "$LOG" 2>&1

echo "=========================================================="
echo "=== Fast Vault Engine Stream Started: $(date) ==="
echo "=========================================================="

stream_item() {
    SRC="$1"
    NAME="$2"
    DIR="$3"
    
    if [ -e "$SRC" ]; then
        ZST="/tmp/vault_pack/$NAME.tar.zst"
        echo "[+] $(date): Compressing $SRC -> $NAME.tar.zst..."
        tar --exclude="node_modules" --exclude=".venv" --exclude="venv" --exclude="__pycache__" -cf - -C "$(dirname "$SRC")" "$(basename "$SRC")" \
            | zstd -1 -T4 -o "$ZST"
        
        echo "[+] $(date): Streaming $NAME.tar.zst to Toshiba HD (ai_vault:AI_VAULT/$DIR/)..."
        rclone copy "$ZST" "ai_vault:AI_VAULT/$DIR/" --stats 10s --stats-one-line
        
        echo "[+] $(date): Transfer complete for $NAME. Purging buffer..."
        rm -f "$ZST"
    fi
}

# Pipeline Execution:
stream_item "/home/ubuntu/projects/artemis" "artemis" "projects_archive"
stream_item "/home/ubuntu/infra-recovery-vault/.git" "infra_git_history" "infra_archives"
stream_item "/home/ubuntu/clients/AVVS-Triatek" "avvs_triatek" "clients_archive"
stream_item "/home/ubuntu/scraping-suite" "scraping_suite" "tools_archive"
stream_item "/home/ubuntu/tools" "ubuntu_tools" "tools_archive"
stream_item "/home/ubuntu/projects/geo-auditor" "geo_auditor" "projects_archive"
stream_item "/home/ubuntu/projects/ai-data-analyst" "ai_data_analyst" "projects_archive"
stream_item "/home/ubuntu/.rustup" "rustup_toolchains" "sdks_archive"
stream_item "/home/ubuntu/google-cloud-sdk" "gcloud_sdk" "sdks_archive"

echo "=========================================================="
echo "=== Fast Vault Engine Stream Completed: $(date) ==="
echo "=========================================================="
