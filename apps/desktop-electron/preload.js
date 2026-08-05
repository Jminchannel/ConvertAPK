const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("windowControls", {
  minimize: () => ipcRenderer.invoke("window:minimize"),
  toggleMaximize: () => ipcRenderer.invoke("window:toggle-maximize"),
  close: () => ipcRenderer.invoke("window:close"),
  isMaximized: () => ipcRenderer.invoke("window:is-maximized"),
  onState: (handler) => {
    const listener = (_event, state) => handler(state);
    ipcRenderer.on("window:state", listener);
    return () => ipcRenderer.removeListener("window:state", listener);
  },
});

let fs = null;
let path = null;
try {
  fs = require("fs");
  path = require("path");
} catch (error) {
  fs = null;
  path = null;
}

const resolveAppDataDir = () => {
  if (process.env.APPDATA && process.env.APPDATA.trim()) {
    return process.env.APPDATA;
  }
  if (process.platform === "darwin") {
    const home = process.env.HOME || process.env.USERPROFILE || "";
    return path && home ? path.join(home || process.cwd(), "Library", "Application Support") : process.cwd();
  }
  if (process.env.XDG_CONFIG_HOME && process.env.XDG_CONFIG_HOME.trim()) {
    return process.env.XDG_CONFIG_HOME;
  }
  const home = process.env.HOME || process.env.USERPROFILE || "";
  return path && home ? path.join(home, ".config") : process.cwd();
};

const getOrCreateClientId = () => {
  if (!fs || !path) {
    return (
      "client_" +
      Date.now() +
      "_" +
      Math.random().toString(36).slice(2, 10)
    );
  }
  const appDataDir = resolveAppDataDir();
  const configDir = path.join(appDataDir, "ConvertAPK");
  const clientIdPath = path.join(configDir, "client-id.txt");
  try {
    if (!fs.existsSync(configDir)) {
      fs.mkdirSync(configDir, { recursive: true });
    }
    if (fs.existsSync(clientIdPath)) {
      const existing = fs.readFileSync(clientIdPath, "utf-8").trim();
      if (existing) {
        return existing;
      }
    }
    const generated =
      "client_" +
      Date.now() +
      "_" +
      Math.random().toString(36).slice(2, 10);
    fs.writeFileSync(clientIdPath, generated, "utf-8");
    return generated;
  } catch (error) {
    return (
      "client_" +
      Date.now() +
      "_" +
      Math.random().toString(36).slice(2, 10)
    );
  }
};

const clientId = getOrCreateClientId();

contextBridge.exposeInMainWorld("appDialogs", {
  selectDirectory: (defaultPath) =>
    ipcRenderer.invoke("dialog:select-directory", { defaultPath }),
});

contextBridge.exposeInMainWorld("appClient", {
  clientId,
});
