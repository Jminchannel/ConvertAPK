import assert from "node:assert/strict";
import { once } from "node:events";
import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const offlineizerPath = path.resolve(testDirectory, "../scripts/offlineize_html_assets.mjs");

function runOfflineizer(entryFile, allowedUrls) {
  return new Promise((resolve, reject) => {
    const args = [offlineizerPath, entryFile];
    for (const allowedUrl of allowedUrls) {
      args.push("--allow-url", allowedUrl);
    }

    const child = spawn(process.execPath, args, { stdio: ["ignore", "pipe", "pipe"] });
    let output = "";
    child.stdout.on("data", (chunk) => {
      output += chunk;
    });
    child.stderr.on("data", (chunk) => {
      output += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve(output);
        return;
      }
      reject(new Error(`offlineizer exited with ${code}: ${output}`));
    });
  });
}

function findTag(html, marker) {
  const tag = html.match(new RegExp(`<[^>]*${marker}[^>]*>`, "i"));
  assert.ok(tag, `missing tag containing ${marker}`);
  return tag[0];
}

test("removes stale SRI only from localized assets whose content changed", async (t) => {
  const server = http.createServer((request, response) => {
    if (request.url === "/styles.css") {
      response.writeHead(200, { "content-type": "text/css" });
      response.end(".marker { background-image: url('./marker.png'); }");
      return;
    }
    if (request.url === "/runtime.js") {
      response.writeHead(200, { "content-type": "application/javascript" });
      response.end("window.offlineizerRegression = true;");
      return;
    }
    if (request.url === "/stable.css") {
      response.writeHead(200, { "content-type": "text/css" });
      response.end(".stable { color: blue; }");
      return;
    }
    if (request.url === "/marker.png") {
      response.writeHead(200, { "content-type": "image/png" });
      response.end(Buffer.from([137, 80, 78, 71]));
      return;
    }
    response.writeHead(404);
    response.end();
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => server.close());

  const address = server.address();
  assert.equal(typeof address, "object");
  const baseUrl = `http://127.0.0.1:${address.port}`;
  const cssUrl = `${baseUrl}/styles.css`;
  const scriptUrl = `${baseUrl}/runtime.js`;
  const stableCssUrl = `${baseUrl}/stable.css`;
  const tempDirectory = await fs.mkdtemp(path.join(os.tmpdir(), "offlineizer-sri-"));
  t.after(() => fs.rm(tempDirectory, { recursive: true, force: true }));

  const entryFile = path.join(tempDirectory, "index.html");
  await fs.writeFile(
    entryFile,
    `<link rel="stylesheet" href="${cssUrl}" integrity="sha256-css-original" crossorigin="anonymous">\n` +
      `<script src="${scriptUrl}" integrity="sha256-script-original" crossorigin="anonymous"></script>\n` +
      `<link rel="stylesheet" href="${stableCssUrl}" integrity="sha256-stable-original" crossorigin="anonymous">\n`,
    "utf8"
  );

  await runOfflineizer(entryFile, [cssUrl, scriptUrl, stableCssUrl]);

  const outputHtml = await fs.readFile(entryFile, "utf8");
  const cssTag = findTag(outputHtml, "styles_");
  const scriptTag = findTag(outputHtml, "runtime_");
  const stableCssTag = findTag(outputHtml, "stable_");
  assert.match(cssTag, /href="\.\/assets\/remote\/css\//);
  assert.doesNotMatch(cssTag, /\sintegrity=/i);
  assert.match(scriptTag, /integrity="sha256-script-original"/);
  assert.match(stableCssTag, /integrity="sha256-stable-original"/);

  const cssDirectory = path.join(tempDirectory, "assets", "remote", "css", "127.0.0.1");
  const cssFileName = (await fs.readdir(cssDirectory)).find((name) => name.startsWith("styles_"));
  assert.ok(cssFileName, "missing localized stylesheet");
  const outputCss = await fs.readFile(path.join(cssDirectory, cssFileName), "utf8");
  assert.match(outputCss, /marker_[0-9a-f]{8}\.png/);
  assert.doesNotMatch(outputCss, /url\(['"]?\.\/marker\.png/);
});
