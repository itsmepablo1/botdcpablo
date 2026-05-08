/* ─────────────────────────────────────────────────────────────────────────
   app.js — Discord Bot Panel Frontend Logic
   ───────────────────────────────────────────────────────────────────────── */

const API = '';  // same origin

// ── Auth ──────────────────────────────────────────────────────────────────────

function getToken() { return localStorage.getItem('bot_token'); }

async function apiFetch(path, options = {}) {
  const token = getToken();
  const res = await fetch(API + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    localStorage.removeItem('bot_token');
    window.location.href = '/login';
  }
  return res;
}

// ── Boot ──────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  if (!getToken()) { window.location.href = '/login'; return; }

  // Verify token
  const me = await apiFetch('/api/auth/me');
  if (!me.ok) { window.location.href = '/login'; return; }
  const meData = await me.json();
  document.getElementById('sidebarUser').textContent = meData.username || 'Admin';

  setupNav();
  setupMobileMenu();
  setupLogout();
  loadDashboard();
});

// ── Navigation ────────────────────────────────────────────────────────────────

const PAGE_TITLES = {
  dashboard:  ['Dashboard',          'Overview semua fitur bot'],
  welcome:    ['Welcome / Leave',    'Konfigurasi pesan selamat datang & perpisahan'],
  roles:      ['Role Selector',      'Kelola panel role dropdown'],
  autovoice:  ['Auto Voice Channel', 'Konfigurasi auto-create voice channel'],
  status:     ['Status Channel',     'Realtime member & online counter'],
  streaming:  ['Streaming Notif',    'Notifikasi live streaming'],
};

function setupNav() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', e => {
      e.preventDefault();
      const page = item.dataset.page;
      navigateTo(page);
      // Mobile: close sidebar
      document.getElementById('sidebar').classList.remove('open');
    });
  });
}

function navigateTo(page) {
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

  const navItem = document.querySelector(`.nav-item[data-page="${page}"]`);
  const pageEl  = document.getElementById(`page-${page}`);
  if (navItem) navItem.classList.add('active');
  if (pageEl)  pageEl.classList.add('active');

  const [title, sub] = PAGE_TITLES[page] || [page, ''];
  document.getElementById('pageTitle').textContent = title;
  document.getElementById('pageSub').textContent   = sub;
}

// ── Mobile Menu ───────────────────────────────────────────────────────────────

function setupMobileMenu() {
  document.getElementById('menuBtn').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
  });
}

// ── Logout ────────────────────────────────────────────────────────────────────

function setupLogout() {
  document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('bot_token');
    window.location.href = '/login';
  });
}

// ── Alert Helper ─────────────────────────────────────────────────────────────

function showAlert(id, msg, type = 'success') {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.className = `alert ${type}`;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 4000);
}

// ─────────────────────────────────────────────────────────────────────────────
// DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────

async function loadDashboard() {
  const res  = await apiFetch('/api/dashboard/stats');
  const data = await res.json();

  document.getElementById('st-configs').textContent  = data.configs       ?? '—';
  document.getElementById('st-panels').textContent   = data.role_panels   ?? '—';
  document.getElementById('st-vcs').textContent      = data.active_vcs    ?? '—';
  document.getElementById('st-live').textContent     = data.live_streamers ?? '—';

  const res2  = await apiFetch('/api/dashboard/guilds');
  const guilds = await res2.json();
  const tbody  = document.getElementById('guildsBody');
  if (!guilds.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Belum ada server yang terkonfigurasi.</td></tr>';
    return;
  }
  tbody.innerHTML = guilds.map(g => `
    <tr>
      <td><code style="color:#c4b5fd">${g.guild_id}</code></td>
      <td>${g.welcome_channel_id ? `<code>${g.welcome_channel_id}</code>` : '<span class="text-muted">—</span>'}</td>
      <td>${g.leave_channel_id   ? `<code>${g.leave_channel_id}</code>`   : '<span class="text-muted">—</span>'}</td>
      <td>${g.status_member_channel_id ? `<code>${g.status_member_channel_id}</code>` : '<span class="text-muted">—</span>'}</td>
      <td>${g.streaming_channel_id    ? `<code>${g.streaming_channel_id}</code>`    : '<span class="text-muted">—</span>'}</td>
      <td>${g.autovoice_channel_id    ? `<code>${g.autovoice_channel_id}</code>`    : '<span class="text-muted">—</span>'}</td>
    </tr>
  `).join('');
}

// ─────────────────────────────────────────────────────────────────────────────
// WELCOME / LEAVE
// ─────────────────────────────────────────────────────────────────────────────

async function loadWelcome() {
  const gid = document.getElementById('wl-guild').value.trim();
  if (!gid) return showAlert('wl-alert', '❌ Masukkan Guild ID!', 'error');
  const res  = await apiFetch(`/api/welcome/${gid}`);
  const data = await res.json();
  document.getElementById('wl-wch').value  = data.welcome_channel_id  || '';
  document.getElementById('wl-wmsg').value = data.welcome_message      || '';
  document.getElementById('wl-lch').value  = data.leave_channel_id    || '';
  document.getElementById('wl-lmsg').value = data.leave_message        || '';
  showAlert('wl-alert', '✅ Config dimuat!', 'success');
}

async function saveWelcome() {
  const gid = document.getElementById('wl-guild').value.trim();
  if (!gid) return showAlert('wl-alert', '❌ Masukkan Guild ID!', 'error');
  const body = {
    guild_id:          parseInt(gid),
    welcome_channel_id: parseInt(document.getElementById('wl-wch').value)  || null,
    welcome_message:    document.getElementById('wl-wmsg').value.trim()     || null,
    leave_channel_id:  parseInt(document.getElementById('wl-lch').value)   || null,
    leave_message:     document.getElementById('wl-lmsg').value.trim()     || null,
  };
  const res = await apiFetch('/api/welcome/update', { method: 'POST', body: JSON.stringify(body) });
  if (res.ok) showAlert('wl-alert', '✅ Config berhasil disimpan!', 'success');
  else        showAlert('wl-alert', '❌ Gagal menyimpan config.', 'error');
}

// ─────────────────────────────────────────────────────────────────────────────
// ROLES
// ─────────────────────────────────────────────────────────────────────────────

async function loadRoles() {
  const gid = document.getElementById('roles-guild').value.trim();
  if (!gid) return showAlert('roles-alert', '❌ Masukkan Guild ID!', 'error');
  const res    = await apiFetch(`/api/roles/${gid}`);
  const panels = await res.json();
  renderRolePanels(panels);
}

function renderRolePanels(panels) {
  const container = document.getElementById('roles-panels');
  if (!panels.length) {
    container.innerHTML = '<div class="card" style="padding:22px;color:var(--text3);text-align:center">Belum ada panel role.</div>';
    return;
  }
  container.innerHTML = panels.map(p => `
    <div class="panel-block">
      <div class="panel-block-header">
        <div>
          <span style="font-weight:600;color:var(--text)">Panel #${p.id}: ${escHtml(p.title)}</span>
          <span style="margin-left:12px;font-size:12px;color:var(--text3)">Channel: <code>${p.channel_id}</code></span>
          ${p.message_id ? `<span style="margin-left:8px;font-size:12px;color:var(--green)">✅ Posted</span>` : `<span style="margin-left:8px;font-size:12px;color:var(--amber)">⚠ Belum dikirim</span>`}
        </div>
        <button class="btn-danger" style="padding:6px 12px;font-size:12px" onclick="deletePanel(${p.id})">🗑 Hapus</button>
      </div>
      <div class="panel-block-body">
        ${p.groups.map(g => `
          <div style="margin-bottom:12px">
            <div style="font-size:13px;font-weight:600;color:var(--text2);margin-bottom:6px">📋 ${escHtml(g.name)}</div>
            <div style="display:flex;flex-wrap:wrap;gap:8px">
              ${g.options.map(o => `
                <span style="background:rgba(124,58,237,0.15);border:1px solid rgba(124,58,237,0.25);border-radius:8px;padding:4px 10px;font-size:12px;color:#c4b5fd">
                  ${o.emoji || ''} Role ID: ${o.role_id}${o.description ? ` — ${escHtml(o.description)}` : ''}
                </span>
              `).join('')}
            </div>
          </div>
        `).join('')}
        <div style="display:flex;gap:10px;margin-top:10px">
          <input type="text" id="ng-name-${p.id}" placeholder="Nama grup baru..." style="max-width:200px"/>
          <button class="btn-sm" onclick="addGroup(${p.id})">➕ Tambah Grup</button>
        </div>
      </div>
    </div>
  `).join('');
}

async function createPanel() {
  const gid   = document.getElementById('roles-guild').value.trim();
  const chid  = document.getElementById('r-chid').value.trim();
  const title = document.getElementById('r-title').value.trim() || '🎭 Pilih Role Kamu';
  const desc  = document.getElementById('r-desc').value.trim()  || 'Pilih role menggunakan dropdown.';
  if (!gid || !chid) return showAlert('roles-alert', '❌ Guild ID & Channel ID wajib diisi!', 'error');
  const res = await apiFetch('/api/roles/panel/create', {
    method: 'POST',
    body: JSON.stringify({ guild_id: parseInt(gid), channel_id: parseInt(chid), title, description: desc })
  });
  if (res.ok) {
    const d = await res.json();
    showAlert('roles-alert', `✅ Panel #${d.panel_id} dibuat! Gunakan /roles post ${d.panel_id} di Discord untuk mengirimnya.`, 'success');
    loadRoles();
  } else {
    showAlert('roles-alert', '❌ Gagal membuat panel.', 'error');
  }
}

async function deletePanel(panelId) {
  if (!confirm(`Hapus panel #${panelId}?`)) return;
  const res = await apiFetch(`/api/roles/panel/${panelId}`, { method: 'DELETE' });
  if (res.ok) { showAlert('roles-alert', `✅ Panel #${panelId} dihapus.`, 'success'); loadRoles(); }
  else showAlert('roles-alert', '❌ Gagal menghapus panel.', 'error');
}

async function addGroup(panelId) {
  const nameEl = document.getElementById(`ng-name-${panelId}`);
  const name   = nameEl.value.trim();
  if (!name) return;
  const res = await apiFetch('/api/roles/group/add', {
    method: 'POST', body: JSON.stringify({ panel_id: panelId, name })
  });
  if (res.ok) { showAlert('roles-alert', `✅ Grup "${name}" ditambahkan. Tambah role via /roles add di Discord.`, 'success'); loadRoles(); }
  else showAlert('roles-alert', '❌ Gagal.', 'error');
}

// ─────────────────────────────────────────────────────────────────────────────
// AUTO VOICE
// ─────────────────────────────────────────────────────────────────────────────

async function loadAutoVoice() {
  const gid = document.getElementById('av-guild').value.trim();
  if (!gid) return showAlert('av-alert', '❌ Masukkan Guild ID!', 'error');
  const res  = await apiFetch(`/api/autovoice/${gid}`);
  const data = await res.json();
  document.getElementById('av-chid').value = data.autovoice_channel_id || '';
  showAlert('av-alert', '✅ Config dimuat!', 'success');
  await loadActiveVCs();
}

async function loadActiveVCs() {
  const gid = document.getElementById('av-guild').value.trim();
  if (!gid) return;
  const res  = await apiFetch(`/api/autovoice/${gid}/active-vcs`);
  const vcs  = await res.json();
  const tbody = document.getElementById('av-vcs-body');
  const countEl = document.getElementById('av-vc-count');

  if (!vcs || !vcs.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Tidak ada VC aktif saat ini.</td></tr>';
    countEl.textContent = '0 channel aktif';
    return;
  }
  countEl.textContent = `${vcs.length} channel aktif`;
  tbody.innerHTML = vcs.map(v => `
    <tr>
      <td><code style="color:#c4b5fd">${v.channel_id}</code></td>
      <td>${escHtml(v.name || '—')}</td>
      <td><code>${v.owner_id}</code></td>
      <td>${v.user_limit ? v.user_limit : '<span class="text-muted">∞</span>'}</td>
      <td>${v.is_locked
        ? '<span style="color:#ef4444">🔒 Terkunci</span>'
        : '<span style="color:#22c55e">🔓 Terbuka</span>'}</td>
      <td style="color:var(--text3);font-size:12px">${v.created_at ? v.created_at.split('.')[0] : '—'}</td>
    </tr>
  `).join('');
}

async function saveAutoVoice() {
  const gid  = document.getElementById('av-guild').value.trim();
  const chid = document.getElementById('av-chid').value.trim();
  if (!gid) return showAlert('av-alert', '❌ Masukkan Guild ID!', 'error');
  const res = await apiFetch('/api/autovoice/update', {
    method: 'POST', body: JSON.stringify({ guild_id: parseInt(gid), channel_id: parseInt(chid) || null })
  });
  if (res.ok) showAlert('av-alert', '✅ Config disimpan!', 'success');
  else        showAlert('av-alert', '❌ Gagal.', 'error');
}

async function disableAutoVoice() {
  const gid = document.getElementById('av-guild').value.trim();
  if (!gid) return showAlert('av-alert', '❌ Masukkan Guild ID!', 'error');
  await apiFetch('/api/autovoice/update', {
    method: 'POST', body: JSON.stringify({ guild_id: parseInt(gid), channel_id: null })
  });
  document.getElementById('av-chid').value = '';
  showAlert('av-alert', '✅ Auto Voice dinonaktifkan.', 'success');
}


// ─────────────────────────────────────────────────────────────────────────────
// STATUS CHANNEL
// ─────────────────────────────────────────────────────────────────────────────

async function loadStatus() {
  const gid = document.getElementById('sc-guild').value.trim();
  if (!gid) return showAlert('sc-alert', '❌ Masukkan Guild ID!', 'error');
  const res  = await apiFetch(`/api/status/${gid}`);
  const data = await res.json();
  document.getElementById('sc-mch').value = data.status_member_channel_id || '';
  document.getElementById('sc-och').value = data.status_online_channel_id || '';
  showAlert('sc-alert', '✅ Config dimuat!', 'success');
}

async function saveStatus() {
  const gid = document.getElementById('sc-guild').value.trim();
  if (!gid) return showAlert('sc-alert', '❌ Masukkan Guild ID!', 'error');
  const res = await apiFetch('/api/status/update', {
    method: 'POST',
    body: JSON.stringify({
      guild_id:                  parseInt(gid),
      status_member_channel_id:  parseInt(document.getElementById('sc-mch').value) || null,
      status_online_channel_id:  parseInt(document.getElementById('sc-och').value) || null,
    })
  });
  if (res.ok) showAlert('sc-alert', '✅ Config disimpan!', 'success');
  else        showAlert('sc-alert', '❌ Gagal.', 'error');
}

// ─────────────────────────────────────────────────────────────────────────────
// STREAMING
// ─────────────────────────────────────────────────────────────────────────────

async function loadStreaming() {
  const gid = document.getElementById('st-guild').value.trim();
  if (!gid) return showAlert('st-alert', '❌ Masukkan Guild ID!', 'error');
  const res  = await apiFetch(`/api/streaming/${gid}`);
  const data = await res.json();
  document.getElementById('st-chid').value = data.streaming_channel_id || '';
  document.getElementById('st-rid').value  = data.streaming_role_id    || '';
  showAlert('st-alert', '✅ Config dimuat!', 'success');
}

async function saveStreaming() {
  const gid = document.getElementById('st-guild').value.trim();
  if (!gid) return showAlert('st-alert', '❌ Masukkan Guild ID!', 'error');
  const res = await apiFetch('/api/streaming/update', {
    method: 'POST',
    body: JSON.stringify({
      guild_id:   parseInt(gid),
      channel_id: parseInt(document.getElementById('st-chid').value) || null,
      role_id:    parseInt(document.getElementById('st-rid').value)  || null,
    })
  });
  if (res.ok) showAlert('st-alert', '✅ Config disimpan!', 'success');
  else        showAlert('st-alert', '❌ Gagal.', 'error');
}

async function disableStreaming() {
  const gid = document.getElementById('st-guild').value.trim();
  if (!gid) return showAlert('st-alert', '❌ Masukkan Guild ID!', 'error');
  await apiFetch('/api/streaming/update', {
    method: 'POST', body: JSON.stringify({ guild_id: parseInt(gid), channel_id: null, role_id: null })
  });
  document.getElementById('st-chid').value = '';
  document.getElementById('st-rid').value  = '';
  showAlert('st-alert', '✅ Streaming notif dinonaktifkan.', 'success');
}

// ── Utils ─────────────────────────────────────────────────────────────────────

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
