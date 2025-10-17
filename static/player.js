
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  const audio = $('#pl-audio');
  const el = {
    cover: $('#pl-cover'),
    title: $('#pl-title'),
    artist: $('#pl-artist'),
    btnPlay: $('#btn-play'),
    iconPlay: $('#btn-play .icon-play'),
    iconPause: $('#btn-play .icon-pause'),
    btnPrev: $('#btn-prev'),
    btnNext: $('#btn-next'),
    btnRepeat: $('#btn-repeat'),
    btnShuffle: $('#btn-shuffle'),
    btnLike: $('#btn-like'),
    seek: $('#pl-seek'),
    cur: $('#pl-current'),
    dur: $('#pl-duration'),
    volume: $('#pl-volume'),
    tracks: $('#tracks'),
    btnPlayAll: $('#btn-play-all'),
  };

  let queue = [];
  let index = -1;
  let repeat = false;
  let shuffle = false;
  let liked = new Set(JSON.parse(localStorage.getItem('liked') || '[]'));

  const fmt = (sec) => { if (!isFinite(sec)) return '0:00'; const m = Math.floor(sec / 60); const s = Math.floor(sec % 60).toString().padStart(2, '0'); return `${m}:${s}`; };
  const setActive = (i) => { $$('.track').forEach(t => t.classList.remove('is-active')); const row = $(`.track[data-idx="${i}"]`); if (row) row.classList.add('is-active'); };
  const updateLikeBtn = () => { const cur = queue[index]; if (!cur) return; el.btnLike.classList.toggle('is-on', liked.has(cur.id)); };

  el.btnPlay?.addEventListener('click', () => { if (!audio.src && queue[0]) playAt(0); else if (audio.paused) audio.play(); else audio.pause(); });
  el.btnNext?.addEventListener('click', () => next());
  el.btnPrev?.addEventListener('click', () => prev());
  el.btnRepeat?.addEventListener('click', () => { repeat = !repeat; el.btnRepeat.classList.toggle('is-on', repeat); });
  el.btnShuffle?.addEventListener('click', () => { shuffle = !shuffle; el.btnShuffle.classList.toggle('is-on', shuffle); });
  el.btnLike?.addEventListener('click', () => { const cur = queue[index]; if (!cur) return; if (liked.has(cur.id)) liked.delete(cur.id); else liked.add(cur.id); localStorage.setItem('liked', JSON.stringify([...liked])); updateLikeBtn(); });

  el.seek?.addEventListener('input', () => { if (audio.duration) audio.currentTime = (el.seek.value / 100) * audio.duration; });
  el.volume?.addEventListener('input', () => { audio.volume = parseFloat(el.volume.value); });

  document.addEventListener('keydown', (e) => { if (['INPUT','TEXTAREA'].includes(e.target.tagName)) return; if (e.code === 'Space' || e.key?.toLowerCase() === 'k') { e.preventDefault(); el.btnPlay?.click(); } if (e.key?.toLowerCase() === 'l') next(); if (e.key?.toLowerCase() === 'j') prev(); });

  audio.addEventListener('play', () => { el.iconPlay.style.display = 'none'; el.iconPause.style.display = 'block'; });
  audio.addEventListener('pause', () => { el.iconPlay.style.display = 'block'; el.iconPause.style.display = 'none'; });
  audio.addEventListener('timeupdate', () => { el.cur.textContent = fmt(audio.currentTime); el.dur.textContent = fmt(audio.duration || 0); if (audio.duration) { el.seek.value = (audio.currentTime / audio.duration) * 100; } });
  audio.addEventListener('ended', () => { if (repeat) { audio.currentTime = 0; audio.play(); return; } next(true); });

  function playAt(i) { if (i < 0 || i >= queue.length) return; index = i; const tr = queue[i]; audio.src = tr.url; el.cover.src = tr.cover || ''; el.title.textContent = tr.title || '—'; el.artist.textContent = tr.artist || '—'; setActive(i); updateLikeBtn(); audio.play().catch(()=>{}); }
  function next() { if (!queue.length) return; if (shuffle) { let rnd = Math.floor(Math.random() * queue.length); if (queue.length > 1 && rnd === index) rnd = (rnd + 1) % queue.length; playAt(rnd); } else { playAt((index + 1) % queue.length); } }
  function prev() { if (!queue.length) return; if (audio.currentTime > 2) { audio.currentTime = 0; return; } playAt((index - 1 + queue.length) % queue.length); }

  function renderList(list) {
    if (!el.tracks) return;
    el.tracks.innerHTML = '';
    list.forEach((t, i) => {
      const row = document.createElement('div');
      row.className = 'track';
      row.dataset.idx = i;
      row.innerHTML = `
        <img class="cover" src="${t.cover || ''}" alt="">
        <button class="play s">▶</button>
        <div class="meta">
          <div class="title">${t.title}</div>
          <div class="muted s">${t.artist || ''}</div>
        </div>
        <button class="btn ghost s">Добавить</button>
      `;
      row.querySelector('.play').addEventListener('click', () => playAt(i));
      el.tracks.appendChild(row);
    });
  }

  fetch('/api/tracks').then(r => r.json()).then(list => { queue = list; renderList(queue); });
  el.btnPlayAll?.addEventListener('click', () => { if (!queue.length) return; playAt(0); });
})();
