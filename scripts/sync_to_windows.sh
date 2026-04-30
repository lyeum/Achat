#!/bin/bash
# sync_to_windows.sh — WSL → C:\Achat 빠른 동기화
#
# 사용법:
#   bash scripts/sync_to_windows.sh [--dest /mnt/c/Achat]
#
# 동기화 범위:
#   - 소스 코드 (Python, QML 등)
#   - ui_ux/assets/ (characters, icons, background — gitignore 대상이지만 배포 포함)
#
# 제외 항목:
#   - .venv, models/, chroma_deploy/  (설치본이 보유)
#   - ui_ux/assets/preferences.json   (사용자 설정 — 덮어쓰지 않음)
#   - data/sessions/, training/, docs/, tests/

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-/mnt/c/Achat}"

if [[ "$1" == "--dest" ]]; then
    DEST="$2"
fi

if [[ ! -d "$DEST" ]]; then
    echo "오류: 대상 경로 없음: $DEST" >&2
    exit 1
fi

echo "[sync] $ROOT → $DEST"

# ── 소스 코드 동기화 ────────────────────────────────────────────────────────
rsync -a --checksum \
         --exclude='__pycache__' \
         --exclude='*.pyc' \
         --exclude='.venv' \
         --exclude='.git' \
         --exclude='output/' \
         --exclude='training/' \
         --exclude='tests/' \
         --exclude='docs/' \
         --exclude='chroma_dev/' \
         --exclude='chroma_verify/' \
         --exclude='chroma_deploy/' \
         --exclude='data/' \
         --exclude='dist/' \
         --exclude='*.log' \
         --exclude='*.gguf' \
         --exclude='models/' \
         --exclude='pyproject-deploy.toml' \
         --exclude='ui_ux/assets/' \
         "$ROOT/" "$DEST/"

# ── assets 별도 동기화 (gitignore 우회) ───────────────────────────────────
echo "[sync] assets..."
rsync -a --checksum \
         --exclude='preferences.json' \
         "$ROOT/ui_ux/assets/" "$DEST/ui_ux/assets/"

# ── chroma_deploy 동기화 (prompt_guides 등 사전 시딩 포함) ─────────────────
if [[ -d "$ROOT/chroma_deploy" ]]; then
    echo "[sync] chroma_deploy..."
    rsync -a --checksum "$ROOT/chroma_deploy/" "$DEST/chroma_deploy/"
fi

echo "[sync] 완료"
