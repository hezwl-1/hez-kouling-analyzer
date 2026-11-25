# 网易云音乐 APK 口令解析接口分析报告

**样本**：`106_5b634bb11dbb2480212025c108a0ee6c.apk`
**版本时间**：2026-11-24 构建 / 21 个 dex，约 190MB 字节码
**包名**：`com.netease.cloudmusic`（网易云音乐）
**分析方式**：DEX 结构解析 + 字节码反汇编（无 jadx/apktool，自写解析器）

---

## 一、结论：核心接口

### 口令解析接口

```
POST/GET  https://interface.music.163.com/eapi/password/url/decode/get
```

| 项 | 值 |
|---|---|
| 接口路径 | `password/url/decode/get` |
| 请求参数 | `encodedPassword` = 剪贴板中的完整口令文本 |
| 返回模型 | `com.netease.cloudmusic.meta.AppTokenInfo` |
| 网关域名 | `interface.music.163.com`（`/eapi/` 前缀，另有 `/weapi/`、`/xeapi/`、`/neapi/`、`/store/eapi/`、`/live/eapi/` 备用） |

`AppTokenInfo` 结构：

```java
class AppTokenInfo {
    String  token;        // 口令原文/令牌
    String  decodedUrl;   // ★ 解析出来的跳转地址（dp链接 / uk / h5）
    PopInfo popInfo;      // 弹窗配置

    class PopInfo {
        Des     description;
        boolean popUp;
        boolean showCloseBtn;
    }
    class Des {
        String title;
        String btnText;
        String coverImageUrl;
    }
}
```

**`decodedUrl` 就是要找的跳转地址**——它可以是 `orpheus://`深链、`https://`H5，或第三方 dp 链接。

---

## 二、完整调用链

```
剪贴板监听（Activity onResume / 粘贴事件）
  └─ t50/p$a;->e(String)                       剪贴板文本回调
       └─ t50/p;->h(Activity, String)
            └─ t50/p;->m(Activity, String)     ★ 口令识别核心
                 ├─ 文本预处理：remove(" ") 、remove("\n")
                 ├─ String.matches(".*\\$.+\\$.*")   ★ 口令特征正则
                 │    └─ 你的口令 `1http:/$aqYvQf35171768$` 命中 $...$ 段
                 ├─ AB 开关："cloud_disk_check_show_paste"
                 └─ new t50/q(Activity, iAppToken, iCallback, iDialog).doExecute()
                      └─ t50/q;->e(String[] params)          // AsyncTask 后台
                           └─ NeteaseMusicApiImpl.E7().h(params[0])
                                └─ NeteaseMusicApiImpl;->h(String)   ★ 真正发请求
                                     ├─ d32/e;->b("password/url/decode/get")
                                     ├─ 参数 "encodedPassword" = 口令文本
                                     └─ 返回 AppTokenInfo
                      └─ t50/q;->f(AppTokenInfo info)        // 回到主线程
                           ├─ 有 popInfo → 弹 MaterialDialog 确认框
                           └─ 无弹窗 → q;->d(Context, info.getDecodedUrl())
                                └─ RedirectActivity.launch(Context, url)   ★ 跳转执行
```

### 关键类速查

| 类 | 作用 |
|---|---|
| `Lt50/p;` | 口令控制器（剪贴板入口） |
| `Lt50/p$a;` | 剪贴板监听回调（`d()` 读剪贴板 / `e(String)` 收文本） |
| `Lt50/q;` | AsyncTask，负责请求 + 弹窗 + 跳转 |
| `Lt50/z;` | 系统 TextClassifier 封装，仅做实体抽取（非口令逻辑） |
| `Lt50/b;` | 口令确认弹窗（MaterialDialog） |
| `Lt50/l;` | 列表 item 动画（同名误命中，与口令无关） |
| `LNeteaseMusicApiImpl;` | `h(String)` 发包方法所在 |
| `LAppTokenInfo;` | 响应模型 |
| `LRedirectActivity;` | 统一跳转落地页 |

---

## 三、你的口令如何被解析

你给的口令：

```
08:06 1http:/$aqYvQf35171768$ 02/04/1990 SC8986  复zhi口令码打开网易☁音乐，
参与星火计划，领取你的星火福利！
```

处理过程：

1. **清洗**：删掉所有空格和换行 → `08:061http:/$aqYvQf35171768$02/04/1990SC8986复zhi口令码...`
2. **正则匹配** `.*\$.+\$.*` → 命中 `$aqYvQf35171768$` 这一段（前后有 `$` 包裹）
3. **整段清洗后文本**作为 `encodedPassword` POST 给 `/eapi/password/url/decode/get`
4. 服务端返回 `AppTokenInfo`，其中 `decodedUrl` 就是最终的「星火计划」活动落地页

> 注意：`08:06`、`02/04/1990`、`SC8986` 这些是**干扰项/水印**，服务端靠 `$...$` 里的 `aqYvQf35171768` 定位真实口令。

---

## 四、实测结果（已成功调通）

### 实测输出

用你给的口令实测，接口返回：

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

**解出的跳转地址**（星火计划活动页）：

```
https://y.music.163.com/g/yida/radsjl3919725993/49170baa9fad453c87a60acafd665dad
?full_screen=true&nm_style=sbt
&encryptUid=34c2e74422f73557e2e7c87fe3f910111c01e379df1b377e4a0542e158d26e10
```

### 重要结论：**接口无需登录**

对照实验：

| 请求条件 | 结果 |
|---|---|
| **真实口令** + 只有 Content-Type | ✅ 200，返回完整 JSON（281B） |
| 真实口令 + 完整 UA/Cookie/IP | ✅ 200，同样结果 |
| 假口令 `test123` | 200，`{"code":422,"message":"非法口令"}` |

→ **匿名即可调用，不需要 `MUSIC_U` Cookie，不需要设备指纹**。之前判断「需要登录」是错的，实际是 Python/curl 环境下的请求被网关判为空响应（Node 的 undici 正常）。

### 校验逻辑

服务端靠 `$...$` 里的短码定位口令，与前后水印无关：

- 真实短码 `aqYvQf35171768` → code 200 + decodedUrl
- 随便编 `test123` → code 422 非法口令

### eapi 加密细节（已验证）

- 算法：AES-128-ECB，key = `e82ckenh8dichen8`，PKCS7 填充
- 明文：`<path>-36cd479b6b5-<json>-36cd479b6b5-<md5>`
- md5 = `md5("nobody" + path + "use" + json + "md5forencrypt")`
- 输出：hex 大写
- 注意：参与签名的 path 用 `/api/` 前缀，实际请求发到 `/eapi/` 路径

---

## 五、其他发现的相关接口

| 接口 | 用途 |
|---|---|
| `eapi/flow/middle/deeplink/get` | 中间页 deeplink 解析（广告/活动跳转兜底） |
| `eapi/flow/middle/wakeup/deeplink/get` | 唤醒场景 deeplink |
| `eapi/flow/ad/exposure/deeplink/get` | 广告曝光 deeplink |
| `eapi/song/enhance/player/url/v1` | 播放地址（非口令，容易混淆） |

短链域名常量：`163cn.tv`、`163cn.link`（由 `cl/b$c`、`cl/b$j` 两个混淆类处理）

配置文件 `assets/default_link_config.json` 含 273 条 `link#xxx` 跳转模板，例如：
- `link#song_share` → `https://y.music.163.com/m/song?id=${id}`
- `link#playlist_share` → `https://y.music.163.com/m/playlist?id=${id}`
- `link#user_share` → `https://y.music.163.com/m/user?id=${id}`

这些是**分享出去**的链接模板，不是口令解析，别搞混。

---

## 六、复现脚本（eapi 加密请求）

```python
import json, hashlib, binascii
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

EAPI_KEY = b'e82ckenh8dichen8'

def eapi_encrypt(path: str, payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    digest = hashlib.md5(
        f'nobody{path}use{text}md5forencrypt'.encode()
    ).hexdigest()
    data = f'{path}-36cd479b6b5-{text}-36cd479b6b5-{digest}'
    cipher = AES.new(EAPI_KEY, AES.MODE_ECB)
    return binascii.hexlify(cipher.encrypt(pad(data.encode(), 16))).decode().upper()

def decode_kouling(kouling: str):
    path = '/api/password/url/decode/get'
    params = eapi_encrypt(path, {'encodedPassword': kouling})
    r = requests.post(
        'https://interface.music.163.com/eapi/password/url/decode/get',
        data={'params': params},
        headers={
            'User-Agent': 'NeteaseMusic/9.1.0.231018165600(9010000);Dalvik/2.1.0',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cookie': 'os=android; appver=9.1.0; osver=13; channel=netease;',
        },
        timeout=20,
    )
    return r.json()

# 用法
res = decode_kouling('08:06 1http:/$aqYvQf35171768$ 02/04/1990 SC8986  复zhi口令码打开网易☁音乐，参与星火计划，领取你的星火福利！')
print(res)
```

> 脚本里的 eapi 算法是网易云公开的通用方案，但 `appver`/`osver`/设备指纹可能被服务端校验。若返回 `code != 200`，优先改用抓包方案 A。

---

## 七、附：分析产物

| 文件 | 说明 |
|---|---|
| `apkwork/dexscan.py` | 自写 DEX 解析器（字符串引用反查类） |
| `apkwork/disasm.py` | 自写 DEX 字节码反汇编器 |
| `apkwork/strs/*.txt` | 21 个 dex 的全量字符串导出（32MB） |
| `apkwork/all_api.txt` | 提取的 1121 条 API 路径 |
| `apkwork/ex/` | 解包后的 dex / manifest / assets |