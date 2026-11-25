# 本地网页版工具

把口令解析流程做成可视化界面：粘贴口令 → 离线结构分析 → 真实接口调用 → 调用链展示。

零依赖，不需要 `npm install`。单页前端 + Node 内置模块写的后端。

## 启动

```bash
node server.js
```

Windows 双击 `启动.bat` 效果相同。

浏览器打开 <http://127.0.0.1:8899>。

## 端口与监听

服务只监听 `127.0.0.1:8899`，**不对外网开放**。改端口：

```bash
PORT=9000 node server.js
```

## 功能

| 区块 | 说明 |
|---|---|
| 粘贴口令 | 支持读剪贴板、`$...$` 高亮、`Ctrl+Enter` 快捷解析 |
| 本地结构分析 | 纯离线：复刻客户端清洗逻辑（去空格、去换行）+ 正则匹配，不联网 |
| 接口请求与响应 | 真实调用 `/eapi/password/url/decode/get`，三标签页展示响应原文 / 请求详情 / 解析后 JSON |
| 调用链 | 从剪贴板回调到 `RedirectActivity.launch` 的 8 步可视化 |

## 接口

| 路由 | 用途 |
|---|---|
| `GET /api/health` | 健康检查 |
| `POST /api/analyze` | 纯离线口令结构分析，不发外网请求 |
| `POST /api/decode` | 真实调用网易云接口，返回 `decodedUrl` |

`/api/decode` 的加密逻辑与服务端代理在 `server.js` 里，核心是 `eapiEncrypt()`：

```js
const EAPI_KEY = Buffer.from('e82ckenh8dichen8');
const SEP = '-36cd479b6b5-';
// 签名用 /api/ 前缀，请求发到 /eapi/ 路径 —— 写错会返回空响应
```

## 注意

这个页面里的接口调用**硬编码了网易云的 eapi 协议**。换成别的 App 时，`/api/decode` 那一层需要按目标 App 的协议重写，但 `/api/analyze` 的离线结构分析和整个前端可以复用。

`server.js` 里没有 `requests` 依赖，用的是 Node 内置的 `https` / `crypto`，所以不需要 `npm install`。

## 为什么不直接用浏览器发起请求

因为 eapi 协议要用 AES-128-ECB 加密请求体，而且部分网关会校验 `User-Agent` 和 `Referer`。浏览器里的 `fetch` 会触发 CORS 预检并被拒。所以走本地服务端代理。