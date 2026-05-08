const DEFAULT = 'http://127.0.0.1:7878';

async function load() {
  const { serverUrl } = await chrome.storage.sync.get({ serverUrl: DEFAULT });
  document.getElementById('serverUrl').value = serverUrl;
}

document.getElementById('saveBtn').addEventListener('click', async () => {
  const url = document.getElementById('serverUrl').value.trim() || DEFAULT;
  await chrome.storage.sync.set({ serverUrl: url });
  const s = document.getElementById('status');
  s.style.display = 'inline';
  setTimeout(() => { s.style.display = 'none'; }, 2000);
});

document.getElementById('resetBtn').addEventListener('click', async () => {
  await chrome.storage.sync.set({ serverUrl: DEFAULT });
  document.getElementById('serverUrl').value = DEFAULT;
});

load();
