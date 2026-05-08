const DEFAULT_SERVER = 'http://127.0.0.1:7878';

async function load() {
  const data = await chrome.storage.sync.get({ serverUrl: DEFAULT_SERVER, deviceName: '' });
  document.getElementById('serverUrl').value  = data.serverUrl;
  document.getElementById('deviceName').value = data.deviceName;
}

async function save() {
  const url    = document.getElementById('serverUrl').value.trim()  || DEFAULT_SERVER;
  const device = document.getElementById('deviceName').value.trim() || 'Browser';
  await chrome.storage.sync.set({ serverUrl: url, deviceName: device });
  const s = document.getElementById('status');
  s.style.display = 'inline';
  setTimeout(() => { s.style.display = 'none'; }, 2000);
}

document.getElementById('saveBtn').addEventListener('click', save);

document.getElementById('resetBtn').addEventListener('click', async () => {
  await chrome.storage.sync.set({ serverUrl: DEFAULT_SERVER, deviceName: '' });
  document.getElementById('serverUrl').value  = DEFAULT_SERVER;
  document.getElementById('deviceName').value = '';
});

load();
