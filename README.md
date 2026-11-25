<div align="center">

# hez-kouling-analyzer

**从 Android APK 里逆向定位「口令解析接口」——那个把剪贴板里的分享码变成跳转地址的 API。**

反向工程工具包 · 纯 Python · 零第三方依赖 · 不需要 jadx / apktool / Frida

<p>
  <b>简体中文</b> ·
  <a href="#one-prompt-ai-install">AI 一键安装</a> ·
  <a href="#实战案例网易云音乐">实战案例</a> ·
  <a href="#方法论">方法论</a>
</p>

<p>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat-square" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.8+" />
  <img src="https://img.shields.io/badge/deps-zero-34D399?style=flat-square" alt="Zero dependencies" />
</p>

</div>

---

## 这是什么

用户复制一段形如下面的文本，打开 App 就自动跳转到活动页：

```
08:06 1http:/$aqYvQf35171768$ 02/04/1990 SC8986  复zhi口令码打开网易☁音乐，
参与星火计划，领取你的星火福利！
```

App 是怎么把它变成一个 URL 的？走的是哪个接口？参数怎么加密？

这个工具包就是回答这三个问题的。它给你一套经过实战验证的定位方法，加上一个能替代 jadx 的 DEX 解析器。

**适用场景**

- 想知道某个 App 的口令功能调用哪个后端接口
- 需要还原口令解码协议，自己算 `decodedUrl`
- 逆向剪贴板识别逻辑
- 学习 Android 逆向：不用装一堆重型工具，一个 Python 文件就能读 DEX

---

## One-Prompt AI Install

装给 AI 用 —— 复制下面这句给你的 AI 助手（WorkBuddy / Claude Code / Cursor / Codex 都行），它会自己读完安装文档并装好：

```
请阅读 https://github.com/hezwl-1/hez-kouling-analyzer/blob/main/AI_INSTALL.md 并帮我安装 hez口令解析分析 技能，然后用它分析我给的 APK 里的口令解析接口。
```

英文版：

```
Read https://github.com/hezwl-1/hez-kouling-analyzer/blob/main/AI_INSTALL.md and install hez-kouling-analyzer for me.
```

安装文档是写给 AI 执行的，包含前置判断、三种安装路径（git / tarball / 只读模式）、覆盖前的备份要求、验证命令和排错表。人也可以照着做。

### 手动安装（人看这份）

```bash
git clone --depth 1 https://github.com/hezwl-1/hez-kouling-analyzer.git /tmp/hka

DEST="$HOME/.workbuddy-ai/skills/hez口令解析分析"    # 按你的客户端改
mkdir -p "$DEST"
cp    /tmp/hka/SKILL.md   "$DEST/"
cp -R /tmp/hka/scripts    "$DEST/"
cp -R /tmp/hka/references "$DEST/"
```

Windows 用 `%USERPROFILE%\.workbuddy-ai\skills\`，或直接双击仓库里的 `install.cmd`。

装完**重启客户端**，技能列表才会刷新。

> **关键**：`SKILL.md` 必须直接位于 `hez口令解析分析/` 下。多套一层文件夹是最常见的失败原因。

---

## 不用安装，直接跑

DEX 解析器是独立的，不依赖技能安装，任何时候都能单独用：

```bash
# 解包 APK
unzip -o -q app.apk "*.dex" -d ex/

# 看它能干什么
python3 scripts/dex_tool.py

# 导出全量字符串（32MB 级别也能处理，实测 21 dex / 190MB）
python3 scripts/dex_tool.py strings ex/

# ★ 核心：字符串反查引用类
python3 scripts/dex_tool.py find ex/ '.*\$.+\$.*'

# 反汇编某个方法
python3 scripts/dex_tool.py disasm ex/classes18.dex 'Lt50/p;' 'm'

# 列出类的所有方法
python3 scripts/dex_tool.py methods ex/classes17.dex 'Lcom/netease/cloudmusic/meta/AppTokenInfo;'
```

---

## 方法论

一句话版：

> **搜口令里的特殊字符 → 找到正则 → 反查引用它的类 → 反汇编 → 顺调用链找到接口**

为什么不是直接搜 API 路径？

因为**口令接口的路径通常伪装成别的功能**。网易云那个接口叫 `password/url/decode/get` —— 看名字像改密码，实际上 `encodedPassword` 参数收的是整段口令。按关键词 `kouling` / `command` / `share` 去搜，一条都搜不到。

为什么搜字符串有效？

因为**代码可以混淆，字符串不行**。类名方法名全被压成 `t50/p`、`d32/e` 这种，但正则、参数名、接口路径都是明文常量。这个不对称就是整个方法的立足点。

### 七步流程

| 步 | 动作 | 产出 |
|---|---|---|
| 1 | 解包，记录 dex 数量与包名 | 素材 |
| 2 | 导出全量字符串，按优先级检索 | 候选线索 |
| 3 | `find` 反查字符串的引用类 | 命中方法 |
| 4 | `disasm` 反汇编，跟 `invoke` 走 | 调用链 |
| 5 | 确认参数名与返回模型 | 字段结构 |
| 6 | 确认网关域名与加密方案 | 协议 |
| 7 | 实测调通 | 真实 URL |

第 2 步的检索优先级（按命中率排序）：

1. **口令里的特殊字符** —— `$`、`¥`、`￥`。大概率就是正则里的分隔符
2. 中文提示文案 —— 「复制」「打开」「口令」「星火」
3. 剪贴板 API —— `getPrimaryClip`、`ClipboardManager`
4. 返回字段名 —— `decodedUrl`、`jumpUrl`、`scheme`
5. API 路径 —— 最后手段，因为最可能是伪装的

完整版含排错表和踩坑记录：见 [`SKILL.md`](./SKILL.md)。

---

## 实战案例：网易云音乐

样本 190MB / 21 dex，全程无 jadx、无 apktool、无 Frida。

**接口**

```
POST https://interface.music.163.com/eapi/password/url/decode/get
     params = eapi_encrypt({ encodedPassword: <口令全文> })
```

**调用链**

```
剪贴板回调  t50/p$a;->e(String)
  └─ t50/p;->h(Activity, String)
       └─ t50/p;->m                    ★ 正则 .*\$.+\$.* 识别口令
            └─ t50/q  AsyncTask
                 └─ NeteaseMusicApiImpl;->h(String)      ★ 发包
                      └─ d32/e;->b("password/url/decode/get")
                           └─ AppTokenInfo { token, decodedUrl, popInfo }
                 └─ RedirectActivity.launch(decodedUrl)  ★ 跳转
```

**实测结果**

```json
{
  "code": 200,
  "data": {
    "decodedUrl": "https://y.music.163.com/g/yida/radsjl3919725993/49170baa9fad453c87a60acafd665dad?full_screen=true&nm_style=sbt&encryptUid=34c2e744...",
    "popInfo": { "popUp": false, "description": null }
  }
}
```

假口令 `test123` 返回 `{"code":422,"message":"非法口令"}` —— 说明**接口匿名可调，不需要登录 Cookie**。

加密：eapi，AES-128-ECB / key `e82ckenh8dichen8`，分隔符 `-36cd479b6b5-`，签名用 `/api/` 前缀但请求发 `/eapi/`。

完整报告（含口令清洗过程、AppTokenInfo 结构、其他相关接口辨析）见 [`docs/netease-decode-api.md`](./docs/netease-decode-api.md)。

---

## 本地网页版工具

`web/` 里是一个零依赖的 Node 工具，把上面这套流程做成可视化的：粘贴口令 → 看离线结构分析 → 看真实接口返回 → 看调用链。

```bash
cd web
node server.js          # 或 Windows 双击 启动.bat
# 打开 http://127.0.0.1:8899
```

只监听 `127.0.0.1`，不对外。详见 [`web/README.md`](./web/README.md)。

---

## 仓库结构

```
hez-kouling-analyzer/
├── SKILL.md                      # 方法论主体（7 步流程 + 排错表 + 6 条经验）
├── AI_INSTALL.md                 # 写给 AI 执行的安装文档
├── install.cmd / .sh / .ps1      # 一键安装脚本
├── scripts/
│   ├── dex_tool.py               # 通用 DEX 解析器，5 个子命令
│   ├── eapi_client.js            # 网易云 eapi 实现（Node，实测可用）
│   └── eapi_client.py            # 同上 Python 版（协议参考，注意空响应坑）
├── references/
│   ├── netease-case.md           # 网易云完整案例 + 5 个踩坑
│   └── patterns.md               # 各类 App 特征速查
├── docs/
│   └── netease-decode-api.md     # 逆向分析报告正文
└── web/
    ├── server.js                 # 本地工具后端（eapi 代理）
    └── public/index.html         # 单页前端
```

---

## 环境要求

| 项 | 要求 |
|---|---|
| Python | 3.8+（`dex_tool.py`） |
| Node.js | 18+（仅 `eapi_client.js` 和 `web/` 需要） |
| 其他 | 无。不需要 jadx、apktool、Frida、PyCrypto、requests |

`dex_tool.py` 是纯标准库实现，AES 都是自己写的。

---

## 三个最容易踩的坑

**1. 接口返回空 body，别急着判定「需要登录」**

这个坑真实浪费了一整轮分析。同样的加密参数：Python `urllib` 和 `curl` 拿到空响应，Node 的 `fetch`（undici）正常返回 200 + 完整 JSON。加密输出经比对是字节级一致的。

**先换 HTTP 客户端，再怀疑鉴权。**

**2. class_data 里 static 和 instance 字段必须分开循环**

合并成一个 `range(sf + inf)` 会导致后续所有方法索引漂移，症状是 `struct.error: unpack_from requires a buffer of at least ... bytes`。看起来像文件损坏，其实是解析器 bug。

**3. `apis` 命令会漏裸路径**

口令接口常常不带 `/api/` 前缀。最初的实现只匹配带前缀路径，直接漏掉了 `password/url/decode/get`。现在同时匹配裸的多段小写路径 —— 代价是噪音从 1121 条涨到 3461 条，但宁可多抓不漏。

---

## 如果目标 App 不是网易系

`references/patterns.md` 里有速查表：常见口令形态（`$x$` / `¥x¥` / Base64 / 短链）、返回字段名、各厂商网关前缀（阿里 `mtop`、字节 `aweme`、微信 `cgi-bin`）、加密方案识别、剪贴板监听的四种实现。

判断「找到的是不是口令接口」的三条标准：

- [ ] 参数是**一整段文本**（不是 ID、不是数字）
- [ ] 返回含**URL 语义字段**
- [ ] 调用方在**剪贴板读取之后**

三条都满足基本就是它。只满足前两条但调用方在广告/推送模块 —— 那是 deeplink 归因，不是口令。

---

## 使用范围

本项目用于**协议分析与安全研究**，面向你有权检视的应用。

请勿用于批量爬取、刷活动奖励、绕过访问控制等用途。使用前请自行确认符合目标服务条款与当地法律。

---

## License

[MIT](./LICENSE)

---

<div align="center">
<sub>如果这个工具帮你省下了装 jadx 和翻三十个 obfuscated 类的时间，给个 star。</sub>
</div>