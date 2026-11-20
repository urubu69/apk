import re
import os

src_html_path = r'c:\Users\carlo\Desktop\Codigos\musica\mobile\templates\index.html'
with open(src_html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Substitui caminhos estáticos para caminhos locais de assets
html = html.replace('/static/icon-192.png', 'icon.png')
html = html.replace('/static/icon-512.png', 'icon.png')

# Adiciona o botão 'Importar MP3' no formulário
import_btn = '''
        <div style="display:flex; gap:8px; margin-top:8px;">
          <button type="button" class="btn-add" style="flex:1; background:#282828; color:#fff; border:1px solid #444;" onclick="triggerImportLocal()">
            📁 Importar MP3 do Celular
          </button>
        </div>
'''
html = html.replace('</form>', import_btn + '      </form>')

# Encontra onde termina o HTML e começa o script
script_start = html.find('<script>')
html_head_body = html[:script_start]

native_script = '''<script>
    let state = { tracks: [], playlists: [] };
    let currentPlaylistId = 'downloads';
    let currentTrack = null;
    let currentTrackIndex = -1;
    let selectedTrackForModal = null;
    let isNativePlaying = false;

    const audio = document.getElementById('audioElement');
    const btnPlayPause = document.getElementById('btnPlayPause');
    const progressFill = document.getElementById('progressFill');

    function toggleSidebar(open) {
      const drawer = document.getElementById('sidebarDrawer');
      const backdrop = document.getElementById('sidebarBackdrop');
      if (open) {
        drawer.classList.add('open');
        backdrop.classList.add('open');
      } else {
        drawer.classList.remove('open');
        backdrop.classList.remove('open');
      }
    }

    function fetchState() {
      if (window.Android && window.Android.getLibrary) {
        try {
          const raw = window.Android.getLibrary();
          state = JSON.parse(raw);
          if (!state.playlists || state.playlists.length === 0) {
            state.playlists = [{ id: 'downloads', name: 'Downloads', track_ids: [] }];
          }
          if (!state.tracks) state.tracks = [];
          renderSidebar();
          renderActivePlaylistBanner();
          renderTracks();
          return;
        } catch(e) {
          console.error(e);
        }
      }
      
      // Fallback para navegador web
      fetch('/api/state')
        .then(r => r.json())
        .then(data => {
          state = data;
          renderSidebar();
          renderActivePlaylistBanner();
          renderTracks();
        })
        .catch(console.error);
    }

    function saveState() {
      if (window.Android && window.Android.saveLibrary) {
        window.Android.saveLibrary(JSON.stringify(state));
      }
    }

    function renderSidebar() {
      const dlPl = state.playlists.find(p => p.id === 'downloads') || { track_ids: [] };
      const dlCount = dlPl.track_ids ? dlPl.track_ids.length : 0;
      document.getElementById('sidebarCountDownloads').textContent = `${dlCount} música${dlCount === 1 ? '' : 's'}`;

      const cardDl = document.getElementById('sidebarCardDownloads');
      const dotDl = document.getElementById('dotDownloads');
      if (currentPlaylistId === 'downloads') {
        cardDl.classList.add('active');
        dotDl.style.display = 'block';
      } else {
        cardDl.classList.remove('active');
        dotDl.style.display = 'none';
      }

      const customList = document.getElementById('sidebarCustomList');
      customList.innerHTML = '';

      const customPlaylists = state.playlists.filter(p => p.id !== 'downloads');
      if (customPlaylists.length === 0) {
        customList.innerHTML = '<div style="padding:12px; color:#777; font-size:12px; text-align:center;">Nenhuma playlist personalizada criada</div>';
        return;
      }

      customPlaylists.forEach(pl => {
        const count = pl.track_ids ? pl.track_ids.length : 0;
        const isActive = pl.id === currentPlaylistId;
        const item = document.createElement('div');
        item.className = `sidebar-pl-item ${isActive ? 'active' : ''}`;
        item.onclick = () => selectPlaylist(pl.id);

        item.innerHTML = `
          <div class="sidebar-pl-dot" style="display: ${isActive ? 'block' : 'none'}"></div>
          <div class="sidebar-pl-info">
            <div class="sidebar-pl-name">${escapeHtml(pl.name)}</div>
            <div class="sidebar-pl-meta">${count} música${count === 1 ? '' : 's'}</div>
          </div>
          <div class="sidebar-pl-actions" onclick="event.stopPropagation()">
            <button class="btn-sidebar-icon" title="Renomear" onclick="promptRenamePlaylist('${pl.id}')">✏️</button>
            <button class="btn-sidebar-icon btn-del" title="Excluir" onclick="deletePlaylist('${pl.id}')">🗑️</button>
          </div>
        `;
        customList.appendChild(item);
      });
    }

    function renderActivePlaylistBanner() {
      const pl = state.playlists.find(p => p.id === currentPlaylistId);
      const name = pl ? pl.name : 'Downloads';
      const count = pl && pl.track_ids ? pl.track_ids.length : 0;

      document.getElementById('activePlaylistTitle').textContent = name;
      document.getElementById('activePlaylistCount').textContent = `${count} música${count === 1 ? '' : 's'}`;
      document.getElementById('badgePlaylistTarget').textContent = `Salva em ${name}`;
    }

    function selectPlaylist(id) {
      currentPlaylistId = id;
      toggleSidebar(false);
      renderSidebar();
      renderActivePlaylistBanner();
      renderTracks();
    }

    function renderTracks() {
      const listEl = document.getElementById('trackList');
      listEl.innerHTML = '';

      const pl = state.playlists.find(p => p.id === currentPlaylistId);
      const trackIds = pl ? (pl.track_ids || []) : [];
      const visibleTracks = state.tracks.filter(t => trackIds.includes(t.id));

      if (visibleTracks.length === 0) {
        listEl.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">🎵</div>
            <p>Nenhuma música nesta playlist.</p>
            <p style="font-size:12px; margin-top:4px;">Cole um link acima ou importe MP3 do celular!</p>
          </div>
        `;
        return;
      }

      visibleTracks.forEach(track => {
        const item = document.createElement('div');
        const isPlayingThis = currentTrack && currentTrack.id === track.id;
        item.className = `track-item ${isPlayingThis ? 'playing' : ''}`;
        item.onclick = () => playTrack(track.id);

        const coverSrc = track.coverPath || (track.cover ? track.cover : 'icon.png');

        item.innerHTML = `
          <img src="${coverSrc}" class="track-cover" onerror="this.src='icon.png'" alt="Cover">
          <div class="track-info">
            <div class="track-title">${escapeHtml(track.title)}</div>
            <div class="track-artist">${escapeHtml(track.artist || 'SpotyLink')}</div>
          </div>
          <div class="track-actions" onclick="event.stopPropagation()">
            <button class="btn-action" title="Adicionar à playlist" onclick="openAddToPlaylistModal('${track.id}')">＋</button>
            <button class="btn-action" title="Excluir" onclick="deleteTrack('${track.id}')">🗑️</button>
          </div>
        `;
        listEl.appendChild(item);
      });
    }

    function playTrack(id) {
      const pl = state.playlists.find(p => p.id === currentPlaylistId);
      const trackIds = pl ? pl.track_ids : [];
      const visibleTracks = state.tracks.filter(t => trackIds.includes(t.id));

      currentTrackIndex = visibleTracks.findIndex(t => t.id === id);
      if (currentTrackIndex === -1) return;

      currentTrack = visibleTracks[currentTrackIndex];
      updatePlayerUI();

      if (window.Android && window.Android.playTrack) {
        const audioSrc = currentTrack.audioPath || currentTrack.url || '';
        window.Android.playTrack(audioSrc, currentTrack.title, currentTrack.artist || 'SpotyLink');
      } else {
        audio.src = `/api/audio/${id}`;
        audio.play().catch(console.error);
      }
      renderTracks();
    }

    function togglePlayPause() {
      if (!currentTrack) {
        const pl = state.playlists.find(p => p.id === currentPlaylistId);
        if (pl && pl.track_ids && pl.track_ids.length > 0) {
          playTrack(pl.track_ids[0]);
        }
        return;
      }

      if (window.Android) {
        if (isNativePlaying) {
          window.Android.pauseTrack();
        } else {
          window.Android.resumeTrack();
        }
      } else {
        if (audio.paused) audio.play(); else audio.pause();
      }
    }

    function playNext() {
      const pl = state.playlists.find(p => p.id === currentPlaylistId);
      const trackIds = pl ? pl.track_ids : [];
      const visibleTracks = state.tracks.filter(t => trackIds.includes(t.id));
      if (visibleTracks.length === 0) return;

      currentTrackIndex = (currentTrackIndex + 1) % visibleTracks.length;
      playTrack(visibleTracks[currentTrackIndex].id);
    }

    function playPrev() {
      const pl = state.playlists.find(p => p.id === currentPlaylistId);
      const trackIds = pl ? pl.track_ids : [];
      const visibleTracks = state.tracks.filter(t => trackIds.includes(t.id));
      if (visibleTracks.length === 0) return;

      currentTrackIndex = (currentTrackIndex - 1 + visibleTracks.length) % visibleTracks.length;
      playTrack(visibleTracks[currentTrackIndex].id);
    }

    function updatePlayerUI() {
      if (!currentTrack) return;
      document.getElementById('playerTitle').textContent = currentTrack.title;
      document.getElementById('playerArtist').textContent = currentTrack.artist || 'SpotyLink';
      document.getElementById('playerCover').src = currentTrack.coverPath || currentTrack.cover || 'icon.png';
    }

    // Callbacks recebidos da camada nativa Android
    window.onNativePlaybackState = function(isPlaying, currentPosMs, durationMs) {
      isNativePlaying = isPlaying;
      btnPlayPause.textContent = isPlaying ? '⏸' : '▶';
      if (durationMs > 0) {
        const pct = (currentPosMs / durationMs) * 100;
        progressFill.style.width = `${pct}%`;
      }
    };

    window.onNativeDownloadComplete = function(success, trackId, title, filePath) {
      document.getElementById('btnSubmitAdd').textContent = '+ Adicionar';
      document.getElementById('btnSubmitAdd').disabled = false;

      if (!success) return;

      const newTrack = {
        id: trackId,
        title: title || 'Nova Música',
        artist: 'SpotyLink',
        audioPath: filePath,
        cover: 'icon.png'
      };

      state.tracks.push(newTrack);

      let targetPl = state.playlists.find(p => p.id === currentPlaylistId);
      if (!targetPl) targetPl = state.playlists.find(p => p.id === 'downloads');
      if (targetPl && !targetPl.track_ids.includes(trackId)) {
        targetPl.track_ids.push(trackId);
      }

      saveState();
      renderSidebar();
      renderActivePlaylistBanner();
      renderTracks();
    };

    function triggerImportLocal() {
      if (window.Android && window.Android.pickLocalAudio) {
        window.Android.pickLocalAudio();
      } else {
        alert('Disponível no app nativo (.apk)');
      }
    }

    // Adição de música
    document.getElementById('formAddMusic').onsubmit = function(e) {
      e.preventDefault();
      const input = document.getElementById('inputUrl');
      const url = input.value.trim();
      if (!url) return;

      document.getElementById('btnSubmitAdd').textContent = 'Baixando...';
      document.getElementById('btnSubmitAdd').disabled = true;

      if (window.Android && window.Android.downloadAudioLink) {
        window.Android.downloadAudioLink(url);
        input.value = '';
      } else {
        // Fallback web
        fetch('/api/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: url, playlist_id: currentPlaylistId })
        }).then(r => r.json()).then(data => {
          document.getElementById('btnSubmitAdd').textContent = '+ Adicionar';
          document.getElementById('btnSubmitAdd').disabled = false;
          input.value = '';
          fetchState();
        }).catch(err => {
          alert('Erro no download: ' + err);
          document.getElementById('btnSubmitAdd').textContent = '+ Adicionar';
          document.getElementById('btnSubmitAdd').disabled = false;
        });
      }
    };

    async function pasteFromClipboard() {
      try {
        const text = await navigator.clipboard.readText();
        if (text) document.getElementById('inputUrl').value = text.trim();
      } catch (err) {
        console.warn(err);
      }
    }

    function promptCreatePlaylist() {
      const name = prompt('Nome da nova playlist:');
      if (!name || !name.trim()) return;

      const newId = 'pl_' + Date.now();
      state.playlists.push({ id: newId, name: name.trim(), track_ids: [] });
      saveState();
      selectPlaylist(newId);
    }

    function promptRenamePlaylist(id) {
      const pl = state.playlists.find(p => p.id === id);
      if (!pl) return;
      const newName = prompt('Novo nome da playlist:', pl.name);
      if (!newName || !newName.trim()) return;

      pl.name = newName.trim();
      saveState();
      renderSidebar();
      renderActivePlaylistBanner();
    }

    function deletePlaylist(id) {
      if (!confirm('Deseja realmente excluir esta playlist? As músicas baixadas não serão apagadas.')) return;
      state.playlists = state.playlists.filter(p => p.id !== id);
      if (currentPlaylistId === id) currentPlaylistId = 'downloads';
      saveState();
      renderSidebar();
      renderActivePlaylistBanner();
      renderTracks();
    }

    function deleteTrack(id) {
      if (!confirm('Deseja excluir esta faixa?')) return;

      if (window.Android && window.Android.deleteTrackFile) {
        window.Android.deleteTrackFile(id);
      }

      state.playlists.forEach(p => {
        p.track_ids = p.track_ids.filter(tid => tid !== id);
      });
      state.tracks = state.tracks.filter(t => t.id !== id);

      if (currentTrack && currentTrack.id === id) {
        if (window.Android) window.Android.pauseTrack();
        currentTrack = null;
        document.getElementById('playerTitle').textContent = 'Nenhuma música tocando';
        document.getElementById('playerArtist').textContent = 'Selecione uma faixa acima';
      }

      saveState();
      renderSidebar();
      renderActivePlaylistBanner();
      renderTracks();
    }

    function openAddToPlaylistModal(trackId) {
      selectedTrackForModal = trackId;
      const listEl = document.getElementById('modalPlList');
      listEl.innerHTML = '';

      state.playlists.forEach(pl => {
        const has = pl.track_ids && pl.track_ids.includes(trackId);
        const item = document.createElement('div');
        item.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid #282828;';
        item.innerHTML = `
          <span style="font-weight:600">${escapeHtml(pl.name)}</span>
          <button class="btn-action" style="background:${has ? '#e91429' : '#1DB954'}; border:none; color:#fff; padding:6px 14px; border-radius:20px; font-weight:700;">
            ${has ? 'Remover' : 'Adicionar'}
          </button>
        `;
        item.querySelector('button').onclick = () => {
          if (has) {
            pl.track_ids = pl.track_ids.filter(tid => tid !== trackId);
          } else {
            if (!pl.track_ids) pl.track_ids = [];
            pl.track_ids.push(trackId);
          }
          saveState();
          openAddToPlaylistModal(trackId);
          renderSidebar();
          renderActivePlaylistBanner();
          renderTracks();
        };
        listEl.appendChild(item);
      });

      document.getElementById('modalPlaylist').classList.add('open');
    }

    function closeModal() {
      document.getElementById('modalPlaylist').classList.remove('open');
      selectedTrackForModal = null;
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/[&<>"']/g, m => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      })[m]);
    }

    // Inicialização ao carregar
    window.addEventListener('DOMContentLoaded', fetchState);
  </script>
</body>
</html>
'''

full_html = html_head_body + native_script

dest_path = r'c:\Users\carlo\Desktop\Codigos\musica\android-app\app\src\main\assets\index.html'
with open(dest_path, 'w', encoding='utf-8') as f:
    f.write(full_html)

print('Arquivo gerado com sucesso em:', dest_path, f'({len(full_html)} bytes)')
