const { app, BrowserWindow } = require('electron');
const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');

let backendProc = null;
let mainWindow = null;

function waitForBackend(url, timeout=30000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      http.get(url, res => {
        if (res.statusCode === 200) resolve();
        else if (Date.now() - start > timeout) reject(new Error('timeout'));
        else setTimeout(check, 500);
      }).on('error', () => {
        if (Date.now() - start > timeout) reject(new Error('timeout'));
        else setTimeout(check, 500);
      });
    };
    check();
  });
}

function startBackend() {
  const isDev = !app.isPackaged;
  const backendDir = isDev
    ? path.join(__dirname, '..', 'pdf-toolkit', 'backend')
    : path.join(process.resourcesPath, 'backend');

  const py = 'C:\\Users\\LOX\\AppData\\Local\\Programs\\Python\\Python312\\python.exe';
  // In packaged app, we expect backend.exe via pyinstaller in resources
  const backendExe = path.join(process.resourcesPath, 'backend', 'backend.exe');
  const fs = require('fs');
  let proc;
  if (fs.existsSync(backendExe)) {
    proc = spawn(backendExe, [], { cwd: backendDir, windowsHide: true });
  } else {
    proc = spawn(py, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], {
      cwd: backendDir, windowsHide: true
    });
  }
  proc.stdout && proc.stdout.on('data', d => console.log('[backend]', d.toString()));
  proc.stderr && proc.stderr.on('data', d => console.error('[backend]', d.toString()));
  backendProc = proc;
  return proc;
}

function startFrontend() {
  const isDev = !app.isPackaged;
  const frontendDir = isDev
    ? path.join(__dirname, '..', 'pdf-toolkit', 'frontend')
    : path.join(process.resourcesPath, 'frontend');
  // both dev and prod need Next.js server on 3000
  const cmd = isDev ? 'npm run dev -- --port 3000 --hostname 127.0.0.1' : 'npx next start -p 3000 -H 127.0.0.1';
  return spawn('cmd.exe', ['/c', cmd], {
    cwd: frontendDir, windowsHide: true, shell: true
  });
}

app.whenReady().then(async () => {
  startBackend();
  const frontendProc = startFrontend();

  try {
    await waitForBackend('http://127.0.0.1:8000/health', 20000);
    await waitForBackend('http://127.0.0.1:3000', 20000);
  } catch (e) {
    console.error('servers not ready', e);
  }

  mainWindow = new BrowserWindow({
    width: 1280, height: 860,
    title: 'PDF Toolkit — BETA',
    backgroundColor: '#fbfaf8',
    autoHideMenuBar: true,
    icon: path.join(__dirname, 'icon.ico')
  });
  mainWindow.loadURL('http://127.0.0.1:3000');

  mainWindow.on('closed', () => {
    mainWindow = null;
    if (backendProc) backendProc.kill();
    if (frontendProc) frontendProc.kill();
  });
});

app.on('window-all-closed', () => {
  if (backendProc) backendProc.kill();
  app.quit();
});
app.on('before-quit', () => {
  if (backendProc) backendProc.kill();
});
