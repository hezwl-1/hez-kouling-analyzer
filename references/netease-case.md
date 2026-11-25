# 案例实录：网易云音乐口令解析接口

**样本**：`106_5b634bb11dbb2480212025c108a0ee6c.apk`
**包名**：`com.netease.cloudmusic`
**规模**：21 个 dex，约 190MB 字节码
**环境限制**：无 jadx / apktool（`apktool.bat` 是空壳，jar 不存在；GitHub 下载超时）

## 最终结果

```
POST https://interface.music.163.com/eapi/password/url/decode/get
参数：encodedPassword = 口令全文
返回：{ token, decodedUrl, popInfo }
```

实测输出：

```json
{
  "code": 200,
  "data": {
    "decodedUrl": "https://y.music.163.com/g/yida/radsjl3919725993/49170baa9fad453c87a60acafd665dad?full_screen=true&nm_style=sbt&encryptUid=34c2e74422f73557e2e7c87fe3f910111c01e379df1b377e4a0542e158d26e10",
    "popInfo": { "popUp": false, "description": null }
  },
  "message": ""
}
```

## 完整调用链

```
t50/p$a.e(String)                     剪贴板监听回调
  → t50/p.h(Activity, String)         口令控制器
    → t50/p.m                         ★ 正则识别
      → t50/q AsyncTask               后台任务
        → NeteaseMusicApiImpl.h       ★ 发包
          → d32/e.b(...)              HTTP 封装
            → AppTokenInfo            { token, decodedUrl, popInfo }
        → t50/q.f(info)               主线程回调
          → RedirectActivity.launch   ★ 跳转
```

### 各环节细节

**t50/p;->m（口令识别核心）**

```java
invoke-static lt;->e(CharSequence)Z            // 非空判断
const-string v0, " "                          // 先删空格
const-string v2, ""
invoke-virtual String->replace(CharSequence, CharSequence)
const-string v0, "\n"                         // 再删换行
invoke-virtual String->replace(...)
const-string v0, "cloud_disk_check_show_paste" // AB 开关
const-string v0, ".*\$.+\$.*"                  // ★ 口令特征正则
invoke-virtual String->matches(String)Z
new-instance t50/q                             // 起异步任务
```

**NeteaseMusicApiImpl;->h(String)**

```java
const-string v0, "password/url/decode/get"    // ★ 接口路径
invoke-static d32/e;->b(String)Le42/a;
const-string v3, "encodedPassword"            // ★ 参数名
invoke-virtual e42/f;->v0([Object)Le42/f;
check-cast AppTokenInfo
invoke-virtual AppTokenInfo;->setToken(String)
```

**AppTokenInfo 结构**

```java
class AppTokenInfo {
    String  token;
    String  decodedUrl;      // ★ 跳转地址
    PopInfo popInfo;

    class PopInfo { Des description; boolean popUp; boolean showCloseBtn; }
    class Des     { String title, btnText, coverImageUrl; }
}
```

## 定位过程（关键路径）

### 1. 全量字符串导出

21 个 dex，导出 154 万条字符串到 `strs/*.txt`。

### 2. 中文关键词定位

搜「星火」「口令」「剪贴板」：

```
classes18.dex  {'口令': 1, '邀请': 19}
classes20.dex  {'剪贴板': 1}
```

`classes18.dex` 同时含「口令」，重点看。

### 3. 发现剪贴板读取点

搜 `read clipboard text error` → `Lt50/p$a;->d`，进而找到 `Lt50/z;->h(Context)`（系统 TextClassifier 封装，用于实体抽取，不是口令逻辑）。

### 4. 正则一击命中（决定性突破）

在 `classes18.dex` 的字符串里搜正则特征：

```bash
grep -nE '\\\$|\\d\{' strs/classes18.dex.txt
```

第 13876 行：

```
.*\$.+\$.*
```

正对口令的 `$aqYvQf35171768$` 格式。

### 5. 反查引用类

对这个正则做字符串反查，得到 3 处：

```
Lcom/netease/cloudmusic/module/barcode/g$d;->c   ← 二维码扫描，误命中
Lt50/l;->k                                        ← 同名类（RecyclerView item 动画），误命中
Lt50/p;->m                                        ← ★ 真命中
```

逐个反汇编排除误命中后锁定 `t50/p;->m`。

### 6. 顺链找到接口

`t50/p;->m` → `t50/q`（AsyncTask）→ `t50/q;->e` → `NeteaseMusicApiImpl;->h` → 看到 `password/url/decode/get`。

## 踩过的坑

### 坑 1：dpLink 是广告字段，不是口令

一开始搜 `dpLink` 命中 12 处，全在 `classes18.dex`，看上下文发现都是广告归因：

```
handleAdFreePlayTaskFromBoot dpLink =
tryReportAdExternalUser 归因上报: dpLink=
AdExposureDeeplinkData(dpLink=
```

**教训**：`dpLink` 在广告 SDK 里是通用字段名，别一见就当成口令跳转。

### 坑 2：`/api/sns/v1/ext/share/token` 是小红书的

这个接口名很可疑，但查全串发现是：

```
https://edith.xiaohongshu.com/api/sns/v1/ext/share/token
```

**教训**：APK 里会打包第三方 SDK 的接口，看路径之前先看完整域名。

### 坑 3：误判「需要登录」

Python 调接口一直返回空 body，我下结论说「服务端对匿名请求返回空，需要 Cookie」。

**这个结论是错的。** 后来用 Node.js fetch 重写，同样的加密内容、同样的请求头，直接返回 200 + 完整数据。

对照实验：

| 条件 | Python urllib | Node.js fetch |
|---|---|---|
| 真实口令 | 0 字节 | 281 字节，完整 JSON |
| 忽略 UA/Cookie | 0 字节 | 281 字节 |

加密输出两者字节级一致（比对过 hex）。

**教训**：空响应先换 HTTP 客户端，不要急着下「需要鉴权」的结论。

### 坑 4：DEX 解析索引漂移

自写解析器一开始把 class_data 的字段段合并成一个循环：

```python
for _ in range(sf + inf):   # 错
    ...
```

导致后续方法索引全部偏移，出现 `struct.error: unpack_from requires a buffer of at least 26322548 bytes`。

正确写法必须拆两组：

```python
for _ in range(sf):    # static fields
    ...
for _ in range(inf):   # instance fields
    ...
```

### 坑 5：jadx / apktool 不可用

- `apktool.bat` 里引用 `%apktoolJar%`，但同目录下没有 jar
- PATH 里有个中文路径的 jadx 目录，实际不存在
- GitHub 下载 jadx 超时

**处理**：不折腾装工具，直接自写 DEX 解析器。190MB 的包也能扫，速度可接受（全量字符串导出约 1 分钟）。

## eapi 加密协议

```python
path   = '/api/password/url/decode/get'
text   = '{"encodedPassword":"<口令>"}'
md5    = md5("nobody" + path + "use" + text + "md5forencrypt")
raw    = path + "-36cd479b6b5-" + text + "-36cd479b6b5-" + md5
params = AES128ECB(raw, "e82ckenh8dichen8").hex().upper()
```

**易错点**：签名用 `/api/` 前缀，但实际请求 URL 要发到 `/eapi/` 路径。写错返回空响应。

## 其他发现

| 项目 | 内容 |
|---|---|
| 短链域名 | `163cn.tv`、`163cn.link`（由 `cl/b$c`、`cl/b$j` 两个混淆类处理） |
| 相关 deeplink 接口 | `flow/middle/deeplink/get`、`flow/middle/wakeup/deeplink/get`、`flow/ad/exposure/deeplink/get` |
| 链接配置表 | `assets/default_link_config.json`，273 条 `link#xxx` 模板（是**分享出去**的链接，与口令解析无关） |
| 提取到的 API 总数 | 1121 条 |

## 产出物

| 文件 | 说明 |
|---|---|
| `apkwork/dexscan.py` | DEX 解析器原型（已演进为技能的 `scripts/dex_tool.py`） |
| `apkwork/disasm.py` | 反汇编器原型 |
| `apkwork/eapi_decode.py` | Python 加密实现 |
| `apkwork/web/` | 网页版工具（Node 服务端 + 单页前端） |
| `apkwork/strs/` | 21 个 dex 全量字符串（32MB） |