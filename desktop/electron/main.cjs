const { app, BrowserWindow, Menu, shell } = require('electron')
const { spawn, spawnSync } = require('child_process')
const fs = require('fs')
const http = require('http')
const net = require('net')
const path = require('path')
const { pathToFileURL } = require('url')

app.setName('Face Recognition Service')
app.setAppUserModelId('local.face-recognition-service')

const isPackaged = app.isPackaged
const ROOT_DIR = isPackaged ? process.resourcesPath : path.resolve(__dirname, '..', '..')
const BACKEND_DIR = isPackaged ? path.join(process.resourcesPath, 'backend') : path.join(ROOT_DIR, 'backend')
const FRONTEND_DIST = isPackaged
  ? path.join(process.resourcesPath, 'frontend', 'index.html')
  : path.join(ROOT_DIR, 'frontend', 'dist', 'index.html')
const ICON_PATH = resolveIconPath()
const LOG_DIR = isPackaged ? path.join(app.getPath('userData'), 'logs') : path.join(ROOT_DIR, 'logs')
const isDev = process.argv.includes('--dev') || process.env.ELECTRON_DEV === '1'
const isSmokeTest = process.argv.includes('--smoke-test')
const DEFAULT_RUNTIME_DIR = process.platform === 'win32'
  ? 'D:\\FaceService'
  : path.join(app.getPath('appData'), 'FaceRecognitionService')

let backendProcess = null
let mainWindow = null
let backendLogPath = null
let isQuitting = false
let runtimeDir = DEFAULT_RUNTIME_DIR

function resolveIconPath() {
  const candidates = [
    path.join(process.resourcesPath || '', 'assets', 'app-icon.ico'),
    path.join(__dirname, 'assets', 'app-icon.ico'),
  ]
  return candidates.find((candidate) => fs.existsSync(candidate)) || candidates[candidates.length - 1]
}

function ensureLogDir() {
  fs.mkdirSync(LOG_DIR, { recursive: true })
  backendLogPath = path.join(LOG_DIR, `desktop-backend-${new Date().toISOString().replace(/[:.]/g, '-')}.log`)
}

function createMainWindow(options = {}) {
  if (mainWindow && !mainWindow.isDestroyed()) return mainWindow
  mainWindow = new BrowserWindow({
    width: options.width || 1280,
    height: options.height || 860,
    minWidth: 980,
    minHeight: 680,
    backgroundColor: '#0b1120',
    icon: ICON_PATH,
    title: options.title || 'Face Recognition Service',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  })
  return mainWindow
}

function installMenu() {
  const template = [
    {
      label: 'App',
      submenu: [
        {
          label: 'Open Logs Folder',
          click: () => shell.openPath(LOG_DIR),
        },
        {
          label: 'Open Runtime Folder',
          click: () => shell.openPath(runtimeDir),
        },
        {
          label: 'Open Backend Log',
          enabled: Boolean(backendLogPath),
          click: () => backendLogPath && shell.openPath(backendLogPath),
        },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
      ],
    },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.unref()
    server.on('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : null
      server.close(() => {
        if (port) resolve(port)
        else reject(new Error('Could not allocate a free backend port'))
      })
    })
  })
}

function waitForHttp(url, timeoutMs = 90000) {
  const started = Date.now()
  return new Promise((resolve, reject) => {
    const check = () => {
      const request = http.get(url, (response) => {
        response.resume()
        if (response.statusCode && response.statusCode >= 200 && response.statusCode < 500) {
          resolve()
          return
        }
        retry()
      })
      request.on('error', retry)
      request.setTimeout(3000, () => {
        request.destroy()
        retry()
      })
    }

    const retry = () => {
      if (Date.now() - started > timeoutMs) {
        reject(new Error(`Timed out waiting for ${url}`))
        return
      }
      setTimeout(check, 750)
    }

    check()
  })
}

function startBackend(port) {
  const python = process.env.FACE_SERVICE_PYTHON || 'python'
  const runtimeEnv = loadRuntimeEnv()
  const baseDir = runtimeEnv.BASE_DIR || process.env.BASE_DIR || DEFAULT_RUNTIME_DIR
  runtimeDir = baseDir
  fs.mkdirSync(baseDir, { recursive: true })
  const env = {
    ...process.env,
    ...runtimeEnv,
    BASE_DIR: baseDir,
    HOST: '127.0.0.1',
    PORT: String(port),
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
  }
  const log = fs.createWriteStream(backendLogPath, { flags: 'a' })
  log.write(`[desktop] Starting backend on 127.0.0.1:${port}\n`)
  log.write(`[desktop] Command: ${python} main.py\n\n`)
  log.write(`[desktop] BASE_DIR=${env.BASE_DIR}\n`)
  log.write(`[desktop] .env source=${runtimeEnv.__source || 'none'}\n\n`)

  backendProcess = spawn(python, ['main.py'], {
    cwd: BACKEND_DIR,
    env,
    windowsHide: true,
  })

  backendProcess.stdout.pipe(log)
  backendProcess.stderr.pipe(log)
  backendProcess.on('exit', (code, signal) => {
    log.write(`\n[desktop] Backend exited code=${code} signal=${signal}\n`)
    if (!isQuitting && mainWindow && !mainWindow.isDestroyed()) {
      showFatalScreen(
        'Backend stopped unexpectedly',
        `The local backend process exited while the desktop app was running.\n\nExit code: ${code}\nSignal: ${signal || 'none'}\n\nBackend log:\n${backendLogPath}`,
      )
    }
  })
  backendProcess.on('error', (error) => {
    log.write(`\n[desktop] Backend spawn error: ${error.stack || error.message}\n`)
  })
}

function loadRuntimeEnv() {
  const candidates = [
    path.join(process.cwd(), '.env'),
    path.join(path.dirname(process.execPath), '.env'),
    path.join(ROOT_DIR, '.env'),
  ]

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return {
        ...parseEnvFile(candidate),
        __source: candidate,
      }
    }
  }
  return {}
}

function parseEnvFile(filePath) {
  const values = {}
  const content = fs.readFileSync(filePath, 'utf8')
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    const equals = line.indexOf('=')
    if (equals <= 0) continue
    const key = line.slice(0, equals).trim()
    let value = line.slice(equals + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    values[key] = value
  }
  return values
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) return
  backendProcess.kill()
  backendProcess = null
}

function checkPython() {
  const python = process.env.FACE_SERVICE_PYTHON || 'python'
  const result = spawnSync(python, ['--version'], {
    cwd: ROOT_DIR,
    encoding: 'utf8',
    windowsHide: true,
  })
  if (result.error) {
    throw new Error(`Could not start Python executable "${python}".\n\n${result.error.message}`)
  }
  if (result.status !== 0) {
    throw new Error(`Python version check failed for "${python}".\n\n${result.stderr || result.stdout}`)
  }
  return `${python}: ${(result.stdout || result.stderr || '').trim()}`
}

function htmlPage(title, body, options = {}) {
  const escapedTitle = escapeHtml(title)
  const escapedBody = escapeHtml(body)
  const escapedEyebrow = escapeHtml(options.eyebrow || 'Face Recognition Service')
  const statusItems = options.steps || []
  const stepsHtml = statusItems
    .map((step) => {
      const tone = step.done ? '#22c55e' : step.active ? '#93c5fd' : '#64748b'
      const bullet = step.done ? '✓' : step.active ? '•' : '○'
      return `<li style="color:${tone}"><span>${bullet}</span><strong>${escapeHtml(step.label)}</strong></li>`
    })
    .join('')
  return `data:text/html;charset=utf-8,${encodeURIComponent(`
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>${escapedTitle}</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #0b1120;
        color: #e5e7eb;
        font-family: Inter, Segoe UI, sans-serif;
      }
      main {
        width: min(720px, calc(100vw - 48px));
        border: 1px solid #334155;
        border-radius: 24px;
        background: rgba(15, 23, 42, 0.86);
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
        padding: 28px;
      }
      .eyebrow {
        color: #93c5fd;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.12em;
        margin-bottom: 10px;
        text-transform: uppercase;
      }
      h1 { margin: 0 0 12px; font-size: 28px; }
      p { color: #cbd5e1; line-height: 1.6; }
      ul {
        display: grid;
        gap: 10px;
        list-style: none;
        margin: 18px 0;
        padding: 0;
      }
      li {
        align-items: center;
        border: 1px solid #334155;
        border-radius: 14px;
        display: flex;
        gap: 10px;
        padding: 10px 12px;
      }
      pre {
        white-space: pre-wrap;
        overflow: auto;
        border: 1px solid #334155;
        border-radius: 16px;
        background: #020617;
        padding: 16px;
        color: #bfdbfe;
      }
    </style>
  </head>
  <body>
    <main>
      <div class="eyebrow">${escapedEyebrow}</div>
      <h1>${escapedTitle}</h1>
      <p>${escapeHtml(options.description || '')}</p>
      ${stepsHtml ? `<ul>${stepsHtml}</ul>` : ''}
      <pre>${escapedBody}</pre>
    </main>
  </body>
</html>`)}`
}

function htmlError(title, body) {
  return htmlPage(title, body, {
    description: 'Desktop shell could not start the local backend.',
  })
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

async function openFrontend(apiBaseUrl) {
  createMainWindow()

  const encodedApi = encodeURIComponent(apiBaseUrl)
  if (isDev) {
    const devUrl = `http://127.0.0.1:3000/?apiBaseUrl=${encodedApi}`
    await mainWindow.loadURL(devUrl)
    return
  }

  if (!fs.existsSync(FRONTEND_DIST)) {
    await mainWindow.loadURL(htmlError('Frontend build is missing', `Run first:\n\nnpm --prefix frontend run build\n\nExpected file:\n${FRONTEND_DIST}`))
    return
  }

  const fileUrl = `${pathToFileURL(FRONTEND_DIST).toString()}?apiBaseUrl=${encodedApi}`
  await mainWindow.loadURL(fileUrl)
}

async function verifyRendererLoaded() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    throw new Error('Renderer window was not created')
  }
  await new Promise((resolve) => setTimeout(resolve, 1500))
  const result = await mainWindow.webContents.executeJavaScript(`
    (() => {
      const root = document.getElementById('root');
      return {
        title: document.title,
        rootChildren: root ? root.children.length : -1,
        bodyTextLength: document.body ? document.body.innerText.length : 0,
        location: window.location.href
      };
    })()
  `)
  if (!result || result.rootChildren < 1 || result.bodyTextLength < 1) {
    throw new Error(`Renderer did not render React UI: ${JSON.stringify(result)}`)
  }
}

async function showStartupScreen(activeStep, detail = '') {
  const steps = [
    'Prepare logs',
    'Find backend port',
    'Check Python',
    'Start backend',
    'Wait for health',
    'Load app UI',
  ]
  const activeIndex = steps.indexOf(activeStep)
  createMainWindow({ title: 'Face Recognition Service - starting' })
  await mainWindow.loadURL(htmlPage('Starting local service', detail || activeStep, {
    description: 'The desktop app is preparing the local backend and UI.',
    steps: steps.map((label, index) => ({
      label,
      done: activeIndex > index,
      active: activeIndex === index,
    })),
  }))
}

async function showFatalScreen(title, detail) {
  createMainWindow({
    width: 960,
    height: 680,
    title: `Face Recognition Service - ${title}`,
  })
  await mainWindow.loadURL(htmlError(title, detail))
}

async function boot() {
  ensureLogDir()
  installMenu()
  try {
    await showStartupScreen('Prepare logs', `Backend log:\n${backendLogPath}`)
    await showStartupScreen('Find backend port')
    const port = await findFreePort()
    const apiBaseUrl = `http://127.0.0.1:${port}/api`

    await showStartupScreen('Check Python')
    const pythonVersion = checkPython()

    await showStartupScreen('Start backend', `${pythonVersion}\nBackend log:\n${backendLogPath}`)
    startBackend(port)

    await showStartupScreen('Wait for health', `Waiting for http://127.0.0.1:${port}/api/health`)
    await waitForHttp(`http://127.0.0.1:${port}/api/health`)

    await showStartupScreen('Load app UI', `API: ${apiBaseUrl}`)
    await openFrontend(apiBaseUrl)
    if (isSmokeTest) {
      await verifyRendererLoaded()
      setTimeout(() => app.quit(), 500)
    }
  } catch (error) {
    if (isSmokeTest) {
      console.error(error.stack || error.message)
      app.exit(1)
      return
    }
    await showFatalScreen('Backend startup failed', `${error.stack || error.message}\n\nBackend log:\n${backendLogPath}`)
  }
}

app.whenReady().then(boot)

app.on('window-all-closed', () => {
  isQuitting = true
  stopBackend()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  isQuitting = true
  stopBackend()
})
