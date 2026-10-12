const { app, BrowserWindow, dialog, shell, session } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');
const https = require('https');
const net = require('net');

let window;
let shuttingDown = false;
const children = new Set();
let logPath;

const resources = () => app.isPackaged ? process.resourcesPath : path.join(__dirname, 'runtime');
const smokeResult = process.argv.find(value => value.startsWith('--smoke-result='))?.slice(15);
const smokeTest = process.argv.includes('--smoke-test');

function log(message) {
  const line = `${new Date().toISOString()} ${message}\n`;
  if (logPath) {
    try { fs.appendFileSync(logPath, line); } catch {}
  }
}

function launch(command, args, options = {}) {
  const child = spawn(command, args, { windowsHide: true, ...options });
  children.add(child);
  child.stdout?.on('data', data => log(data.toString().trimEnd()));
  child.stderr?.on('data', data => log(data.toString().trimEnd()));
  child.on('error', error => { child.startError = error; log(error.message); });
  child.on('exit', (code, signal) => { children.delete(child); log(`Process ${child.pid} stopped (${code ?? signal})`); });
  return child;
}

function run(command, args, options) {
  return new Promise((resolve, reject) => {
    const child = launch(command, args, options);
    let output = '';
    child.stdout?.on('data', data => { output += data; });
    child.stderr?.on('data', data => { output += data; });
    child.once('error', reject);
    child.once('exit', code => code === 0 ? resolve(output.trim()) : reject(new Error(`${command} завершился с кодом ${code}.\n${output.slice(-1800)}`)));
  });
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

function request(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https:') ? https : http;
    const req = client.get(url, response => {
      response.resume();
      response.on('end', () => resolve(response.statusCode));
    });
    req.setTimeout(3000, () => req.destroy(new Error('Request timeout')));
    req.once('error', reject);
  });
}

function fetchJson(url, timeoutMs = 4500, redirects = 5) {
  return new Promise((resolve, reject) => {
    if (redirects < 0) return reject(new Error('Too many redirects'));
    const client = url.startsWith('https:') ? https : http;
    const req = client.get(url, {
      headers: {
        'User-Agent': 'PDF-Toolkit-Desktop-AutoUpdater',
        'Accept': 'application/vnd.github+json'
      }
    }, res => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        res.resume();
        const nextUrl = new URL(res.headers.location, url).toString();
        return resolve(fetchJson(nextUrl, timeoutMs, redirects - 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
      }
      let body = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { body += chunk; });
      res.on('end', () => {
        try { resolve(JSON.parse(body)); }
        catch (err) { reject(err); }
      });
    });
    req.setTimeout(timeoutMs, () => req.destroy(new Error('GitHub check timeout')));
    req.once('error', reject);
  });
}

function downloadFile(url, destPath, timeoutMs = 180000, redirects = 8) {
  return new Promise((resolve, reject) => {
    if (redirects < 0) return reject(new Error('Too many redirects'));
    const client = url.startsWith('https:') ? https : http;
    const req = client.get(url, {
      headers: { 'User-Agent': 'PDF-Toolkit-Desktop-AutoUpdater' }
    }, res => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        res.resume();
        const nextUrl = new URL(res.headers.location, url).toString();
        return resolve(downloadFile(nextUrl, destPath, timeoutMs, redirects - 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`Download failed with HTTP ${res.statusCode}`));
      }
      const file = fs.createWriteStream(destPath);
      res.pipe(file);
      file.on('finish', () => file.close(() => resolve(destPath)));
      file.once('error', err => {
        try { fs.unlinkSync(destPath); } catch {}
        reject(err);
      });
    });
    req.setTimeout(timeoutMs, () => req.destroy(new Error('Download timeout')));
    req.once('error', reject);
  });
}

async function waitReady(url, child, timeout = 60000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline && !shuttingDown) {
    if (child.startError) throw child.startError;
    if (child.exitCode !== null || child.signalCode !== null) throw new Error('Локальный сервер остановился. Подробности сохранены в журнале.');
    try { if (await request(url) === 200) return; } catch {}
    await new Promise(resolve => setTimeout(resolve, 400));
  }
  throw new Error('Сервер приложения не успел запуститься. Подробности сохранены в журнале.');
}

function startupScreen(message) {
  if (!window) return;
  const safe = message.replace(/[&<>"']/g, value => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[value]));
  window.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html><html lang="ru"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>PDF Toolkit</title><style>body{margin:0;background:#f6f7fb;font:16px system-ui;color:#203348;display:grid;place-content:center;min-height:100vh;text-align:center}b{font-size:34px;letter-spacing:-1px}p{color:#68778a;max-width:520px;line-height:1.7;padding:0 24px}.dot{width:40px;height:40px;border:4px solid #dce4f3;border-top-color:#5277ed;border-radius:100%;margin:32px auto;animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.dot{animation:none}}</style><b>PDF Toolkit</b><div class="dot"></div><p>${safe}</p></html>`)}`);
}

function patchBackendCompatibility(backendDir) {
  try {
    const mainPy = path.join(backendDir, 'app', 'main.py');
    if (fs.existsSync(mainPy)) {
      let content = fs.readFileSync(mainPy, 'utf8');
      if (!content.includes('"/api/health"')) {
        content = content.replace('@app.get("/health")', '@app.get("/health")\n@app.get("/api/health")');
        fs.writeFileSync(mainPy, content, 'utf8');
      }
    }
    const configPy = path.join(backendDir, 'app', 'config.py');
    if (fs.existsSync(configPy)) {
      let content = fs.readFileSync(configPy, 'utf8');
      if (!content.includes('PDF_TOOLKIT_TMP_DIR')) {
        content = content.replace(
          /TMP_ROOT\s*=\s*os\.getenv\("TMP_ROOT".*?\)/,
          'TMP_ROOT = os.getenv("TMP_ROOT") or os.getenv("PDF_TOOLKIT_TMP_DIR") or os.path.join(tempfile.gettempdir(), "pdf-toolkit")'
        );
        fs.writeFileSync(configPy, content, 'utf8');
      }
    }
  } catch (err) {
    log(`patchBackendCompatibility warning: ${err.message}`);
  }
}

function prepareLiveBackend() {
  const configPath = path.join(resources(), 'desktop-runtime.json');
  const runtimeConfig = fs.existsSync(configPath) ? JSON.parse(fs.readFileSync(configPath, 'utf8')) : {};
  const liveBackendDir = path.join(app.getPath('userData'), 'live-backend');
  const statePath = path.join(app.getPath('userData'), 'update-state.json');
  let state = fs.existsSync(statePath) ? JSON.parse(fs.readFileSync(statePath, 'utf8')) : null;

  const saveState = newState => {
    state = { ...state, ...newState };
    fs.writeFileSync(statePath, JSON.stringify(state, null, 2), 'utf8');
  };

  if (!state || state.builtAt !== runtimeConfig.builtAt || !fs.existsSync(path.join(liveBackendDir, 'app', 'main.py'))) {
    fs.rmSync(liveBackendDir, { recursive: true, force: true });
    fs.mkdirSync(liveBackendDir, { recursive: true });
    fs.cpSync(path.join(resources(), 'backend'), liveBackendDir, { recursive: true });
    patchBackendCompatibility(liveBackendDir);
    saveState({
      repo: runtimeConfig.repo || 'khusan-1-lox/pdf-toolkit',
      branch: runtimeConfig.branch || 'main',
      commitSha: runtimeConfig.commitSha || null,
      builtAt: runtimeConfig.builtAt || new Date().toISOString(),
      installedReleaseId: state?.installedReleaseId || null,
      lastReleasePublishedAt: runtimeConfig.builtAt || new Date().toISOString()
    });
  }

  return { runtimeConfig, backendDir: liveBackendDir, getState: () => state, saveState };
}

async function checkAndApplyGitHubUpdates({ python, backendDir, getState, saveState, isBackground = false }) {
  if (smokeTest) return { updated: false, restarting: false };
  const state = getState();
  const repo = state.repo || 'khusan-1-lox/pdf-toolkit';
  const branch = state.branch || 'main';

  // 1. Check GitHub Releases for a newer .exe installer
  try {
    const releases = await fetchJson(`https://api.github.com/repos/${repo}/releases?per_page=5`);
    if (Array.isArray(releases) && releases.length > 0) {
      const latest = releases[0];
      const publishedAt = Date.parse(latest.published_at || 0);
      const baseline = Date.parse(state.lastReleasePublishedAt || state.builtAt || 0);
      const exeAsset = (latest.assets || []).find(a => /setup.*\.exe$/i.test(a.name)) || (latest.assets || []).find(a => /\.exe$/i.test(a.name));
      if (exeAsset && publishedAt > baseline && latest.id !== state.installedReleaseId) {
        log(`Found new GitHub Release ${latest.tag_name} (${exeAsset.name})`);
        if (!isBackground) {
          startupScreen(`Найдена новая версия ${latest.tag_name} на GitHub! Скачиваем обновление…`);
        }
        const installerPath = path.join(app.getPath('temp'), `PDF-Toolkit-Update-${latest.id}.exe`);
        await downloadFile(exeAsset.browser_download_url, installerPath);
        saveState({
          installedReleaseId: latest.id,
          lastReleasePublishedAt: latest.published_at
        });

        let shouldInstall = true;
        if (isBackground && window) {
          const choice = await dialog.showMessageBox(window, {
            type: 'info',
            buttons: ['Обновить и перезапустить', 'Позже'],
            defaultId: 0,
            title: 'Обновление PDF Toolkit',
            message: `Скачана новая версия PDF Toolkit (${latest.tag_name}) с GitHub.`,
            detail: 'Установить обновление и перезапустить программу сейчас?'
          });
          shouldInstall = choice.response === 0;
        }

        if (shouldInstall) {
          stopChildren();
          const exeToRelaunch = process.execPath;
          const psCmd = `Start-Sleep -Seconds 2; Start-Process -FilePath '${installerPath.replace(/'/g, "''")}' -ArgumentList '/S' -Wait; Start-Process -FilePath '${exeToRelaunch.replace(/'/g, "''")}'`;
          spawn('powershell.exe', ['-NoProfile', '-WindowStyle', 'Hidden', '-Command', psCmd], {
            detached: true,
            windowsHide: true,
            stdio: 'ignore'
          }).unref();
          app.quit();
          return { updated: true, restarting: true };
        }
      }
    }
  } catch (err) {
    log(`GitHub Releases check skipped: ${err.message}`);
  }

  // 2. Check GitHub branch (main) for new commits and hot-update backend automatically
  try {
    const commitData = await fetchJson(`https://api.github.com/repos/${repo}/commits/${branch}`);
    const remoteSha = commitData?.sha;
    if (remoteSha && state.commitSha && remoteSha !== state.commitSha) {
      log(`New commit on GitHub ${repo}@${branch}: ${remoteSha} (local: ${state.commitSha})`);
      if (!isBackground) {
        startupScreen(`Найдено обновление на GitHub (${remoteSha.slice(0, 7)})! Загружаем свежую версию…`);
      }
      const zipPath = path.join(app.getPath('userData'), 'github-main-update.zip');
      await downloadFile(`https://codeload.github.com/${repo}/zip/refs/heads/${branch}`, zipPath);
      const extractScript = [
        'import zipfile, os, shutil, sys',
        'zip_path, target_backend = sys.argv[1], sys.argv[2]',
        'tmp_dir = target_backend + "_tmp"',
        'shutil.rmtree(tmp_dir, ignore_errors=True)',
        'os.makedirs(tmp_dir, exist_ok=True)',
        'with zipfile.ZipFile(zip_path, "r") as zf:',
        '    for member in zf.namelist():',
        '        parts = member.split("/", 1)',
        '        if len(parts) == 2 and parts[1].startswith("backend/") and not parts[1].endswith("/"):',
        '            rel = parts[1][len("backend/"):]',
        '            if rel.startswith("app/") or rel == "requirements.txt":',
        '                dest = os.path.join(tmp_dir, rel)',
        '                os.makedirs(os.path.dirname(dest), exist_ok=True)',
        '                with zf.open(member) as src, open(dest, "wb") as dst:',
        '                    shutil.copyfileobj(src, dst)',
        'if os.path.exists(os.path.join(tmp_dir, "app", "main.py")):',
        '    shutil.rmtree(os.path.join(target_backend, "app"), ignore_errors=True)',
        '    shutil.move(os.path.join(tmp_dir, "app"), os.path.join(target_backend, "app"))',
        '    if os.path.exists(os.path.join(tmp_dir, "requirements.txt")):',
        '        shutil.copy2(os.path.join(tmp_dir, "requirements.txt"), os.path.join(target_backend, "requirements.txt"))',
        'shutil.rmtree(tmp_dir, ignore_errors=True)'
      ].join('\n');
      await run(python, ['-c', extractScript, zipPath, backendDir]);
      try { fs.unlinkSync(zipPath); } catch {}
      patchBackendCompatibility(backendDir);
      saveState({ commitSha: remoteSha, updatedAt: new Date().toISOString() });
      log(`Hot-updated backend from GitHub commit ${remoteSha}`);
      return { updated: true, restarting: false, newSha: remoteSha };
    } else if (remoteSha && !state.commitSha) {
      saveState({ commitSha: remoteSha });
    }
  } catch (err) {
    log(`GitHub branch check skipped: ${err.message}`);
  }

  return { updated: false, restarting: false };
}

async function findPython(backendDir, runtimeConfig) {
  const localPaths = [
    path.join(resources(), 'python', 'python.exe'),
    process.env.PDF_TOOLKIT_PYTHON,
    path.join(__dirname, '..', '.venv-test', 'Scripts', 'python.exe'),
    path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe'),
    runtimeConfig.python ? (path.isAbsolute(runtimeConfig.python) ? runtimeConfig.python : path.join(resources(), runtimeConfig.python)) : null,
    path.join(app.getPath('userData'), 'python-env', 'Scripts', 'python.exe'),
    path.join(app.getPath('userData'), 'python-portable', 'tools', 'python.exe')
  ].filter(Boolean);
  for (const python of new Set(localPaths)) {
    if (!fs.existsSync(python)) continue;
    try { await run(python, ['-c', 'import app.main'], { cwd: backendDir }); log(`Using Python: ${python}`); return python; }
    catch (error) { log(`Python candidate not ready: ${error.message}`); }
  }
  startupScreen('Подготавливаем Python для PDF-инструментов. При первом запуске требуется интернет; это может занять пару минут…');
  const candidates = [['py', ['-3.12']], ['py', ['-3.11']], ['py', ['-3.10']], ['python', []], ['py', ['-3']]];
  let interpreter;
  for (const [command, prefix] of candidates) {
    try {
      const output = await run(command, [...prefix, '-c', 'import sys; print(sys.executable)']);
      if (fs.existsSync(output)) { interpreter = output; break; }
    } catch {}
  }

  let python;
  if (interpreter) {
    const environment = path.join(app.getPath('userData'), 'python-env');
    await run(interpreter, ['-m', 'venv', environment]);
    python = path.join(environment, 'Scripts', 'python.exe');
  } else {
    startupScreen('Устанавливаем встроенный Python 3.12 (на вашем ПК не найден Python). Пожалуйста, подождите 1–2 минуты…');
    const portableDir = path.join(app.getPath('userData'), 'python-portable');
    const nupkgZip = path.join(app.getPath('userData'), 'python-3.12.9.zip');
    fs.rmSync(portableDir, { recursive: true, force: true });
    fs.mkdirSync(portableDir, { recursive: true });
    await downloadFile('https://www.nuget.org/api/v2/package/python/3.12.9', nupkgZip);
    await run('powershell.exe', [
      '-NoProfile', '-Command',
      `Expand-Archive -Path '${nupkgZip.replace(/'/g, "''")}' -DestinationPath '${portableDir.replace(/'/g, "''")}' -Force`
    ]);
    try { fs.unlinkSync(nupkgZip); } catch {}
    python = path.join(portableDir, 'tools', 'python.exe');
    await run(python, ['-m', 'ensurepip', '--upgrade']);
  }

  startupScreen('Устанавливаем компоненты обработки PDF (только при первом запуске)…');
  await run(python, ['-m', 'pip', 'install', '-r', path.join(backendDir, 'requirements.txt'), '--disable-pip-version-check', '--no-warn-script-location']);
  await run(python, ['-c', 'import app.main'], { cwd: backendDir });
  return python;
}

function stopChildren() {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (!child.pid) continue;
    if (process.platform === 'win32') spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
    else child.kill();
  }
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.focus(); } });
  app.whenReady().then(async () => {
    fs.mkdirSync(app.getPath('userData'), { recursive: true });
    logPath = path.join(app.getPath('userData'), 'desktop.log');
    fs.writeFileSync(logPath, 'PDF Toolkit startup\n');
    try {
      session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
      if (!smokeTest) {
        window = new BrowserWindow({
          width: 1360,
          height: 900,
          minWidth: 860,
          minHeight: 620,
          title: 'PDF Toolkit',
          backgroundColor: '#f6f7fb',
          autoHideMenuBar: true,
          icon: path.join(__dirname, 'icon.ico'),
          webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true }
        });
        startupScreen('Запускаем PDF-инструменты и проверяем обновления на GitHub…');
      }
      const { runtimeConfig, backendDir, getState, saveState } = prepareLiveBackend();
      const frontendDir = path.join(resources(), 'frontend');
      if (!fs.existsSync(path.join(frontendDir, 'server.js'))) throw new Error('Сборка интерфейса отсутствует. Выполните npm run build в папке desktop-electron.');
      const python = await findPython(backendDir, runtimeConfig);

      // Check GitHub for new Release .exe or new commit on main before starting backend
      const updateResult = await checkAndApplyGitHubUpdates({ python, backendDir, getState, saveState, isBackground: false });
      if (updateResult.restarting) return;

      const backendPort = await freePort();
      const backendUrl = `http://127.0.0.1:${backendPort}`;
      let backend = launch(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)], {
        cwd: backendDir,
        env: { ...process.env, PYTHONUNBUFFERED: '1', PDF_TOOLKIT_TMP_DIR: path.join(app.getPath('userData'), 'documents') }
      });
      await waitReady(`${backendUrl}/health`, backend);

      const frontendPort = await freePort();
      const frontendUrl = `http://localhost:${frontendPort}`;
      const frontend = launch(process.execPath, [path.join(frontendDir, 'server.js')], {
        cwd: frontendDir,
        env: {
          ...process.env,
          ELECTRON_RUN_AS_NODE: '1',
          NODE_ENV: 'production',
          HOSTNAME: 'localhost',
          PORT: String(frontendPort),
          PDF_TOOLKIT_API_URL: backendUrl,
          NEXT_TELEMETRY_DISABLED: '1'
        }
      });
      await waitReady(`${frontendUrl}/ru`, frontend);
      if (await request(`${frontendUrl}/api/health`) !== 200) throw new Error('Не удалось связать интерфейс и PDF-сервер.');
      log(`READY frontend=${frontendUrl} backend=${backendUrl}`);

      if (smokeResult) fs.writeFileSync(smokeResult, JSON.stringify({ ready: true, frontendUrl, backendUrl, python, logPath }, null, 2));
      if (smokeTest) { app.quit(); return; }

      window.webContents.setWindowOpenHandler(({ url }) => { if (/^https?:\/\//.test(url)) shell.openExternal(url); return { action: 'deny' }; });
      window.webContents.on('will-navigate', (event, url) => { if (!url.startsWith(`${frontendUrl}/`)) event.preventDefault(); });
      await window.loadURL(`${frontendUrl}/ru`);

      // Background check every 10 minutes while the app is open
      setInterval(async () => {
        if (shuttingDown) return;
        const bgUpdate = await checkAndApplyGitHubUpdates({ python, backendDir, getState, saveState, isBackground: true });
        if (bgUpdate.updated && !bgUpdate.restarting && bgUpdate.newSha) {
          log('Restarting local backend after hot-update from GitHub...');
          if (backend.pid) {
            spawn('taskkill', ['/pid', String(backend.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
          }
          await new Promise(r => setTimeout(r, 800));
          backend = launch(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(backendPort)], {
            cwd: backendDir,
            env: { ...process.env, PYTHONUNBUFFERED: '1', PDF_TOOLKIT_TMP_DIR: path.join(app.getPath('userData'), 'documents') }
          });
          await waitReady(`${backendUrl}/health`, backend).catch(() => {});
          if (window && !window.isDestroyed()) window.webContents.reload();
        }
      }, 10 * 60 * 1000).unref();
    } catch (error) {
      log(error.stack || error.message);
      if (smokeResult) fs.writeFileSync(smokeResult, JSON.stringify({ ready: false, error: error.message, logPath }, null, 2));
      if (!smokeTest) dialog.showErrorBox('PDF Toolkit: ошибка запуска', `${error.message}\n\nЖурнал: ${logPath}`);
      app.quit();
    }
  });
  app.on('window-all-closed', () => app.quit());
  app.on('before-quit', stopChildren);
}
