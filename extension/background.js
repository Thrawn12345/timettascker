const DEFAULT_SERVER = 'http://127.0.0.1:7878';
const FLUSH_INTERVAL_MINUTES = 1;
const IDLE_THRESHOLD_SECONDS = 60;

async function getServer() {
  const { serverUrl } = await chrome.storage.sync.get({ serverUrl: DEFAULT_SERVER });
  return serverUrl.replace(/\/$/, '');
}

let activeTab = null;      // { url, title }
let activeStart = null;    // unix seconds
let queue = [];            // buffered entries waiting to send
let windowFocused = true;

// ── helpers ────────────────────────────────────────────────────────────────

function hostname(url) {
  try {
    const h = new URL(url).hostname;
    return h.replace(/^www\./, '');
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
         !url.startsWith('devtools://');
}

// ── session management ─────────────────────────────────────────────────────

function closeSession() {
  if (!activeTab || !activeStart) return;
  const endTime = Date.now() / 1000;
  const duration = endTime - activeStart;
  if (duration >= 2) {
    queue.push({
      name: hostname(activeTab.url) || activeTab.title || 'Unknown',
      url:  activeTab.url,
      start_time: activeStart,
      end_time:   endTime,
    });
  }
  activeTab = null;
  activeStart = null;
}

function openSession(tab) {
  closeSession();
  if (tab && isTrackable(tab.url)) {
    activeTab   = { url: tab.url, title: tab.title || '' };
    activeStart = Date.now() / 1000;
  }
}

// Snapshot without closing (used during periodic flush so we keep tracking)
function snapshotSession() {
  if (!activeTab || !activeStart) return;
  const now = Date.now() / 1000;
  const duration = now - activeStart;
  if (duration >= 2) {
    queue.push({
      name: hostname(activeTab.url) || activeTab.title || 'Unknown',
      url:  activeTab.url,
      start_time: activeStart,
      end_time:   now,
    });
    activeStart = now; // reset start so next snapshot doesn't double-count
  }
}

// ── network flush ──────────────────────────────────────────────────────────

async function flush() {
  if (queue.length === 0) return;
  const server = await getServer();
  const batch = queue.splice(0, queue.length);
  const failed = [];
  for (const entry of batch) {
    try {
      const res = await fetch(`${server}/api/tab`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(entry),
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
  try {
    const tab = await chrome.tabs.get(tabId);
    openSession(tab);
  } catch { /* tab may have closed */ }
});

chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
  if (info.status === 'complete' && tab.active) {
    openSession(tab);
  }
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
  } else if (state === 'active' && windowFocused) {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab) openSession(tab);
    } catch { /* */ }
  }
});

// ── periodic alarm ─────────────────────────────────────────────────────────

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'flush') {
    snapshotSession();
    flush();
  }
});

// ── startup ────────────────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(async () => {
  chrome.alarms.create('flush', { periodInMinutes: FLUSH_INTERVAL_MINUTES });
  // Track whatever is active right now
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) openSession(tab);
  } catch { /* */ }
});

chrome.runtime.onStartup.addListener(async () => {
  chrome.alarms.create('flush', { periodInMinutes: FLUSH_INTERVAL_MINUTES });
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) openSession(tab);
  } catch { /* */ }
});
