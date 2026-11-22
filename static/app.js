(() => {
  const listEl = document.getElementById('channels');
  const groupsEl = document.getElementById('groups');
  const searchEl = document.getElementById('search');
  const player = document.getElementById('player');
  const nowPlaying = document.getElementById('now-playing');

  let hls = null;
  let channels = [];
  let activeGroup = 'all';
  let activeUrl = null;

  async function load() {
    const res = await fetch('/api/channels');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    channels = await res.json();
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
      li.textContent = 'لا توجد قنوات تطابق البحث.';
      listEl.appendChild(li);
    }
  }

  function play(channel) {
    nowPlaying.textContent = channel.name || '';
    activeUrl = channel.url;
    document.querySelectorAll('.channel').forEach(el => el.classList.remove('playing'));
    const clicked = [...document.querySelectorAll('.channel span')]
      .find(s => s.textContent === (channel.name || '(بدون اسم)'));
    if (clicked && clicked.parentElement) clicked.parentElement.classList.add('playing');

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
    player.play().catch(() => { /* autoplay may be blocked; user can press play */ });
  }

  searchEl.addEventListener('input', render);
  load().catch(err => {
    nowPlaying.textContent = 'تعذّر تحميل القنوات: ' + err.message;
  });
})();
