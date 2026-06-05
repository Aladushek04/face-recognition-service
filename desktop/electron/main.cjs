const { app, BrowserWindow } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const http = require('http')
const net = require('net')
const path = require('path')
const { pathToFileURL } = require('url')

const ROOT_DIR = path.resolve(__dirname, '..', '..')
const BACKEND_DIR = path.join(ROOT_DIR, 'backend')
const FRONTEND_DIR = path.join(ROOT_DIR, 'frontend')
const FRONTEND_DIST = path.join(FRONTEND_DIR, 'dist', 'index.html')
const LOG_DIR = path.join(ROOT_DIR, 'logs')
const isDev = process.argv.includes('--dev') || process.env.ELECTRON_DEV === '1'
const isSmokeTest = process.argv.includes('--smoke-test')

let backendProcess = null
let mainWindow = null
let backendLogPath = null

function ensureLogDir() {
  fs.mkdirSync(LOG_DIR, { recursive: true })
  backendLogPath = path.join(LOG_DIR, `desktop-backend-${new Date().toISOString().replace(/[:.]/g, '-')}.log`)
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
  const env = {
    ...process.env,
    HOST: '127.0.0.1',
    PORT: String(port),
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
  }
  const log = fs.createWriteStream(backendLogPath, { flags: 'a' })
  log.write(`[desktop] Starting backend on 127.0.0.1:${port}\n`)
  log.write(`[desktop] Command: ${python} main.py\n\n`)

  backendProcess = spawn(python, ['main.py'], {
    cwd: BACKEND_DIR,
    env,
    windowsHide: true,
  })

  backendProcess.stdout.pipe(log)
  backendProcess.stderr.pipe(log)
  backendProcess.on('exit', (code, signal) => {
    log.write(`\n[desktop] Backend exited code=${code} signal=${signal}\n`)
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-exited', { code, signal })
    }
  })
  backendProcess.on('error', (error) => {
    log.write(`\n[desktop] Backend spawn error: ${error.stack || error.message}\n`)
  })
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) return
  backendProcess.kill()
  backendProcess = null
}

function htmlError(title, body) {
  const escapedTitle = escapeHtml(title)
  const escapedBody = escapeHtml(body)
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
      h1 { margin: 0 0 12px; font-size: 28px; }
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
      <h1>${escapedTitle}</h1>
      <p>Desktop shell could not start the local backend.</p>
      <pre>${escapedBody}</pre>
    </main>
  </body>
</html>`)}`
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

async function openFrontend(apiBaseUrl) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 980,
    minHeight: 680,
    backgroundColor: '#0b1120',
    title: 'Face Recognition Service',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

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

async function boot() {
  ensureLogDir()
  const port = await findFreePort()
  const apiBaseUrl = `http://127.0.0.1:${port}/api`

  startBackend(port)
  try {
    await waitForHttp(`http://127.0.0.1:${port}/api/health`)
    await openFrontend(apiBaseUrl)
    if (isSmokeTest) {
      setTimeout(() => app.quit(), 2500)
    }
  } catch (error) {
    mainWindow = new BrowserWindow({
      width: 960,
      height: 680,
      backgroundColor: '#0b1120',
      title: 'Face Recognition Service - startup failed',
    })
    await mainWindow.loadURL(htmlError('Backend startup failed', `${error.stack || error.message}\n\nBackend log:\n${backendLogPath}`))
  }
}

app.whenReady().then(boot)

app.on('window-all-closed', () => {
  stopBackend()
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  stopBackend()
})
