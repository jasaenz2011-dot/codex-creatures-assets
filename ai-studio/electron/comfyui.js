/**
 * ComfyUI process manager.
 * Detects, launches, and monitors a local ComfyUI instance.
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const COMFY_PORT = 8188;
const COMFY_URL  = `http://127.0.0.1:${COMFY_PORT}`;

// Common install locations to probe on Windows
const WINDOWS_SEARCH_PATHS = [
  'C:\\ComfyUI',
  'C:\\ComfyUI_windows_portable',
  path.join(process.env.USERPROFILE || '', 'ComfyUI'),
  path.join(process.env.USERPROFILE || '', 'Desktop', 'ComfyUI_windows_portable'),
  path.join(process.env.USERPROFILE || '', 'Documents', 'ComfyUI'),
];

let comfyProcess = null;

function findComfyUI() {
  for (const candidate of WINDOWS_SEARCH_PATHS) {
    const launcher = path.join(candidate, 'run_nvidia_gpu.bat');
    const launcher2 = path.join(candidate, 'ComfyUI', 'main.py');
    if (fs.existsSync(launcher) || fs.existsSync(launcher2)) {
      return candidate;
    }
  }
  return null;
}

async function isRunning() {
  try {
    const res = await fetch(`${COMFY_URL}/system_stats`, { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}

async function waitUntilReady(timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await isRunning()) return true;
    await new Promise(r => setTimeout(r, 1000));
  }
  return false;
}

async function launch(installPath) {
  if (await isRunning()) return { status: 'already_running', url: COMFY_URL };

  const launcher = path.join(installPath, 'run_nvidia_gpu.bat');
  const launcherCpu = path.join(installPath, 'run_cpu.bat');

  const bat = fs.existsSync(launcher) ? launcher : launcherCpu;
  if (!fs.existsSync(bat)) {
    return { status: 'not_found', url: null };
  }

  comfyProcess = spawn('cmd.exe', ['/c', bat], {
    cwd: installPath,
    detached: false,
    stdio: 'ignore',
  });

  const ready = await waitUntilReady(60000);
  return ready
    ? { status: 'launched', url: COMFY_URL }
    : { status: 'timeout', url: null };
}

function stop() {
  if (comfyProcess) {
    comfyProcess.kill();
    comfyProcess = null;
  }
}

module.exports = { findComfyUI, isRunning, launch, stop, COMFY_URL };
