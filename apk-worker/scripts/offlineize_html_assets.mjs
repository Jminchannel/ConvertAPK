#!/usr/bin/env node

import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";

const cliArgs = process.argv.slice(2);
let entryArg = "";
const rawAllowUrls = [];
for (let i = 0; i < cliArgs.length; i += 1) {
  const arg = cliArgs[i];
  if (arg === "--allow-url") {
    if (i + 1 < cliArgs.length) {
      rawAllowUrls.push(cliArgs[i + 1]);
      i += 1;
    }
    continue;
  }
  if (!entryArg && !String(arg || "").startsWith("--")) {
    entryArg = arg;
  }
}

if (!entryArg) {
  console.error("[offlineize] usage: node offlineize_html_assets.mjs <path-to-index.html> [--allow-url <url>...]");
  process.exit(2);
}

const entryFile = path.resolve(entryArg);
const rootDir = path.dirname(entryFile);
const offlineRoot = path.join(rootDir, "assets", "remote");
const remoteToLocal = new Map();
const sourceBaseByFile = new Map();
const failedCanonicalUrls = new Set();

let downloadCount = 0;
let replaceCount = 0;
let failCount = 0;

const IMAGE_EXT = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".avif", ".apng"]);
const AUDIO_EXT = new Set([".mp3", ".wav", ".ogg", ".aac", ".m4a", ".flac", ".opus"]);
const VIDEO_EXT = new Set([".mp4", ".webm", ".mov", ".mkv", ".m3u8", ".ts", ".avi"]);
const FONT_EXT = new Set([".woff", ".woff2", ".ttf", ".otf", ".eot"]);

const MIME_TO_EXT = new Map([
  ["text/css", ".css"],
  ["application/javascript", ".js"],
  ["text/javascript", ".js"],
  ["application/x-javascript", ".js"],
  ["application/json", ".json"],
  ["image/svg+xml", ".svg"],
  ["image/png", ".png"],
  ["image/jpeg", ".jpg"],
  ["image/webp", ".webp"],
  ["audio/mpeg", ".mp3"],
  ["audio/ogg", ".ogg"],
  ["video/mp4", ".mp4"],
  ["font/woff2", ".woff2"],
  ["font/woff", ".woff"],
]);

function isSkippableUrl(raw) {
  const value = String(raw || "").trim();
  if (!value) return true;
  const lower = value.toLowerCase();
  return (
    lower.startsWith("#") ||
    lower.startsWith("javascript:") ||
    lower.startsWith("mailto:") ||
    lower.startsWith("tel:") ||
    lower.startsWith("data:") ||
    lower.startsWith("blob:")
  );
}

function toRemoteUrl(raw, baseUrl = "") {
  const value = String(raw || "").trim();
  if (!value || isSkippableUrl(value)) return null;

  if (value.startsWith("//")) {
    return `https:${value}`;
  }
  if (/^https?:\/\//i.test(value)) {
    return value;
  }
  if (!baseUrl) return null;
  try {
    return new URL(value, baseUrl).toString();
  } catch {
    return null;
  }
}

function localFileCandidate(ownerFile, rawUrl) {
  const value = String(rawUrl || "").trim();
  if (!value) return "";
  if (value.startsWith("//")) return "";
  if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(value)) return "";
  const withoutHash = value.split("#")[0] || value;
  const withoutQuery = withoutHash.split("?")[0] || withoutHash;
  if (!withoutQuery) return "";
  return path.resolve(path.dirname(ownerFile), withoutQuery);
}

function canonicalRemoteUrl(raw) {
  const u = new URL(raw);
  u.hash = "";
  return u.toString();
}

function normalizeAllowUrl(raw) {
  const value = String(raw || "").trim();
  if (!value) return "";
  const candidate = value.startsWith("//") ? `https:${value}` : value;
  if (!/^https?:\/\//i.test(candidate)) return "";
  try {
    return canonicalRemoteUrl(candidate);
  } catch {
    return "";
  }
}

const allowCanonicalUrls = new Set(rawAllowUrls.map(normalizeAllowUrl).filter(Boolean));

function sanitizeSegment(seg) {
  const clean = String(seg || "")
    .replace(/%[0-9A-Fa-f]{2}/g, "_")
    .replace(/[^a-zA-Z0-9._-]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  return clean || "item";
}

function extFromMime(mime) {
  const normalized = String(mime || "").split(";")[0].trim().toLowerCase();
  return MIME_TO_EXT.get(normalized) || "";
}

function bucketFromExtOrMime(ext, mime) {
  const m = String(mime || "").toLowerCase();
  if (ext === ".css" || m.includes("text/css")) return "css";
  if (ext === ".js" || m.includes("javascript")) return "js";
  if (IMAGE_EXT.has(ext) || m.startsWith("image/")) return "images";
  if (AUDIO_EXT.has(ext) || m.startsWith("audio/")) return "audio";
  if (VIDEO_EXT.has(ext) || m.startsWith("video/")) return "video";
  if (FONT_EXT.has(ext) || m.startsWith("font/")) return "fonts";
  return "files";
}

function defaultExtForBucket(bucket) {
  switch (bucket) {
    case "css":
      return ".css";
    case "js":
      return ".js";
    case "images":
      return ".png";
    case "audio":
      return ".mp3";
    case "video":
      return ".mp4";
    case "fonts":
      return ".woff2";
    default:
      return ".bin";
  }
}

function buildLocalPath(remoteUrl, mime = "") {
  const u = new URL(remoteUrl);
  const host = sanitizeSegment(u.hostname || "remote");
  const pathname = u.pathname || "/";
  const rawParts = pathname.split("/").filter(Boolean);
  const parts = rawParts.map((p) => {
    try {
      return sanitizeSegment(decodeURIComponent(p));
    } catch {
      return sanitizeSegment(p);
    }
  });

  let fileName = parts.pop() || "index";
  let ext = path.extname(fileName).toLowerCase();
  const mimeExt = extFromMime(mime);
  const bucket = bucketFromExtOrMime(ext || mimeExt, mime);

  if (!ext) {
    ext = mimeExt || defaultExtForBucket(bucket);
  }

  const base = sanitizeSegment(fileName.slice(0, fileName.length - path.extname(fileName).length)) || "asset";
  const hash = crypto.createHash("md5").update(remoteUrl).digest("hex").slice(0, 8);
  const finalName = `${base}_${hash}${ext}`;

  return path.join(offlineRoot, bucket, host, ...parts, finalName);
}

function toRelativeAssetPath(ownerFile, targetFile) {
  let rel = path.relative(path.dirname(ownerFile), targetFile).replace(/\\/g, "/");
  if (!rel.startsWith(".")) rel = `./${rel}`;
  return rel;
}

async function fetchWithRetry(url, retries = 2) {
  let lastError = null;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const timeout = 30000 + attempt * 15000;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const res = await fetch(url, {
        redirect: "follow",
        signal: controller.signal,
        headers: {
          "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36",
          Accept: "*/*",
        },
      });
      clearTimeout(timer);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      return res;
    } catch (error) {
      clearTimeout(timer);
      lastError = error;
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, 800 * (attempt + 1)));
      }
    }
  }
  throw lastError || new Error("fetch failed");
}

async function downloadRemoteAsset(remoteUrl) {
  const canonical = canonicalRemoteUrl(remoteUrl);
  if (remoteToLocal.has(canonical)) {
    return remoteToLocal.get(canonical);
  }

  const response = await fetchWithRetry(canonical);
  const mime = String(response.headers.get("content-type") || "")
    .split(";")[0]
    .trim()
    .toLowerCase();
  const localPath = buildLocalPath(canonical, mime);
  const localDir = path.dirname(localPath);
  await fsp.mkdir(localDir, { recursive: true });

  const tempPath = `${localPath}.part`;
  try {
    if (response.body) {
      await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(tempPath));
    } else {
      const buf = Buffer.from(await response.arrayBuffer());
      await fsp.writeFile(tempPath, buf);
    }
    await fsp.rename(tempPath, localPath);
  } catch (error) {
    await fsp.rm(tempPath, { force: true }).catch(() => {});
    throw error;
  }

  remoteToLocal.set(canonical, localPath);
  sourceBaseByFile.set(path.resolve(localPath), canonical);
  downloadCount += 1;
  console.log(`[offlineize] saved: ${canonical} -> ${path.relative(rootDir, localPath).replace(/\\/g, "/")}`);
  return localPath;
}

async function localizeUrl(rawUrl, ownerFile, baseUrl = "") {
  const localCandidate = localFileCandidate(ownerFile, rawUrl);
  if (localCandidate && fs.existsSync(localCandidate)) {
    return rawUrl;
  }

  const remote = toRemoteUrl(rawUrl, baseUrl);
  if (!remote) return rawUrl;
  let canonical = "";
  try {
    canonical = canonicalRemoteUrl(remote);
  } catch {
    return rawUrl;
  }
  if (failedCanonicalUrls.has(canonical)) {
    return rawUrl;
  }
  if (allowCanonicalUrls.size > 0) {
    if (!allowCanonicalUrls.has(canonical)) {
      return rawUrl;
    }
  }

  try {
    const localPath = await downloadRemoteAsset(canonical);
    const localized = toRelativeAssetPath(ownerFile, localPath);
    if (localized !== rawUrl) {
      replaceCount += 1;
    }
    return localized;
  } catch (error) {
    failedCanonicalUrls.add(canonical);
    failCount += 1;
    console.warn(`[offlineize] failed: ${remote} (${error.message || error})`);
    return rawUrl;
  }
}

async function replaceAsync(text, regex, replacer) {
  let output = "";
  let lastIndex = 0;
  for (const match of text.matchAll(regex)) {
    const idx = match.index ?? 0;
    output += text.slice(lastIndex, idx);
    output += await replacer(match);
    lastIndex = idx + match[0].length;
  }
  output += text.slice(lastIndex);
  return output;
}

async function processCssText(cssText, ownerFile, baseUrl = "") {
  let text = cssText;

  text = await replaceAsync(
    text,
    /@import\s+(?:url\(\s*)?(["']?)([^"')\s]+)\1\s*\)?([^;]*);/gi,
    async (m) => {
      const localized = await localizeUrl(m[2], ownerFile, baseUrl);
      return `@import url("${localized}")${m[3]};`;
    }
  );

  text = await replaceAsync(
    text,
    /url\(\s*(["']?)([^"')]+)\1\s*\)/gi,
    async (m) => {
      const localized = await localizeUrl(m[2], ownerFile, baseUrl);
      return `url("${localized}")`;
    }
  );

  return text;
}

async function processHtmlFile(htmlFile) {
  const originText = await fsp.readFile(htmlFile, "utf8");
  let text = originText;

  text = await replaceAsync(
    text,
    /(<(?:img|script|link|audio|video|source|track|iframe|embed)\b[^>]*?\b(?:src|href|poster|data-src|data-href|data-poster)\s*=\s*)(["'])([^"']+)\2/gi,
    async (m) => {
      const localized = await localizeUrl(m[3], htmlFile, "");
      return `${m[1]}${m[2]}${localized}${m[2]}`;
    }
  );

  text = await replaceAsync(
    text,
    /(<(?:img|source)\b[^>]*?\bsrcset\s*=\s*)(["'])([^"']+)\2/gi,
    async (m) => {
      const entries = m[3]
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const rewritten = [];
      for (const entry of entries) {
        const parts = entry.split(/\s+/);
        const src = parts.shift() || "";
        const localized = await localizeUrl(src, htmlFile, "");
        rewritten.push([localized, ...parts].join(" "));
      }
      return `${m[1]}${m[2]}${rewritten.join(", ")}${m[2]}`;
    }
  );

  text = await replaceAsync(
    text,
    /(<style\b[^>]*>)([\s\S]*?)(<\/style>)/gi,
    async (m) => {
      const css = await processCssText(m[2], htmlFile, "");
      return `${m[1]}${css}${m[3]}`;
    }
  );

  text = await replaceAsync(
    text,
    /(style\s*=\s*)(["'])([\s\S]*?)\2/gi,
    async (m) => {
      const css = await processCssText(m[3], htmlFile, "");
      return `${m[1]}${m[2]}${css}${m[2]}`;
    }
  );

  if (text !== originText) {
    await fsp.writeFile(htmlFile, text, "utf8");
    return true;
  }
  return false;
}

async function processCssFile(cssFile) {
  const source = await fsp.readFile(cssFile, "utf8");
  const baseUrl = sourceBaseByFile.get(path.resolve(cssFile)) || "";
  const rewritten = await processCssText(source, cssFile, baseUrl);
  if (rewritten !== source) {
    await fsp.writeFile(cssFile, rewritten, "utf8");
    return true;
  }
  return false;
}

async function collectFiles(dir, extensions) {
  const found = [];
  const stack = [dir];
  while (stack.length > 0) {
    const current = stack.pop();
    const entries = await fsp.readdir(current, { withFileTypes: true });
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === ".git" || entry.name === "node_modules" || entry.name === ".gradle") continue;
        stack.push(full);
        continue;
      }
      const ext = path.extname(entry.name).toLowerCase();
      if (extensions.has(ext)) {
        found.push(full);
      }
    }
  }
  return found;
}

async function main() {
  const stat = await fsp.stat(entryFile).catch(() => null);
  if (!stat || !stat.isFile()) {
    throw new Error(`entry html not found: ${entryFile}`);
  }

  await fsp.mkdir(offlineRoot, { recursive: true });
  const htmlFiles = await collectFiles(rootDir, new Set([".html", ".htm"]));
  for (const htmlFile of htmlFiles) {
    await processHtmlFile(htmlFile);
  }

  for (let round = 0; round < 5; round += 1) {
    const cssFiles = await collectFiles(rootDir, new Set([".css"]));
    let changed = false;
    for (const cssFile of cssFiles) {
      const result = await processCssFile(cssFile);
      changed = changed || result;
    }
    if (!changed) {
      break;
    }
  }

  console.log(
    `[offlineize] done. downloaded=${downloadCount}, rewritten=${replaceCount}, failed=${failCount}, root=${path.relative(process.cwd(), rootDir).replace(/\\/g, "/")}`
  );
}

main().catch((error) => {
  console.error(`[offlineize] fatal: ${error.message || error}`);
  process.exit(1);
});
