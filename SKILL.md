---
name: hez口令解析分析
description: 从 Android APK 中逆向定位「口令解析」接口（粘贴口令/分享码后获取跳转地址的 API，又称淘口令、星火口令、邀请码、commandCode）。适用于逆向 App 的剪贴板识别逻辑、寻找 dpLink/deeplink/H5 跳转接口、还原口令解码协议。触发词：解析口令接口、口令逆向、APK找接口、淘口令接口、剪贴板解析、dpLink、deeplink接口、commandCode、分享码解析、hez。
agent_created: true
---

# hez 口令解析分析

## 用途

从 Android APK 中定位「口令 → 跳转地址」的解析接口。典型场景：

- 用户粘贴一段形如 `1http:/$aqYvQf35171768$ 复zhi口令码打开XX` 的文本，App 自动识别并跳转活动页
- 需要找出这个接口的 URL、请求参数、加密方式
- 需要还原出跳转地址（dpLink / deeplink / orpheus:// / H5）

**核心难点**：接口路径往往不含 `kouling`、`command` 等直观关键词。网易云音乐那个接口叫 `password/url/decode/get`（伪装成改密码），只能靠字节码引用关系才能挖出来。

## 前置检查

按顺序确认工具链，缺什么补什么：

```bash
python --version          # 3.8+
unzip -v                  # 解包 APK
which java                # 可选，跑 jadx 需要
```

**关于 jadx/apktool**：本机很可能装了空壳（`apktool.bat` 引用了不存在的 jar）。先实测能否运行，别假设可用：

```bash
apktool --version 2>&1 | head -3
```

如果不可用，**不要卡在装工具上** —— 本技能自带 `scripts/dex_tool.py`，纯 Python 解析 DEX，无需 jadx，已实战验证过 190MB / 21 dex 的包。

## 执行流程

### 第 1 步：解包

```bash
mkdir -p apkwork/ex
cd apkwork/ex
unzip -o -q /path/to/app.apk "*.dex" "AndroidManifest.xml" "resources.arsc" "assets/*"
ls -lh *.dex | head -30
```

记录：dex 数量、总字节数、包名（从 manifest 或 assets 判断）。

### 第 2 步：定位线索（不要盲搜接口路径）

**错误做法**：直接 grep `/api/` 找口令接口。口令接口路径通常不含直观关键词，必然失败。

**正确顺序**：

```bash
# 2.1 先导出全量字符串，后面所有检索都在这个集合上做
python scripts/dex_tool.py strings apkwork/ex
```

然后按优先级检索（用 Grep 工具，比 Python 快）：

| 优先级 | 检索内容 | 说明 |
|---|---|---|
| 1 | 口令文本的中文片段（如「星火」「口令」「复zhi」） | App 里一定有提示文案，能定位到功能模块 |
| 2 | `clipboard` / `getPrimaryClip` | 剪贴板读取点，是整条链路的起点 |
| 3 | `deeplink` / `dpLink` / `scheme` / `redirect` | 跳转相关字段名 |
| 4 | 短链域名（`*.tv` / `*.link` / `t.cn` 类） | 口令文本里常含短链 |
| 5 | 正则特征：`\$`、`\\d{`、`(?i)` | **最关键的突破口**，见下 |

**第 5 项是核心技巧**：口令识别几乎一定用正则做格式校验。搜含 `$` 或 `\\d{` 的正则串，往往能一步命中：

```bash
grep -nE '\\\$|\\d\{|\(\?:' apkwork/strs/*.txt | head -40
```

网易云案例中，就是靠这个方法一击命中 `.*\$.+\$.*`。

### 第 3 步：字符串反查引用类（核心武器）

找到关键字符串（正则、域名、文案）后，用 `find` 命令反查「哪个方法引用了它」：

```bash
python scripts/dex_tool.py find apkwork/ex '.*\$.+\$.*'
```

输出形如：

```
=== classes18.dex (3 处)
  Lcom/netease/cloudmusic/module/barcode/g$d;->c   ← 二维码，误命中
  Lt50/l;->k                                        ← 同名类，误命中
  Lt50/p;->m                                        ← ★ 真正的口令识别点
```

**如何排除误命中**：看类名所在包、方法签名、以及后续反汇编内容。命中多个时全部反汇编一遍，只留真正处理文本的那个。

### 第 4 步：反汇编，顺着调用链走

```bash
python scripts/dex_tool.py disasm apkwork/ex/classes18.dex 'Lt50/p;' 'm'
```

看输出里的 `const-string` 和 `invoke`：

- `const-string` → 参数名（如 `encodedPassword`）、开关 key、正则
- `invoke ...->h(...)` → 下一跳方法
- `new-instance` → 数据模型类（如 `AppTokenInfo`）

**关键判断**：如果 invoke 的目标方法返回类型是个数据模型（如 `AppTokenInfo`），那这个方法就是发包点，直接反汇编它就能看到接口路径。

```bash
python scripts/dex_tool.py disasm apkwork/ex/classes15.dex \
  'Lcom/netease/cloudmusic/api/impl/NeteaseMusicApiImpl;' 'h'
```

第一行就是答案：

```
00000: const-string v0, "password/url/decode/get"
00014: const-string v3, "encodedPassword"
```

### 第 5 步：确认参数与返回结构

反汇编数据模型类，看字段：

```bash
python scripts/dex_tool.py methods apkwork/ex/classes17.dex 'Lcom/netease/cloudmusic/meta/AppTokenInfo;'
```

或用 `disasm` 看构造，或用正向查找定位字段定义。口令场景的经典返回结构：

```
{ token, decodedUrl, popInfo }     ← decodedUrl 就是跳转地址
{ code, url, scheme, h5Url }       ← 其他 App 常见变体
{ result, jumpUrl, deeplink }      ← 变体
```

**重点找带 URL 语义的字段**：`decodedUrl` / `jumpUrl` / `scheme` / `h5Url` / `dpLink` / `deeplink` / `redirectUrl`。

### 第 6 步：确认加密方式与网关

看发包方法的上一层封装（如 `d32/e;->b(String)`），找：

- **域名常量**：搜 `interface.` / `api.` / `gw.` 前缀的域名
- **路径前缀**：`/api/`、`/eapi/`、`/weapi/`、`/v1/`、`/openapi/`
- **加密实现**：搜 `aes`、`rsa`、`md5`、`sign`、`encrypt`

### 第 7 步：实测调通

写脚本发真实请求。**遇到空响应先别下「需要登录」的结论** —— 换 HTTP 客户端再试（见下方「排错」）。

成功的标志：
- `code: 200` + 含跳转 URL 的字段 → 完全成功
- `code: 422 / 400` + 明确错误信息（如「非法口令」）→ 接口通了，只是口令无效，同样算定位成功

## 实战案例：网易云音乐

完整链路，可作为参照模板：

```
剪贴板回调 t50/p$a.e(String)
  → t50/p.h(Activity, text)
    → t50/p.m                      ★ 正则 .*\$.+\$.* 识别口令
      → t50/q AsyncTask
        → NeteaseMusicApiImpl.h    ★ 发包
          → d32/e.b("password/url/decode/get")
            → AppTokenInfo { token, decodedUrl, popInfo }
        → RedirectActivity.launch(decodedUrl)
```

| 项 | 值 |
|---|---|
| 接口 | `POST https://interface.music.163.com/eapi/password/url/decode/get` |
| 参数 | `encodedPassword` = 口令全文 |
| 加密 | eapi：AES-128-ECB / key `e82ckenh8dichen8`，签名用 `/api/` 前缀但请求发 `/eapi/` |
| 鉴权 | **无需登录**，匿名可调 |
| 命中路径 | 全量字符串 → 搜 `\$` 正则 → `.*\$.+\$.*` → 反查引用 → `t50/p.m` → 顺链到 `NeteaseMusicApiImpl.h` |

详见 `references/netease-case.md`。eapi 加密的可运行实现见 `scripts/eapi_client.py`。

## 通用排错

| 症状 | 原因 | 处理 |
|---|---|---|
| `find` 返回 0 | 字符串编码差异，或关键词含转义 | 用 `strings` 导出的 txt 先 grep 确认字符串确实存在，再 `find` |
| 方法索引越界 | class_data 解析错位 | 检查 `iter_methods` 里 static/instance 字段是否分开循环（本脚本已修正） |
| 反汇编只有前几条 | 指令宽度表不对 | 确认 `WIDTH` 表已按 opcode 范围设置，不要用固定宽度扫描 |
| `apis` 抓不到目标接口 | 接口是裸路径，不带 `/api/` 前缀 | 本脚本已同时匹配裸路径；若仍找不到，直接在 `strs/*.txt` 里 grep 已知的路径片段 |
| **接口返回空 body** | **HTTP 客户端差异（最大坑）** | **换客户端重试**：Node.js `fetch`（undici）常能成功，而 Python `urllib`/`curl` 可能被网关判空。先换客户端，别急着加 Cookie |
| 返回 403 / 需要验证 | 真有风控 | 补 `User-Agent`、`Cookie`、设备指纹；或改用抓包 |
| 加密后服务端不认 | 签名拼接顺序错 | 常见是 path、body、key 的拼接顺序或大小写（hex 要大写） |

## 脚本清单

| 脚本 | 用途 |
|---|---|
| `scripts/dex_tool.py` | 通用 DEX 解析：`strings` / `apis` / `find` / `disasm` / `methods` |
| `scripts/eapi_client.py` | 网易云 eapi 加密 + 调用范例（Python，注意可能有空响应问题） |
| `scripts/eapi_client.js` | 同上，Node.js 版，**实测更可靠** |
| `references/netease-case.md` | 网易云完整案例，含所有踩坑记录 |
| `references/patterns.md` | 各类 App 口令接口的常见特征速查 |

### apis 命令的注意点

口令接口的路径常常**不带 `/api/` 前缀**（网易云是裸的 `password/url/decode/get`，
只在签名时才拼 `/api/`）。所以 `apis` 命令同时匹配「带前缀路径」和「裸的多段小写路径」。

代价是会有噪音（类名如 `/api/IRemoteDecoderCreator` 也会被抓到，网易云案例共 3461 条）。
**宁可多抓也别漏** —— 用 grep 过滤比漏掉真接口强。

## 关键经验（务必记住）

1. **不要盲搜接口路径**。口令接口的路径往往伪装成别的功能（网易云叫 `password/url/decode/get`）。
2. **正则是最快的突破口**。口令格式校验一定用正则，搜 `\$` / `\\d{` 能一步命中。
3. **用字符串反查引用类**，比顺着 UI 代码往下找快一个数量级。
4. **空响应先换 HTTP 客户端**，不要直接判定需要登录。这个坑在网易云案例上真实踩过，误判浪费了一整轮。
5. **class_data 的 static/instance 字段必须分开循环**，合并会导致后续所有方法索引漂移。
6. 反汇编时 `const-string` 后面紧跟 `invoke ...->x(..., [Ljava/lang/Object;)` 通常是「参数名 + 参数值」的组合，参数名往往在前一条 `const-string`。