#!/bin/sh
# hez-kouling-analyzer installer (macOS / Linux)
set -eu

SKILL_NAME="hez口令解析分析"
SRC="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$SRC/SKILL.md" ]; then
    echo "[ERROR] SKILL.md not found next to this script." >&2
    echo "        Run install.sh from inside the cloned repository." >&2
    exit 1
fi

# Honour an explicit override, otherwise pick the first client detected.
if [ -n "${SKILL_ROOT:-}" ]; then
    ROOT="$SKILL_ROOT"
elif [ -d "$HOME/.workbuddy-ai" ]; then
    ROOT="$HOME/.workbuddy-ai/skills"
elif [ -d "$HOME/.claude" ]; then
    ROOT="$HOME/.claude/skills"
else
    ROOT="$HOME/.workbuddy-ai/skills"
fi

DEST="$ROOT/$SKILL_NAME"

echo "Source : $SRC"
echo "Target : $DEST"
echo

mkdir -p "$ROOT"

# Back up rather than clobber. Never rm -rf a user's existing skill.
if [ -e "$DEST" ]; then
    printf "An existing install was found. Back it up and replace? (y/N) "
    read -r ans
    case "$ans" in
        [yY]*) ;;
        *) echo "Cancelled."; exit 0 ;;
    esac
    BAK="$DEST.bak-$(date +%Y%m%d-%H%M%S)"
    mv "$DEST" "$BAK"
    echo "Backed up to: $BAK"
fi

mkdir -p "$DEST"
cp    "$SRC/SKILL.md"   "$DEST/"
cp -R "$SRC/scripts"    "$DEST/"
cp -R "$SRC/references" "$DEST/"

echo
if [ -f "$DEST/SKILL.md" ] && [ -f "$DEST/scripts/dex_tool.py" ]; then
    echo "[OK] Installed to $DEST"
    echo
    echo "Next:"
    echo "  1. Restart your client so the skill list refreshes"
    echo "  2. Say: 用 hez口令解析分析 帮我看看这个包的口令接口"
    echo
    echo "Verify the parser:"
    python3 "$DEST/scripts/dex_tool.py" 2>&1 | head -8 || \
        echo "  (python3 not found - try python, or use read-only mode)"
else
    echo "[FAIL] Copy did not complete. Check permissions on $ROOT" >&2
    exit 1
fi