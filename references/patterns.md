# 各 App 口令接口特征速查

定位口令解析接口时，按这些特征去搜，命中率最高。

## 一、口令文本的形态

先看手上的口令长什么样，能反推实现方式：

| 形态 | 示例 | 说明 |
|---|---|---|
| `$xxx$` 包裹 | `1http:/$aqYvQf35171768$` | 网易云。用 `.*\$.+\$.*` 匹配 |
| 纯短码 + 中文引导 | `复制这段话¥abc123¥打开淘宝` | 淘宝系。常带 `¥` 或 `￥` |
| 前导数字 + 长串 | `9$abcdef1234$` | 用 `\\d\\$` 之类正则 |
| URL 里带短码 | `https://t.cn/abc123` | 走短链重定向 |
| Base64 块 | `5L2g5aW977yM5L2g5aW9` | 需解码后再解析 |
| 纯数字 ID | `12345678` | 直接拼接口参数 |

**关键动作**：不管哪种形态，先把它当正则的线索去搜。口令里那个特殊字符（`$`、`¥`、`￥`、`£`）大概率就是 App 用的分隔符，直接搜这个字符的转义形式。

## 二、常见字段名（返回结构）

搜这些字段名，能快速定位响应模型类：

```
decodedUrl      jumpUrl       targetUrl     redirectUrl
deeplink        dpLink        scheme        universalLink
h5Url           webUrl        landingUrl    activityUrl
commandCode     kouling       command       token
shareCode       inviteCode    shortUrl      originalUrl
```

**数组/对象型返回**的常见包裹：

```json
{ "code": 200, "data": { "decodedUrl": "..." } }
{ "result": { "jumpUrl": "..." } }
{ "data": [{ "scheme": "..." }] }
```

## 三、常见参数名（请求结构）

```
encodedPassword     kouling        command        shareCode
token               content        text           code
url                 shortUrl       link          口令原文
```

网易云用的是 `encodedPassword` —— **注意这个伪装**，看着像改密码，其实是口令。

## 四、常见网关与路径前缀

| 前缀 | 所属 |
|---|---|
| `/api/` | 通用（多数 App） |
| `/eapi/` | 网易系（网易云、网易严选） |
| `/weapi/` | 网易 PC 端 |
| `/xeapi/` `/neapi/` `/store/eapi/` | 网易系变体 |
| `/openapi/` `/gw/` `/mtop/` | 阿里系（mtop 是淘宝/支付宝） |
| `/aweme/` | 抖音 |
| `/rest/` `/napi/` | 字节系 |
| `/cgi-bin/` | 微信 |
| `/api/v1/` `/api/v2/` | 常规版本化 |

## 五、常见加密方案

| 方案 | 特征 | 典型 App |
|---|---|---|
| eapi（AES-128-ECB + md5 校验） | key `e82ckenh8dichen8`，分隔符 `-36cd479b6b5-` | 网易系 |
| mtop（MD5 签名 + 参数排序） | 参数含 `sign`、`t`、`appKey` | 阿里系 |
| 自定义 AES-CBC | 参数含 `data`、`iv`、`encrypt` | 金融类 |
| RSA | 参数含 `publicKey`、`encrypt`、`rsa` | 部分银行 |
| 无加密（仅 https） | 直接明文 JSON | 中小 App |

搜这些关键词定位加密实现：

```bash
grep -iE 'aes|rsa|md5|sha256|hmac' strs/*.txt
grep -iE 'encryptData|signStr|makeSign|calcSign' strs/*.txt
```

## 六、剪贴板监听的常见实现

口令功能必然读剪贴板，从这里切入也能顺链找到解析逻辑：

| 实现方式 | 搜什么 |
|---|---|
| Android 原生 | `getPrimaryClip`、`ClipboardManager` |
| 系统 TextClassifier | `TextClassificationManager`、`generateLinks` |
| 自定义工具类 | `getClipboardText`、`readClipboard` |
| RN / Flutter 桥接 | `NativeClipboardSpec`、`ClipboardModule` |

**注意**：剪贴板读取点常在 Activity 的 `onResume` 里，但真正的解析逻辑可能在另一个包。读剪贴板 → 判断格式 → 调接口，这三步可能分散在三个类里。

## 七、识别口令的正则模式

这是最高价值的检索目标。常见写法：

```regex
.*\$.+\$.*                # 网易云（$ 包裹）
[¥￥]([a-zA-Z0-9]{10,})[¥￥]  # 淘宝系
/\d+\$[a-zA-Z0-9]+\$/     # 前导数字
[a-zA-Z0-9]{8,12}         # 纯短码
https?://[^\s]+           # 短链
```

搜的时候关注这几类特征：

```bash
# 含转义美元符
grep -nE '\\\$' strs/*.txt

# 含量词
grep -nE '\\d\{|\+\}|\[a-zA-Z0-9\]' strs/*.txt

# 含非捕获组/断言
grep -nE '\(\?:|\(\?=|\(\?!' strs/*.txt

# 含 match/matches 调用附近的字符串
grep -nE 'matches|Pattern\.compile' strs/*.txt
```

## 八、搜索优先级建议

按这个顺序，通常 3 步内能锁定：

1. **口令里的特殊字符**（`$`、`¥`）→ 找正则 → 反查引用类
2. **中文提示文案**（「复制」「打开」「口令」）→ 找功能模块 → 顺链
3. **剪贴板 API** → 找读取点 → 顺链
4. **返回字段名**（`decodedUrl` 等）→ 找响应模型 → 反向找发包点
5. **API 路径**（最后手段，因为最可能是伪装的）

## 九、快速判断「找到了没有」

一个接口是否就是口令解析接口，看三个条件：

- [ ] 参数是**一整段文本**（不是 ID、不是数字）
- [ ] 返回含**URL 语义字段**
- [ ] 调用方在**剪贴板读取之后**

三条都满足，基本就是它。

如果只满足前两条但调用方是广告/推送模块，那是 deeplink 归因，不是口令。

## 十、遇到混淆怎么办

现代 App 的类名方法名基本都被混淆成 `t50/p`、`d32/e` 这种。这不影响本方法：

- **字符串不会被混淆** —— 正则、参数名、接口路径都是明文字符串
- 所以「搜字符串 → 反查引用类」这条路永远有效
- 类名混淆只影响可读性，不影响定位

反过来，如果发现字符串被加密了（搜不到明文正则），说明 App 用了字符串加密方案，此时搜 `decrypt`、`StringFog`、`jie` 等关键词，或者从 `assets` 里找加密映射表。