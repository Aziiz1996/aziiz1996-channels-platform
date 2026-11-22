(() => {
  const listEl = document.getElementById('channels');
  const groupsEl = document.getElementById('groups');
  const searchEl = document.getElementById('search');
  const player = document.getElementById('player');
  const nowPlaying = document.getElementById('now-playing');
  const fileInput = document.getElementById('file-input');
  const toggleUrl = document.getElementById('toggle-url');
  const urlForm = document.getElementById('url-form');
  const urlInput = document.getElementById('url-input');
  const uploadStatus = document.getElementById('upload-status');

  const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

  let hls = null;
  let channels = [];
  let activeGroup = 'all';
  let activeUrl = null;

  async function fetchChannels() {
    const res = await fetch('/api/channels');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    channels = await res.json();
    activeGroup = 'all';
    renderGroups();
    render();
  }

  function renderGroups() {
    const groups = Array.from(new Set(channels.map(c => c.group).filter(Boolean))).sort();
    groupsEl.innerHTML = '';
    const buttons = [['all', 'الكل'], ...groups.map(g => [g, g])];
    for (const [key, label] of buttons) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = label;
      b.dataset.group = key;
      if (key === activeGroup) b.classList.add('active');
      b.addEventListener('click', () => {
        activeGroup = key;
        groupsEl.querySelectorAll('button').forEach(x =>
          x.classList.toggle('active', x.dataset.group === key));
        render();
      });
      groupsEl.appendChild(b);
    }
  }

  function render() {
    const q = searchEl.value.trim().toLowerCase();
    listEl.innerHTML = '';
    const items = channels.filter(c =>
      (activeGroup === 'all' || c.group === activeGroup) &&
      (!q || (c.name || '').toLowerCase().includes(q))
    );
    for (const c of items) {
      const li = document.createElement('li');
      li.className = 'channel';
      if (c.url === activeUrl) li.classList.add('playing');
      const img = document.createElement('img');
      img.src = c.logo || '';
      img.alt = '';
      img.loading = 'lazy';
      img.addEventListener('error', () => { img.style.visibility = 'hidden'; });
      const span = document.createElement('span');
      span.textContent = c.name || '(بدون اسم)';
      li.append(img, span);
      li.addEventListener('click', () => play(c));
      listEl.appendChild(li);
    }
    if (!items.length) {
      const li = document.createElement('li');
      li.className = 'empty';
      li.textContent = channels.length
        ? 'لا توجد قنوات تطابق البحث.'
        : 'لم يتم تحميل أي قناة بعد. ارفع ملف M3U أو أدخل رابطاً.';
      listEl.appendChild(li);
    }
  }

  function play(channel) {
    nowPlaying.textContent = channel.name || '';
    activeUrl = channel.url;
    document.querySelectorAll('.channel').forEach(el => el.classList.remove('playing'));
    const current = [...document.querySelectorAll('.channel span')]
      .find(s => s.textContent === (channel.name || '(بدون اسم)'));
    if (current && current.parentElement) current.parentElement.classList.add('playing');

    if (hls) { hls.destroy(); hls = null; }
    const url = channel.url;
    if (window.Hls && window.Hls.isSupported()) {
      hls = new window.Hls({ enableWorker: true });
      hls.on(window.Hls.Events.ERROR, (_, data) => {
        if (data && data.fatal) {
          nowPlaying.textContent = 'تعذّر تشغيل القناة: ' + (data.details || data.type);
        }
      });
      hls.loadSource(url);
      hls.attachMedia(player);
    } else if (player.canPlayType('application/vnd.apple.mpegurl')) {
      player.src = url;
    } else {
      nowPlaying.textContent = 'المتصفح لا يدعم تشغيل HLS.';
      return;
    }
    player.play().catch(() => { /* autoplay may be blocked */ });
  }

  async function uploadChannels(body, label) {
    setStatus('جارٍ ' + label + '…', 'info');
    let res;
    try {
      res = await fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (err) {
      setStatus('فشل الاتصال بالخادم: ' + err.message, 'error');
      return;
    }
    let data = {};
    try { data = await res.json(); } catch { /* ignore */ }
    if (!res.ok) {
      setStatus('فشل: ' + (data.error || ('HTTP ' + res.status)), 'error');
      return;
    }
    setStatus('تم تحميل ' + data.count + ' قناة.', 'ok');
    try { await fetchChannels(); } catch (err) {
      setStatus('حُمّلت القائمة لكن تعذّر عرضها: ' + err.message, 'error');
    }
  }

  function setStatus(msg, kind) {
    uploadStatus.textContent = msg;
    uploadStatus.className = 'status ' + (kind || '');
  }

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setStatus('الملف كبير جداً (الحد الأقصى 10 ميغابايت).', 'error');
      fileInput.value = '';
      return;
    }
    let text;
    try {
      text = await file.text();
    } catch (err) {
      setStatus('تعذّر قراءة الملف: ' + err.message, 'error');
      fileInput.value = '';
      return;
    }
    await uploadChannels({ text }, 'قراءة الملف');
    fileInput.value = '';
  });

  toggleUrl.addEventListener('click', () => {
    urlForm.hidden = !urlForm.hidden;
    if (!urlForm.hidden) urlInput.focus();
  });

  urlForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;
    await uploadChannels({ url }, 'جلب الرابط');
  });

  searchEl.addEventListener('input', render);
  fetchChannels().catch(err => {
    setStatus('تعذّر تحميل القنوات: ' + err.message, 'error');
  });
})();
