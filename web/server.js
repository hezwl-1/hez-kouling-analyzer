/**
 * 网易云音乐 口令解析器 — 本地服务端
 *
 * 逆向来源：com.netease.cloudmusic  9.x  (2026-11-24 构建)
 * 接口：POST https://interface.music.163.com/eapi/password/url/decode/get
 * 参数：encodedPassword = 剪贴板口令全文
 *
 * 只在本机运行，不依赖任何第三方包。
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PORT = Number(process.env.PORT || 8899);
const PUBLIC_DIR = path.join(__dirname, 'public');

// eapi 固定密钥（网易云客户端内置）
const EAPI_KEY = Buffer.from('e82ckenh8dichen8');
const SEP = '-36cd479b6b5-';

// 口令特征正则 —— 与 APK 内 t50/p;->m 中的常量完全一致
const KOULING_RE = /.*\$.+\$.*/s;

/* ---------------------------------------------------------------- eapi 加密 */

function eapiEncrypt(apiPath, payload) {
  const text = JSON.stringify(payload);
  const digest = crypto
    .createHash('md5')
    .update(`nobody${apiPath}use${text}md5forencrypt`, 'utf8')
    .digest('hex');
  const raw = `${apiPath}${SEP}${text}${SEP}${digest}`;
  const cipher = crypto.createCipheriv('aes-128-ecb', EAPI_KEY, null);
  cipher.setAutoPadding(true);
  return Buffer.concat([cipher.update(raw, 'utf8'), cipher.final()])
    .toString('hex')
    .toUpperCase();
}

/* ------------------------------------------------------------------ 工具函数 */

function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (c) => {
      size += c.length;
      if (size > 1024 * 512) {
        reject(new Error('请求体过大'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

/* --------------------------------------------------------------- 本地口令分析 */

/** 复刻客户端 t50/p;->m 的预处理：先删空格、再删换行 */
function normalize(text) {
  return String(text).replace(/ /g, '').replace(/\n/g, '');
}

function analyzeLocal(raw) {
  const cleaned = normalize(raw);
  const matched = KOULING_RE.test(cleaned);

  // 抓出所有 $xxx$ 片段，用于展示（客户端只做整体匹配，不单独截取）
  const segments = [];
  const re = /\$([^$]*)\$/g;
  let m;
  while ((m = re.exec(cleaned)) !== null) {
    segments.push({ full: m[0], inner: m[1], index: m.index });
  }

  return {
    original: raw,
    cleaned,
    matched,
    segments,
    length: { raw: raw.length, cleaned: cleaned.length },
  };
}

/* ------------------------------------------------------------- 请求网易云接口 */

async function callDecode({ kouling, cookie, appver, host, apiPath, timeout }) {
  const encryptedPath = apiPath || '/api/password/url/decode/get';
  const publicPath = encryptedPath.replace(/^\/api\//, '/eapi/');
  const targetHost = host || 'interface.music.163.com';
  const url = `https://${targetHost}${publicPath}`;

  const params = eapiEncrypt(encryptedPath, { encodedPassword: kouling });
  const body = new URLSearchParams({ params }).toString();

  const headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'User-Agent': `NeteaseMusic/${appver}.231018165600(9010000);Dalvik/2.1.0`,
    Cookie:
      cookie && cookie.trim()
        ? cookie.trim()
        : `os=android; appver=${appver}; osver=13; channel=netease;`,
    'X-Real-IP': '118.88.88.88',
  };

  const startedAt = Date.now();
  let status = 0;
  let bodyText = '';
  let errMsg = '';

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers,
      body,
      signal: AbortSignal.timeout(Number(timeout) || 20000),
    });
    status = resp.status;
    bodyText = await resp.text();
  } catch (e) {
    errMsg = e.name === 'TimeoutError' ? '请求超时' : String(e.message || e);
  }

  const elapsed = Date.now() - startedAt;

  // 抓取结果里的跳转地址（客户端字段名：decodedUrl）
  let parsed = null;
  try {
    parsed = JSON.parse(bodyText);
  } catch {
    /* 非 JSON，保持原文 */
  }

  const findUrl = (obj, depth = 0) => {
    if (!obj || depth > 6) return null;
    if (typeof obj === 'string') return null;
    for (const [k, v] of Object.entries(obj)) {
      if (/^(decodedUrl|url|jumpUrl|redirectUrl|link)$/i.test(k) && typeof v === 'string' && v) {
        return { key: k, value: v };
      }
      if (typeof v === 'object') {
        const r = findUrl(v, depth + 1);
        if (r) return r;
      }
    }
    return null;
  };

  return {
    request: {
      url,
      method: 'POST',
      encryptedPath,
      paramsLength: params.length,
      paramsPreview: params.slice(0, 96) + (params.length > 96 ? '…' : ''),
      bodyPreview: `params=${params.slice(0, 40)}…`,
      headers: { ...headers, Cookie: headers.Cookie.replace(/(MUSIC_U=[^;]{6})[^;]*/, '$1***') },
      plainPayload: { encodedPassword: kouling.slice(0, 120) },
    },
    response: {
      status,
      elapsedMs: elapsed,
      byteLength: Buffer.byteLength(bodyText, 'utf8'),
      empty: bodyText.trim().length === 0,
      raw: bodyText.slice(0, 20000),
      json: parsed,
      error: errMsg,
    },
    jump: parsed ? findUrl(parsed) : null,
  };
}

/* ------------------------------------------------------------------- 静态文件 */

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

function serveStatic(req, res) {
  let rel = decodeURIComponent(req.url.split('?')[0]);
  if (rel === '/' || rel === '') rel = '/index.html';

  const filePath = path.join(PUBLIC_DIR, path.normalize(rel).replace(/^([/\\])+/, ''));
  if (!filePath.startsWith(PUBLIC_DIR)) {
    res.writeHead(403).end('Forbidden');
    return;
  }

  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('404 Not Found');
      return;
    }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': 'no-cache',
    });
    res.end(data);
  });
}

/* --------------------------------------------------------------------- 路由 */

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname === '/api/health') {
    sendJson(res, 200, { ok: true, service: 'netease-kouling', port: PORT });
    return;
  }

  // 纯本地分析：不联网，只跑正则
  if (url.pathname === '/api/analyze' && req.method === 'POST') {
    try {
      const body = JSON.parse(await readBody(req));
      sendJson(res, 200, { ok: true, ...analyzeLocal(body.kouling || '') });
    } catch (e) {
      sendJson(res, 400, { ok: false, error: String(e.message || e) });
    }
    return;
  }

  // 真实调用接口
  if (url.pathname === '/api/decode' && req.method === 'POST') {
    try {
      const body = JSON.parse(await readBody(req));
      const kouling = body.kouling || '';
      if (!kouling.trim()) {
        sendJson(res, 400, { ok: false, error: '口令不能为空' });
        return;
      }

      const local = analyzeLocal(kouling);
      const remote = await callDecode({
        kouling,
        cookie: body.cookie,
        appver: body.appver || '9.1.0',
        host: body.host,
        apiPath: body.apiPath,
        timeout: body.timeout,
      });

      sendJson(res, 200, { ok: true, local, ...remote });
    } catch (e) {
      sendJson(res, 500, { ok: false, error: String(e.message || e) });
    }
    return;
  }

  serveStatic(req, res);
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('');
  console.log('  网易云口令解析器已启动');
  console.log(`  →  http://127.0.0.1:${PORT}`);
  console.log('');
  console.log('  接口：POST https://interface.music.163.com/eapi/password/url/decode/get');
  console.log('  按 Ctrl+C 停止');
  console.log('');
});