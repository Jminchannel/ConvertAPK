const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("child_process");
const net = require("net");
const path = require("path");
const fs = require("fs");

const BACKEND_HOST = "127.0.0.1";
let backendPort = Number(process.env.CONVERTAPK_PORT || 0);

let backendProcess = null;
let mainWindow = null;
let logPath = null;

function ensureLogPath() {
  if (logPath) {
    return logPath;
  }
  const configDir = path.join(app.getPath("appData"), "ConvertAPK");
  fs.mkdirSync(configDir, { recursive: true });
  logPath = path.join(configDir, "desktop.log");
  return logPath;
}

function logLine(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  try {
    fs.appendFileSync(ensureLogPath(), line, "utf-8");
  } catch (error) {
    // Logging must never crash the app.
  }
}

function loadClientConfig() {
  const configDir = path.join(app.getPath("appData"), "ConvertAPK");
  const configPath = path.join(configDir, "client-config.json");
  const defaults = {
    adminApiUrl: "http://8.148.250.84:9001",
    adminClientToken: "client-secret",
  };
  try {
    if (!fs.existsSync(configPath)) {
      fs.mkdirSync(configDir, { recursive: true });
      fs.writeFileSync(configPath, JSON.stringify(defaults, null, 2), "utf-8");
      return defaults;
    }
    const content = fs.readFileSync(configPath, "utf-8");
    const parsed = JSON.parse(content);
    const merged = { ...defaults, ...parsed };
    if (!merged.adminApiUrl || !merged.adminClientToken) {
      const normalized = {
        ...merged,
        adminApiUrl: merged.adminApiUrl || defaults.adminApiUrl,
        adminClientToken: merged.adminClientToken || defaults.adminClientToken,
      };
      fs.writeFileSync(configPath, JSON.stringify(normalized, null, 2), "utf-8");
      return normalized;
    }
    return merged;
  } catch (error) {
    return defaults;
  }
}

function loadBackendConfig() {
  const configDir = path.join(app.getPath("appData"), "ConvertAPK");
  const configPath = path.join(configDir, "config.json");
  try {
    if (!fs.existsSync(configPath)) {
      return {};
    }
    const content = fs.readFileSync(configPath, "utf-8");
    return JSON.parse(content);
  } catch (error) {
    return {};
  }
}

function resolveDataRoot(rawPath) {
  if (!rawPath || typeof rawPath !== "string") {
    return "";
  }
  const trimmed = rawPath.trim();
  if (!trimmed) {
    return "";
  }
  return path.isAbsolute(trimmed) ? trimmed : path.resolve(process.cwd(), trimmed);
}

function waitForPort(host, port, timeoutMs = 30000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const tryConnect = () => {
      const socket = new net.Socket();
      socket.setTimeout(1000);
      socket.once("error", () => {
        socket.destroy();
        if (Date.now() - started > timeoutMs) {
          reject(new Error("backend startup timeout"));
        } else {
          setTimeout(tryConnect, 500);
        }
      });
      socket.once("timeout", () => {
        socket.destroy();
        if (Date.now() - started > timeoutMs) {
          reject(new Error("backend startup timeout"));
        } else {
          setTimeout(tryConnect, 500);
        }
      });
      socket.connect(port, host, () => {
        socket.end();
        resolve();
      });
    };
    tryConnect();
  });
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, BACKEND_HOST, () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function waitForBackendReady(host, port, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (error) => {
      if (settled) return;
      settled = true;
      if (backendProcess) {
        backendProcess.off("exit", onExit);
        backendProcess.off("error", onError);
      }
      if (error) {
        reject(error);
      } else {
        resolve();
      }
    };
    const onExit = (code, signal) => {
      finish(new Error(`backend exited before ready (code ${code}, signal ${signal})`));
    };
    const onError = (error) => {
      finish(new Error(`backend failed to start: ${error.message}`));
    };
    waitForPort(host, port, timeoutMs).then(() => finish()).catch(finish);
    if (backendProcess) {
      backendProcess.once("exit", onExit);
      backendProcess.once("error", onError);
    }
  });
}

function startBackend() {
  const isPackaged = app.isPackaged;
  const clientConfig = loadClientConfig();
  const backendConfig = loadBackendConfig();
  const configuredDataRoot = resolveDataRoot(backendConfig.data_root);
  const fallbackDataRoot = path.join(app.getPath("appData"), "ConvertAPK");
  const env = {
    ...process.env,
    APK_BUILDER_MODE: "local",
    APK_BUILDER_DATA_DIR:
      process.env.APK_BUILDER_DATA_DIR || configuredDataRoot || fallbackDataRoot,
  };
  const adminApiUrl =
    process.env.CONVERTAPK_ADMIN_URL ||
    process.env.ADMIN_API_URL ||
    clientConfig.adminApiUrl ||
    "";
  const adminToken =
    process.env.CONVERTAPK_CLIENT_TOKEN ||
    process.env.ADMIN_CLIENT_TOKEN ||
    clientConfig.adminClientToken ||
    "";
  if (adminApiUrl) {
    env.ADMIN_API_URL = adminApiUrl;
  }
  if (adminToken) {
    env.ADMIN_CLIENT_TOKEN = adminToken;
  }
  env.CONVERTAPK_APP_VERSION = app.getVersion();

  let command = null;
  let args = [];
  let cwd = null;

  if (isPackaged) {
    const backendRoot = path.join(process.resourcesPath, "backend");
    const primaryExe = path.join(backendRoot, "convertapk-backend.exe");
    const nestedExe = path.join(backendRoot, "convertapk-backend", "convertapk-backend.exe");
    const backendExe = require("fs").existsSync(primaryExe) ? primaryExe : nestedExe;
    const frontendDir = path.join(process.resourcesPath, "frontend");
    env.FRONTEND_DIST_DIR = frontendDir;
    env.ELECTRON_RESOURCES = process.resourcesPath;
    command = backendExe;
    args = [];
    cwd = path.dirname(backendExe);
    if (!fs.existsSync(backendExe)) {
      throw new Error(`backend exe not found: ${backendExe}`);
    }
    if (!fs.existsSync(frontendDir)) {
      logLine(`[Main] frontend dist not found: ${frontendDir}`);
    }
  } else {
    const backendScript = path.join(__dirname, "..", "web", "backend", "main.py");
    const frontendDir = path.join(__dirname, "..", "web", "frontend", "dist");
    env.FRONTEND_DIST_DIR = frontendDir;
    command = process.env.CONVERTAPK_PYTHON || "python";
    args = [backendScript];
    cwd = path.dirname(backendScript);
  }

  if (!backendPort) {
    throw new Error("backend port not set");
  }
  env.CONVERTAPK_PORT = String(backendPort);

  logLine(`[Main] Starting backend: ${command}`);
  logLine(`[Main] Backend cwd: ${cwd}`);
  logLine(`[Main] Backend port: ${env.CONVERTAPK_PORT}`);
  logLine(`[Main] Backend data dir: ${env.APK_BUILDER_DATA_DIR}`);
  logLine(`[Main] ADMIN_API_URL set: ${Boolean(env.ADMIN_API_URL)}`);

  backendProcess = spawn(command, args, {
    env,
    cwd,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });

  // 捕获后端输出用于调试
  if (backendProcess.stdout) {
    backendProcess.stdout.on("data", (data) => {
      const text = data.toString().trim();
      console.log(`[Backend] ${text}`);
      logLine(`[Backend] ${text}`);
    });
  }
  if (backendProcess.stderr) {
    backendProcess.stderr.on("data", (data) => {
      const text = data.toString().trim();
      console.error(`[Backend Error] ${text}`);
      logLine(`[Backend Error] ${text}`);
    });
  }
  backendProcess.on("error", (err) => {
    console.error(`[Backend] Failed to start: ${err.message}`);
    logLine(`[Backend] Failed to start: ${err.message}`);
  });
  backendProcess.on("exit", (code, signal) => {
    console.log(`[Backend] Exited with code ${code}, signal ${signal}`);
    logLine(`[Backend] Exited with code ${code}, signal ${signal}`);
  });
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
  backendProcess = null;
}

async function createWindow() {
  const windowIcon = app.isPackaged
    ? path.join(process.resourcesPath, "icon.png")
    : path.join(__dirname, "build", "icon.png");
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: "#0b0f14",
    frame: false,
    titleBarStyle: "hidden",
    icon: windowIcon,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow = win;
  win.on("maximize", () => {
    win.webContents.send("window:state", { isMaximized: true });
  });
  win.on("unmaximize", () => {
    win.webContents.send("window:state", { isMaximized: false });
  });
  const isLocalUrl = (url) => {
    try {
      const parsed = new URL(url);
      return parsed.hostname === BACKEND_HOST && String(parsed.port) === String(backendPort);
    } catch (error) {
      return false;
    }
  };
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (!isLocalUrl(url)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  await win.loadURL(`http://${BACKEND_HOST}:${backendPort}/`);
}

ipcMain.handle("window:minimize", () => {
  if (mainWindow) {
    mainWindow.minimize();
  }
});

ipcMain.handle("window:toggle-maximize", () => {
  if (!mainWindow) return;
  if (mainWindow.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow.maximize();
  }
});

ipcMain.handle("window:close", () => {
  if (mainWindow) {
    mainWindow.close();
  }
});

ipcMain.handle("window:is-maximized", () => {
  return mainWindow ? mainWindow.isMaximized() : false;
});

ipcMain.handle("dialog:select-directory", async (_event, options = {}) => {
  const defaultPath =
    typeof options.defaultPath === "string" && options.defaultPath.trim()
      ? options.defaultPath
      : app.getPath("documents");
  const result = await dialog.showOpenDialog({
    title: "Select Directory",
    defaultPath,
    properties: ["openDirectory", "createDirectory"],
  });
  if (result.canceled) {
    return "";
  }
  return result.filePaths && result.filePaths[0] ? result.filePaths[0] : "";
});

app.whenReady().then(async () => {
  try {
    backendPort = backendPort || (await getFreePort());
    console.log(`[Main] Starting backend on port ${backendPort}`);
    logLine(`[Main] Starting backend on port ${backendPort}`);
    startBackend();
    console.log(`[Main] Waiting for backend to be ready...`);
    logLine("[Main] Waiting for backend to be ready...");
    await waitForBackendReady(BACKEND_HOST, backendPort, 45000);
    console.log(`[Main] Backend is ready, creating window`);
    logLine("[Main] Backend is ready, creating window");
    await createWindow();
  } catch (error) {
    const logFile = logPath ? logPath : "(log unavailable)";
    const errorMsg = `启动失败: ${String(error)}\n\n后端端口: ${backendPort}\n\n请检查:\n1. 后端 EXE 是否存在\n2. 端口是否被占用\n3. 查看日志: ${logFile}`;
    console.error(errorMsg);
    logLine(`[Main] Startup failed: ${String(error)}`);
    dialog.showErrorBox("ConvertAPK 启动失败", errorMsg);
    app.quit();
  }
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackend();
});
