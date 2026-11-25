#!/usr/bin/env node
/**
 * eapi 加密客户端（Node.js 版）—— 实测可用的口令解析
 *
 * 为什么需要 Node 版：
 *   同样的加密内容和请求头，Python urllib / curl 在部分网络环境会拿到空响应，
 *   而 Node.js 的 fetch（undici）能正常返回。这不是加密问题，是客户端/网关差异。
 *   实战中 Python 版失败了，换 Node 版立刻跑通。
 *
 * 用法：
 *   node eapi_client.js <口令文本>
 */

const crypto = require('crypto');

const EAPI_KEY = Buffer.from('e82ckenh8dichen8');
const SEP = '-36cd479b6b5-';
const GATEWAY = 'interface.music.163.com';

/**
 * eapi 加密
 * 注意：apiPath 用 /api/ 前缀参与签名，但实际请求要发到 /eapi/ 路径。
 */
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

async function decodeKouling(kouling, appver = '9.1.0') {
  const apiPath = '/api/password/url/decode/get';
  const endpoint = `https://${GATEWAY}${apiPath.replace('/api/', '/eapi/')}`;

  const params = eapiEncrypt(apiPath, { encodedPassword: kouling });

  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'User-Agent': `NeteaseMusic/${appver}.231018165600(9010000);Dalvik/2.1.0`,
      Cookie: `os=android; appver=${appver}; osver=13; channel=netease;`,
    },
    body: new URLSearchParams({ params }).toString(),
    signal: AbortSignal.timeout(20000),
  });

  const raw = await resp.text();
  if (!raw.trim()) {
    throw new Error(
      `服务端返回空响应 (HTTP ${resp.status})。` +
        '可尝试换 appver、检查代理，或用抓包工具直接看这条请求。'
    );
  }
  return { status: resp.status, raw, json: JSON.parse(raw) };
}

/** 本地分析：复刻客户端预处理（先删空格、再删换行） */
function analyzeLocal(kouling) {
  const cleaned = String(kouling).replace(/ /g, '').replace(/\n/g, '');
  const matched = /.*\$.+\$.*/s.test(cleaned);
  const segments = [];
  const re = /\$([^$]*)\$/g;
  let m;
  while ((m = re.exec(cleaned)) !== null) {
    segments.push({ full: m[0], inner: m[1], index: m.index });
  }
  return { cleaned, matched, segments };
}

async function main() {
  const kouling = process.argv.slice(2).join(' ');
  if (!kouling) {
    console.log('用法: node eapi_client.js <口令文本>');
    process.exit(1);
  }

  const local = analyzeLocal(kouling);
  console.log('=== 本地分析 ===');
  console.log(`特征匹配: ${local.matched ? '命中' : '未命中'}`);
  local.segments.forEach((s, i) => {
    console.log(`  [${i + 1}] 短码: ${s.inner}  (位置 ${s.index})`);
  });
  console.log();

  console.log('=== 调用接口 ===');
  try {
    const { status, json } = await decodeKouling(kouling);
    console.log(`HTTP ${status}`);
    console.log(JSON.stringify(json, null, 2));
    console.log();

    if (json.code === 200) {
      const url = json.data && json.data.decodedUrl;
      if (url) {
        console.log('=== 跳转地址 ===');
        console.log(url);
      }
    } else {
      console.log(`业务错误: code=${json.code} ${json.message || ''}`);
    }
  } catch (e) {
    console.error(`失败: ${e.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { eapiEncrypt, decodeKouling, analyzeLocal };