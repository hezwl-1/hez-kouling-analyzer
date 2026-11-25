# One-Prompt AI Setup Guide (`hez-kouling-analyzer`)

This guide lets any AI coding agent (**WorkBuddy, Claude Code, Codex, Cursor, OpenCode, Gemini CLI, Cline**) install and use `hez-kouling-analyzer` in a single turn.

You are the agent reading this file. Execute the steps below yourself. Do not ask the user to copy files by hand.

---

## Copy & Paste Prompt for Users

- **简体中文 (Simplified Chinese)** — 推荐
  ```
  请阅读 https://github.com/hezwl-1/hez-kouling-analyzer/blob/main/AI_INSTALL.md 并帮我安装 hez口令解析分析 技能，然后用它分析我给的 APK 里的口令解析接口。
  ```
- **English**
  ```
  Read https://github.com/hezwl-1/hez-kouling-analyzer/blob/main/AI_INSTALL.md and install hez-kouling-analyzer for me, then use it to find the kouling (share-code) decode API in my APK.
  ```
- **繁體中文 (Traditional Chinese)**
  ```
  請閱讀 https://github.com/hezwl-1/hez-kouling-analyzer/blob/main/AI_INSTALL.md 並幫我安裝 hez口令解析分析 技能，然後用它分析我提供的 APK 口令解析介面。
  ```

---

## What you are installing

A reverse-engineering toolkit for locating the **kouling / share-code decode API** inside an Android APK — the endpoint an app calls after reading the clipboard to turn a pasted string like `1http:/$aqYvQf35171768$ 复zhi口令码打开XX` into a jump URL (deeplink / H5 / `orpheus://`).

It is not a binary and has no dependencies. It is three things:

| Part | What it is |
|---|---|
| `SKILL.md` | The 7-step methodology. **Read this file — it is the actual product.** |
| `scripts/dex_tool.py` | Pure-Python DEX parser. Replaces jadx/apktool entirely. |
| `references/` | A verified case study plus a pattern cheat-sheet for other apps. |

---

## Agent Execution Steps

### Step 1 — Decide which mode applies

Check whether you have shell access and a writable home directory.

- If **yes** → do Step 2 (persistent install). This makes the skill auto-trigger in future sessions.
- If **no** (sandboxed chat, no filesystem) → skip to Step 5 (read-only mode). You can still do the whole job by following `SKILL.md` manually.

### Step 2 — Fetch the repo

Pick whichever works in your environment, in this order:

```bash
# Option A — git clone (preferred)
git clone --depth 1 https://github.com/hezwl-1/hez-kouling-analyzer.git /tmp/hez-kouling-analyzer

# Option B — tarball, no git required
curl -fsSL https://github.com/hezwl-1/hez-kouling-analyzer/archive/refs/heads/main.tar.gz \
  | tar -xz -C /tmp
mv /tmp/hez-kouling-analyzer-main /tmp/hez-kouling-analyzer
```

After this, `/tmp/hez-kouling-analyzer/SKILL.md` must exist. **Verify it before continuing** — if the path is wrong, stop and report rather than guessing.

### Step 3 — Install into the skills directory

Target directory by host:

| Host | Skills root |
|---|---|
| WorkBuddy | `~/.workbuddy-ai/skills/` (`%USERPROFILE%\.workbuddy-ai\skills\` on Windows) |
| Claude Code | `~/.claude/skills/` |
| Codex / other | `~/.config/<agent>/skills/` — if unsure, use `~/.ai-skills/` and tell the user where you put it |

The skill's declared name is `hez口令解析分析` (from the `name:` field in `SKILL.md` frontmatter). Create it under that exact name.

**Copy only the three required items** — do not copy `README.md`, `AI_INSTALL.md`, `web/` or `docs/` into the skills directory:

```bash
SKILL_ROOT="$HOME/.workbuddy-ai/skills"        # adjust per table above
DEST="$SKILL_ROOT/hez口令解析分析"
mkdir -p "$DEST"
cp    /tmp/hez-kouling-analyzer/SKILL.md      "$DEST/"
cp -R /tmp/hez-kouling-analyzer/scripts       "$DEST/"
cp -R /tmp/hez-kouling-analyzer/references    "$DEST/"
```

**If `$DEST` already exists, do not clobber it.** Move it to `$DEST.bak-<timestamp>` first, then copy. Tell the user the backup path. Never `rm -rf` a user's existing skill directory.

### Step 4 — Verify, then report

Run both checks. Do not claim success without them.

```bash
# 4.1 Files landed and SKILL.md is at the right depth (not one level too deep)
test -f "$DEST/SKILL.md" && echo "OK: SKILL.md present" || echo "FAIL: wrong depth"
ls "$DEST/scripts/dex_tool.py" "$DEST/references/patterns.md"

# 4.2 The parser actually runs
python3 "$DEST/scripts/dex_tool.py" 2>&1 | head -12
```

`dex_tool.py` prints its five subcommands when invoked with no arguments. If it errors, the problem is Python, not the install — check `python3 --version` (needs 3.8+).

Then tell the user, in their own language:

1. The skill is installed at `$DEST`.
2. **They must restart their client** (WorkBuddy / Claude Code) so the skill list refreshes.
3. After restart, they can just say *「用 hez口令解析分析 帮我看看这个包的口令接口」* and attach an APK.
4. Trigger words that also work: `口令逆向`, `淘口令接口`, `dpLink`, `shareCode`, `commandCode`, `剪贴板解析`.

### Step 5 — Read-only mode (no filesystem access)

You do not need the install to do the analysis. Instead:

1. Fetch and read `SKILL.md` — it contains the full 7-step method.
2. Fetch `references/patterns.md` — regex patterns, field names, gateway prefixes per vendor.
3. Fetch `scripts/dex_tool.py` if you can run Python, or reimplement its two core operations yourself: **enumerate DEX strings**, then **find which methods contain a `const-string` referencing a given string index**, then **disassemble that method**.
4. Follow the method by hand.

Tell the user you are operating without a persistent install, so the method will not auto-trigger next time.

---

## The method in one paragraph

Do **not** grep for API paths — kouling endpoints are routinely disguised as unrelated features (the NetEase Cloud Music one is `password/url/decode/get`, which reads like a password-change API).

Instead: **extract the target's regular expression, find which class references that string, disassemble it, and walk the call chain.** Kouling detection is almost always implemented as a regex format check, and strings are never obfuscated even when every class and method name is. That asymmetry is the whole technique — it survives ProGuard, R8, and even most string-folding schemes.

Full details, including the two traps that cost the most time, are in `SKILL.md`.

---

## Uninstall

```bash
SKILL_ROOT="$HOME/.workbuddy-ai/skills"
mv "$SKILL_ROOT/hez口令解析分析" "$SKILL_ROOT/hez口令解析分析.removed-$(date +%s)"
```

Nothing outside that directory is touched. There is no daemon, no registry entry, no background process.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Skill not listed after restart | `SKILL.md` is nested one level too deep | Must be `skills/hez口令解析分析/SKILL.md`, never `.../hez口令解析分析/hez口令解析分析/SKILL.md` |
| `python3: command not found` | No Python | Try `python`, `py -3` (Windows), or run in read-only mode |
| `dex_tool.py` prints nothing | Ran with a subcommand but no args | Run bare: `python3 dex_tool.py` |
| Garbled Chinese in console | Windows codepage | Cosmetic only — files are UTF-8. Run `chcp 65001` |
| `find` returns 0 hits | Keyword escaping mismatch | Grep the exported `strs/*.txt` first to confirm the literal string exists, then `find` |

---

## Scope & fair use

This toolkit is for **protocol analysis and security research** on apps you are entitled to inspect. Do not use it to scrape, to farm activity rewards at scale, or to bypass access controls. Respect the target service's terms.