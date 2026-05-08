const DEFAULT_SERVER = 'http://127.0.0.1:7878';
const FLUSH_INTERVAL_MINUTES = 1;
const IDLE_THRESHOLD_SECONDS = 60;

async function getServer() {
  const { serverUrl } = await chrome.storage.sync.get({ serverUrl: DEFAULT_SERVER });
  return serverUrl.replace(/\/$/, '');
}

async function getDevice() {
  const { deviceName } = await chrome.storage.sync.get({ deviceName: '' });
  return deviceName || 'Browser';
}

// ── URL normalisation ──────────────────────────────────────────────────────
// Always store the bare hostname (e.g. "youtube.com"), never a path or title.
function siteName(url) {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

function isTrackable(url) {
  if (!url) return false;
  return !url.startsWith('chrome://') &&
         !url.startsWith('chrome-extension://') &&
         !url.startsWith('about:') &&
         !url.startsWith('edge://') &&
         !url.startsWith('devtools://') &&
         !url.startsWith('moz-extension://');
}

// ── state ──────────────────────────────────────────────────────────────────
let activeTab   = null;   // { url }
let activeStart = null;
let windowFocused = true;
let queue = [];

// audibleSessions: tabId → { url, startTime }
// tracks background tabs that are playing audio
const audibleSessions = new Map();

// ── active-tab session management ──────────────────────────────────────────

function closeSession() {
  if (!activeTab || !activeStart) return;
  const endTime = Date.now() / 1000;
  const name = siteName(activeTab.url);
  if (name && endTime - activeStart >= 2) {
    queue.push({ name, url: activeTab.url, start_time: activeStart, end_time: endTime });
  }
  activeTab   = null;
  activeStart = null;
}

function openSession(tab) {
  closeSession();
  if (tab && isTrackable(tab.url) && siteName(tab.url)) {
    // If this tab had an audible session running, close it — active tracking takes over
    for (const [tid, s] of audibleSessions) {
      if (s.url === tab.url) {
        audibleSessions.delete(tid);
        break;
      }
    }
    activeTab   = { url: tab.url };
    activeStart = Date.now() / 1000;
  }
}

// ── audible-tab session management ─────────────────────────────────────────
// Tracks tabs playing audio that are NOT the focused tab.

function startAudibleSession(tabId, url) {
  if (audibleSessions.has(tabId)) return;          // already tracking
  if (!isTrackable(url) || !siteName(url)) return;
  if (activeTab && activeTab.url === url) return;  // active tracker covers this
  audibleSessions.set(tabId, { url, startTime: Date.now() / 1000 });
}

function endAudibleSession(tabId) {
  const s = audibleSessions.get(tabId);
  if (!s) return;
  audibleSessions.delete(tabId);
  const endTime = Date.now() / 1000;
  const name = siteName(s.url);
  if (name && endTime - s.startTime >= 5) {
    queue.push({ name, url: s.url, start_time: s.startTime, end_time: endTime });
  }
}

// ── network flush ──────────────────────────────────────────────────────────

async function flush() {
  if (queue.length === 0) return;
  const [server, device] = await Promise.all([getServer(), getDevice()]);
  const batch  = queue.splice(0);
  const failed = [];
  for (const entry of batch) {
    try {
      const res = await fetch(`${server}/api/tab`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ ...entry, device }),
      });
      if (!res.ok) failed.push(entry);
    } catch {
      failed.push(entry);
    }
  }
  queue.unshift(...failed);
}

// ── event listeners ────────────────────────────────────────────────────────

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try { openSession(await chrome.tabs.get(tabId)); } catch { /* tab closed */ }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // URL change on active tab
  if (changeInfo.status === 'complete' && tab.active) {
    openSession(tab);
  }

  // Audio started/stopped
  if ('audible' in changeInfo) {
    if (tab.audible) {
      startAudibleSession(tabId, tab.url);
    } else {
      endAudibleSession(tabId);
    }
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  endAudibleSession(tabId);
});

chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    windowFocused = false;
    closeSession();
  } else {
    windowFocused = true;
    try {
      const [tab] = await chrome.tabs.query({ active: true, windowId });
      if (tab) openSession(tab);
    } catch { /* */ }
  }
});

chrome.idle.setDetectionInterval(IDLE_THRESHOLD_SECONDS);
chrome.idle.onStateChanged.addListener(async (state) => {
  if (state === 'idle' || state === 'locked') {
    closeSession();
    // pause all audible sessions
    const now = Date.now() / 1000;
    for (const [tabId, s] of audibleSessions) {
      const name = siteName(s.url);
      if (name && now - s.startTime >= 5) {
        queue.push({ name, url: s.url, start_time: s.startTime, end_time: now });
      }
      audibleSessions.delete(tabId);
    }
  } else if (state === 'active' && windowFocused) {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab) openSession(tab);
      // re-detect audible tabs
      const all = await chrome.tabs.query({ audible: true });
      for (const t of all) startAudibleSession(t.id, t.url);
    } catch { /* */ }
  }
});

// ── periodic flush ─────────────────────────────────────────────────────────

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name !== 'flush') return;

  // Snapshot active tab (keep session running)
  if (activeTab && activeStart) {
    const now  = Date.now() / 1000;
    const name = siteName(activeTab.url);
    if (name && now - activeStart >= 2) {
      queue.push({ name, url: activeTab.url, start_time: activeStart, end_time: now });
      activeStart = now;
    }
  }

  // Snapshot audible sessions (keep them running)
  const now = Date.now() / 1000;
  for (const [tabId, s] of audibleSessions) {
    const name = siteName(s.url);
    if (name && now - s.startTime >= 5) {
      queue.push({ name, url: s.url, start_time: s.startTime, end_time: now });
      s.startTime = now;
    }
  }

  flush();
});

// ── startup ────────────────────────────────────────────────────────────────

async function init() {
  chrome.alarms.create('flush', { periodInMinutes: FLUSH_INTERVAL_MINUTES });
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) openSession(tab);
    const audible = await chrome.tabs.query({ audible: true });
    for (const t of audible) startAudibleSession(t.id, t.url);
  } catch { /* */ }
}

chrome.runtime.onInstalled.addListener(init);
chrome.runtime.onStartup.addListener(init);
