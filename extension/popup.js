async function getServer() {
  const { serverUrl } = await chrome.storage.sync.get({ serverUrl: 'http://127.0.0.1:7878' });
  return serverUrl.replace(/\/$/, '');
}

function fmt(seconds) {
  if (seconds < 60)   return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}

function faviconUrl(name) {
  return `https://www.google.com/s2/favicons?sz=32&domain=${encodeURIComponent(name)}`;
}

async function load() {
  const server     = await getServer();
  const dot        = document.getElementById('dot');
  const statusText = document.getElementById('statusText');
  const totalDiv   = document.getElementById('totalToday');
  const entries    = document.getElementById('entries');

  try {
    const [statsRes, summaryRes] = await Promise.all([
      fetch(`${server}/api/stats?period=day`),
      fetch(`${server}/api/summary`),
    ]);

    const stats   = await statsRes.json();
    const summary = await summaryRes.json();

    dot.className          = 'dot ok';
    statusText.textContent = 'Connected — tracking active';
    statusText.className   = 'status-text ok';

    if (summary.today_seconds > 0) {
      totalDiv.style.display = '';
      totalDiv.innerHTML = `Total today: <strong>${fmt(summary.today_seconds)}</strong>`;
    }

    const tabs = stats.filter(s => s.type === 'tab').slice(0, 10);
    const maxSec = tabs[0]?.total_seconds || 1;

    if (tabs.length === 0) {
      entries.innerHTML = '<div class="empty">No browser activity recorded today.<br>Keep browsing and it will appear here.</div>';
      return;
    }

    entries.innerHTML = tabs.map(s => {
      const pct = Math.round((s.total_seconds / maxSec) * 100);
      return `
        <div class="entry">
          <img class="favicon" src="${faviconUrl(s.name)}" alt="" onerror="this.style.display='none'">
          <span class="entry-name" title="${s.name}">${s.name}</span>
          <div class="entry-bar-wrap"><div class="entry-bar" style="width:${pct}%"></div></div>
          <span class="entry-time">${fmt(s.total_seconds)}</span>
        </div>
      `;
    }).join('');

  } catch {
    dot.className          = 'dot error';
    statusText.textContent = 'Server offline — run main.py first';
    statusText.className   = 'status-text error';
    entries.innerHTML      = '<div class="empty">Start the Time Tracker backend<br>to begin recording.</div>';
  }
}

document.getElementById('openBtn').addEventListener('click', async () => {
  const server = await getServer();
  chrome.tabs.create({ url: `${server}/` });
});

document.getElementById('settingsBtn').addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});

load();
