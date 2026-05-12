/* â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
   app.js â€” Discord Bot Panel Frontend Logic
   â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

const API = '';  // same origin

// â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

// â”€â”€ Boot â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

document.addEventListener('DOMContentLoaded', async () => {
  if (!getToken()) { window.location.href = '/login'; return; }

  // Verify token
  const me = await apiFetch('/api/auth/me');
  if (!me.ok) { window.location.href = '/login'; return; }
  const meData = await me.json();
  document.getElementById('sidebarUser').textContent = meData.username || 'Admin';

  // Restore saved Guild ID ke semua input
  restoreGuildIds();

  setupNav();
  setupMobileMenu();
  setupLogout();
  loadDashboard();
  checkBotStatus();
  loadSchedule();
});

// â”€â”€ Guild ID Persistence â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const GUILD_ID_FIELDS = {
  welcome:   'wl-guild',
  roles:     'roles-guild',
  autovoice: 'av-guild',
  status:    'sc-guild',
  streaming: 'st-guild',
};

function saveGuildId(page, value) {
  if (value) localStorage.setItem(`gid_${page}`, value);
}

function restoreGuildIds() {
  for (const [page, fieldId] of Object.entries(GUILD_ID_FIELDS)) {
    const saved = localStorage.getItem(`gid_${page}`);
    const el = document.getElementById(fieldId);
    if (el && saved) el.value = saved;
  }
}

// â”€â”€ Navigation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

  // Auto-load kalau guild ID sudah tersimpan
  const fieldId = GUILD_ID_FIELDS[page];
  if (fieldId) {
    const saved = localStorage.getItem(`gid_${page}`);
    const el = document.getElementById(fieldId);
    if (el && saved) {
      el.value = saved;
      // Auto-load per halaman
      if (page === 'welcome')   loadWelcome();
      if (page === 'roles')     loadRoles();
      if (page === 'autovoice') loadAutoVoice();
      if (page === 'status')    loadStatus();
      if (page === 'streaming') loadStreaming();
    }
  }
}

// â”€â”€ Mobile Menu â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function setupMobileMenu() {
  document.getElementById('menuBtn').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
  });
}

// â”€â”€ Logout â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function setupLogout() {
  document.getElementById('logoutBtn').addEventListener('click', () => {
    localStorage.removeItem('bot_token');
    window.location.href = '/login';
  });
}

// â”€â”€ Alert Helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function showAlert(id, msg, type = 'success') {
  const el = document.getElementById(id);
  if (!el) { console.warn('showAlert: element not found:', id); return; }
  el.textContent = msg;
  el.className = `alert ${type}`;
  el.style.display = 'block';
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => { el.style.display = 'none'; }, 8000);
}

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// DASHBOARD
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function loadDashboard() {
  const res  = await apiFetch('/api/dashboard/stats');
  const data = await res.json();

  document.getElementById('st-configs').textContent  = data.configs       ?? 'â€”';
  document.getElementById('st-panels').textContent   = data.role_panels   ?? 'â€”';
  document.getElementById('st-vcs').textContent      = data.active_vcs    ?? 'â€”';
  document.getElementById('st-live').textContent     = data.live_streamers ?? 'â€”';

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
      <td>${g.welcome_channel_id ? `<code>${g.welcome_channel_id}</code>` : '<span class="text-muted">â€”</span>'}</td>
      <td>${g.leave_channel_id   ? `<code>${g.leave_channel_id}</code>`   : '<span class="text-muted">â€”</span>'}</td>
      <td>${g.status_member_channel_id ? `<code>${g.status_member_channel_id}</code>` : '<span class="text-muted">â€”</span>'}</td>
      <td>${g.streaming_channel_id    ? `<code>${g.streaming_channel_id}</code>`    : '<span class="text-muted">â€”</span>'}</td>
      <td>${g.autovoice_channel_id    ? `<code>${g.autovoice_channel_id}</code>`    : '<span class="text-muted">â€”</span>'}</td>
    </tr>
  `).join('');
}

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// WELCOME / LEAVE
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function loadWelcome() {
  const gid = document.getElementById('wl-guild').value.trim();
  if (!gid) return showAlert('wl-alert', 'âŒ Masukkan Guild ID!', 'error');
  saveGuildId('welcome', gid);
  const res  = await apiFetch(`/api/welcome/${gid}`);
  const data = await res.json();
  document.getElementById('wl-wch').value  = data.welcome_channel_id  || '';
  document.getElementById('wl-wmsg').value = data.welcome_message      || '';
  document.getElementById('wl-lch').value  = data.leave_channel_id    || '';
  document.getElementById('wl-lmsg').value = data.leave_message        || '';
  showAlert('wl-alert', 'âœ… Config dimuat!', 'success');
}

async function saveWelcome() {
  const gid = document.getElementById('wl-guild').value.trim();
  if (!gid) return showAlert('wl-alert', 'âŒ Masukkan Guild ID!', 'error');
  const body = {
    guild_id:           gid,
    welcome_channel_id: document.getElementById('wl-wch').value.trim()  || null,
    welcome_message:    document.getElementById('wl-wmsg').value.trim()  || null,
    leave_channel_id:   document.getElementById('wl-lch').value.trim()   || null,
    leave_message:      document.getElementById('wl-lmsg').value.trim()  || null,
  };
  const res = await apiFetch('/api/welcome/update', { method: 'POST', body: JSON.stringify(body) });
  if (res.ok) showAlert('wl-alert', 'âœ… Config berhasil disimpan!', 'success');
  else        showAlert('wl-alert', 'âŒ Gagal menyimpan config.', 'error');
}

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// ROLES
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function loadRoles() {
  const gid = document.getElementById('roles-guild').value.trim();
  if (!gid) return showAlert('roles-alert', 'âŒ Masukkan Guild ID!', 'error');
  saveGuildId('roles', gid);
  const res    = await apiFetch(`/api/roles/${gid}`);
  const panels = await res.json();
  renderRolePanels(panels);
}

function renderRolePanels(panels) {
  const container = document.getElementById('roles-panels');
  if (!panels.length) {
    container.innerHTML = '<div class="card" style="padding:22px;color:var(--text3);text-align:center">Belum ada panel role. Buat panel baru di atas.</div>';
    return;
  }
  container.innerHTML = panels.map(p => `
    <div class="panel-block" style="margin-bottom:16px">
      <div class="panel-block-header">
        <div>
          <span style="font-weight:600;color:var(--text)">Panel #${p.id}: ${escHtml(p.title)}</span>
          <span style="margin-left:12px;font-size:12px;color:var(--text3)">Channel: <code>${p.channel_id}</code></span>
          ${p.message_id
            ? `<span style="margin-left:8px;font-size:12px;color:#22c55e">âœ… Posted</span>`
            : `<span style="margin-left:8px;font-size:12px;color:#f59e0b">âš  Belum dikirim â€” jalankan <code>/roles post ${p.id}</code> di Discord</span>`}
        </div>
        <button class="btn-danger" style="padding:6px 12px;font-size:12px" onclick="deletePanel(${p.id})">ðŸ—‘ Hapus</button>
      </div>
      <div class="panel-block-body">
        ${p.groups.length === 0
          ? `<div style="color:var(--text3);font-size:13px;margin-bottom:10px">Belum ada grup. Tambahkan grup di bawah.</div>`
          : p.groups.map(g => `
          <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:12px;margin-bottom:12px">
            <div style="font-size:13px;font-weight:600;color:var(--text2);margin-bottom:8px">ðŸ“‹ ${escHtml(g.name)} <span style="font-size:11px;color:var(--text3);font-weight:400">(Group ID: ${g.id})</span></div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px">
              ${g.options.length === 0
                ? `<span style="color:var(--text3);font-size:12px">Belum ada role</span>`
                : g.options.map(o => `
                <span style="background:rgba(124,58,237,0.15);border:1px solid rgba(124,58,237,0.25);border-radius:8px;padding:4px 10px;font-size:12px;color:#c4b5fd;display:flex;align-items:center;gap:6px">
                  ${o.emoji || 'ðŸŽ­'} <code style="color:#e9d5ff">${o.role_id}</code>${o.description ? ` â€” ${escHtml(o.description)}` : ''}
                </span>
              `).join('')}
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
              <input type="text" id="role-id-${g.id}" placeholder="Role ID" style="max-width:160px;font-size:13px"/>
              <input type="text" id="role-emoji-${g.id}" placeholder="Emoji (opsional)" style="max-width:120px;font-size:13px"/>
              <input type="text" id="role-desc-${g.id}" placeholder="Deskripsi (opsional)" style="max-width:180px;font-size:13px"/>
              <button class="btn-sm" onclick="addRoleToGroup(${g.id})">âž• Tambah Role</button>
            </div>
          </div>
        `).join('')}
        <div style="display:flex;gap:10px;margin-top:10px;flex-wrap:wrap">
          <input type="text" id="ng-name-${p.id}" placeholder="Nama grup baru..." style="max-width:200px"/>
          <button class="btn-sm" onclick="addGroup(${p.id})">âž• Tambah Grup</button>
        </div>
      </div>
    </div>
  `).join('');
}

async function addRoleToGroup(groupId) {
  const roleIdEl = document.getElementById(`role-id-${groupId}`);
  const emojiEl  = document.getElementById(`role-emoji-${groupId}`);
  const descEl   = document.getElementById(`role-desc-${groupId}`);
  const roleId   = roleIdEl.value.trim();
  if (!roleId) return showAlert('roles-alert', 'âŒ Role ID harus diisi!', 'error');
  const res = await apiFetch('/api/roles/role/add', {
    method: 'POST',
    body: JSON.stringify({
      group_id:    groupId,
      role_id:     roleId,
      emoji:       emojiEl.value.trim() || null,
      description: descEl.value.trim()  || null,
    })
  });
  if (res.ok) {
    showAlert('roles-alert', `âœ… Role ID ${roleId} ditambahkan!`, 'success');
    roleIdEl.value = ''; emojiEl.value = ''; descEl.value = '';
    loadRoles();
  } else {
    showAlert('roles-alert', 'âŒ Gagal menambahkan role.', 'error');
  }
}

async function createPanel() {
  const gid   = document.getElementById('roles-guild').value.trim();
  const chid  = document.getElementById('r-chid').value.trim();
  const title = document.getElementById('r-title').value.trim() || 'ðŸŽ­ Pilih Role Kamu';
  const desc  = document.getElementById('r-desc').value.trim()  || 'Pilih role menggunakan dropdown.';
  if (!gid || !chid) return showAlert('roles-alert', 'âŒ Guild ID & Channel ID wajib diisi!', 'error');
  const res = await apiFetch('/api/roles/panel/create', {
    method: 'POST',
    body: JSON.stringify({ guild_id: gid, channel_id: chid, title, description: desc })
  });
  if (res.ok) {
    const d = await res.json();
    showAlert('roles-alert', `âœ… Panel #${d.panel_id} dibuat! Tambahkan grup & role di bawah, lalu jalankan /roles post ${d.panel_id} di Discord.`, 'success');
    loadRoles();
  } else {
    showAlert('roles-alert', 'âŒ Gagal membuat panel.', 'error');
  }
}

async function deletePanel(panelId) {
  if (!confirm(`Hapus panel #${panelId}?`)) return;
  const res = await apiFetch(`/api/roles/panel/${panelId}`, { method: 'DELETE' });
  if (res.ok) { showAlert('roles-alert', `âœ… Panel #${panelId} dihapus.`, 'success'); loadRoles(); }
  else showAlert('roles-alert', 'âŒ Gagal menghapus panel.', 'error');
}

async function addGroup(panelId) {
  const nameEl = document.getElementById(`ng-name-${panelId}`);
  const name   = nameEl.value.trim();
  if (!name) return;
  const res = await apiFetch('/api/roles/group/add', {
    method: 'POST', body: JSON.stringify({ panel_id: panelId, name })
  });
  if (res.ok) { showAlert('roles-alert', `âœ… Grup "${name}" ditambahkan! Sekarang tambahkan Role ID ke grup ini.`, 'success'); loadRoles(); }
  else showAlert('roles-alert', 'âŒ Gagal.', 'error');
}

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// AUTO VOICE
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function loadAutoVoice() {
  const gid = document.getElementById('av-guild').value.trim();
  if (!gid) return showAlert('av-alert', 'âŒ Masukkan Guild ID!', 'error');
  saveGuildId('autovoice', gid);
  const res  = await apiFetch(`/api/autovoice/${gid}`);
  const data = await res.json();
  document.getElementById('av-chid').value = data.autovoice_channel_id || '';
  showAlert('av-alert', 'âœ… Config dimuat!', 'success');
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
      <td>${escHtml(v.name || 'â€”')}</td>
      <td><code>${v.owner_id}</code></td>
      <td>${v.user_limit ? v.user_limit : '<span class="text-muted">âˆž</span>'}</td>
      <td>${v.is_locked
        ? '<span style="color:#ef4444">ðŸ”’ Terkunci</span>'
        : '<span style="color:#22c55e">ðŸ”“ Terbuka</span>'}</td>
      <td style="color:var(--text3);font-size:12px">${v.created_at ? v.created_at.split('.')[0] : 'â€”'}</td>
    </tr>
  `).join('');
}

async function saveAutoVoice() {
  const gid  = document.getElementById('av-guild').value.trim();
  const chid = document.getElementById('av-chid').value.trim();
  if (!gid) return showAlert('av-alert', 'âŒ Masukkan Guild ID!', 'error');
  const res = await apiFetch('/api/autovoice/update', {
    method: 'POST', body: JSON.stringify({ guild_id: gid, channel_id: chid || null })
  });
  if (res.ok) showAlert('av-alert', 'âœ… Config disimpan!', 'success');
  else        showAlert('av-alert', 'âŒ Gagal.', 'error');
}

async function disableAutoVoice() {
  const gid = document.getElementById('av-guild').value.trim();
  if (!gid) return showAlert('av-alert', 'âŒ Masukkan Guild ID!', 'error');
  await apiFetch('/api/autovoice/update', {
    method: 'POST', body: JSON.stringify({ guild_id: gid, channel_id: null })
  });
  document.getElementById('av-chid').value = '';
  showAlert('av-alert', 'âœ… Auto Voice dinonaktifkan.', 'success');
}


// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// STATUS CHANNEL
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function loadStatus() {
  const gid = document.getElementById('sc-guild').value.trim();
  if (!gid) return showAlert('sc-alert', 'âŒ Masukkan Guild ID!', 'error');
  saveGuildId('status', gid);
  const res  = await apiFetch(`/api/status/${gid}`);
  const data = await res.json();
  document.getElementById('sc-mch').value = data.status_member_channel_id || '';
  document.getElementById('sc-och').value = data.status_online_channel_id || '';
  showAlert('sc-alert', 'âœ… Config dimuat!', 'success');
}

async function saveStatus() {
  const gid = document.getElementById('sc-guild').value.trim();
  if (!gid) return showAlert('sc-alert', 'âŒ Masukkan Guild ID!', 'error');
  const res = await apiFetch('/api/status/update', {
    method: 'POST',
    body: JSON.stringify({
      guild_id:                 gid,
      status_member_channel_id: document.getElementById('sc-mch').value.trim() || null,
      status_online_channel_id: document.getElementById('sc-och').value.trim() || null,
    })
  });
  if (res.ok) showAlert('sc-alert', 'âœ… Config disimpan!', 'success');
  else        showAlert('sc-alert', 'âŒ Gagal.', 'error');
}

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// STREAMING
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async function loadStreaming() {
  const gid = document.getElementById('st-guild').value.trim();
  if (!gid) return showAlert('st-alert', 'âŒ Masukkan Guild ID!', 'error');
  saveGuildId('streaming', gid);
  const res  = await apiFetch(`/api/streaming/${gid}`);
  const data = await res.json();
  document.getElementById('st-chid').value = data.streaming_channel_id         || '';
  document.getElementById('st-rid').value  = data.streaming_role_id             || '';
  document.getElementById('st-orid').value = data.streaming_on_stream_role_id  || '';
  showAlert('st-alert', 'âœ… Config dimuat!', 'success');
}

async function saveStreaming() {
  const gid = document.getElementById('st-guild').value.trim();
  if (!gid) return showAlert('st-alert', 'âŒ Masukkan Guild ID!', 'error');
  const res = await apiFetch('/api/streaming/update', {
    method: 'POST',
    body: JSON.stringify({
      guild_id:          gid,
      channel_id:        document.getElementById('st-chid').value.trim() || null,
      role_id:           document.getElementById('st-rid').value.trim()  || null,
      on_stream_role_id: document.getElementById('st-orid').value.trim() || null,
    })
  });
  if (res.ok) showAlert('st-alert', 'âœ… Config disimpan!', 'success');
  else        showAlert('st-alert', 'âŒ Gagal.', 'error');
}

async function disableStreaming() {
  const gid = document.getElementById('st-guild').value.trim();
  if (!gid) return showAlert('st-alert', 'âŒ Masukkan Guild ID!', 'error');
  await apiFetch('/api/streaming/update', {
    method: 'POST', body: JSON.stringify({ guild_id: gid, channel_id: null, role_id: null, on_stream_role_id: null })
  });
  document.getElementById('st-chid').value = '';
  document.getElementById('st-rid').value  = '';
  document.getElementById('st-orid').value = '';
  showAlert('st-alert', 'âœ… Streaming notif dinonaktifkan.', 'success');
}

// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// SYSTEM CONTROL
// â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function _setSysStatus(running, text) {
  const dot = document.getElementById('sys-status-dot');
  const txt = document.getElementById('sys-status-text');
  if (dot) dot.style.background = running ? '#22c55e' : '#ef4444';
  if (txt) txt.textContent = text;
}

async function checkBotStatus() {
  _setSysStatus(false, 'â³ Mengecek status...');
  try {
    const res  = await apiFetch('/api/system/status');
    if (!res.ok) { _setSysStatus(false, `âŒ API error (${res.status})`); return; }
    const data = await res.json();
    if (data.running) {
      _setSysStatus(true, `âœ… Bot berjalan â€” PID: ${data.pids.join(', ')}`);
    } else {
      _setSysStatus(false, 'âŒ Bot tidak berjalan');
    }
  } catch (e) {
    _setSysStatus(false, `âš ï¸ Tidak bisa cek status: ${e.message}`);
    console.error('checkBotStatus error:', e);
  }
}

async function restartBot() {
  const btn = document.getElementById('restartBtn');
  if (!btn) { console.error('restartBtn not found'); return; }
  btn.disabled = true;
  btn.textContent = 'â³ Merestart...';
  _setSysStatus(false, 'â³ Sedang merestart bot...');
  showAlert('sys-alert', 'â³ Memproses restart bot, mohon tunggu...', 'success');
  try {
    const res  = await apiFetch('/api/system/restart', { method: 'POST' });
    if (!res.ok) {
      showAlert('sys-alert', `âŒ API error ${res.status}`, 'error');
      _setSysStatus(false, `âŒ API error ${res.status}`);
      btn.disabled = false; btn.textContent = 'ðŸ”„ Restart Bot';
      return;
    }
    const data = await res.json();
    if (data.status === 'ok') {
      showAlert('sys-alert', `âœ… ${data.message}`, 'success');
      _setSysStatus(true, `âœ… Restart berhasil via ${data.method}`);
      setTimeout(checkBotStatus, 5000);
    } else {
      showAlert('sys-alert', `âŒ ${data.message}`, 'error');
      _setSysStatus(false, `âŒ Restart gagal`);
    }
  } catch (e) {
    showAlert('sys-alert', `âŒ Error: ${e.message}`, 'error');
    _setSysStatus(false, `âŒ Error: ${e.message}`);
    console.error('restartBot error:', e);
  }
  setTimeout(() => { btn.disabled = false; btn.textContent = 'ðŸ”„ Restart Bot'; }, 6000);
}

async function loadBotLogs() {
  const box = document.getElementById('sys-log-box');
  if (!box) { console.error('sys-log-box not found'); return; }
  box.style.display = 'block';
  box.innerHTML = '<span style="color:#6b7280">â³ Memuat log...</span>';
  try {
    const res  = await apiFetch('/api/system/logs?lines=80');
    if (!res.ok) { box.innerHTML = `<span style="color:#ef4444">API error: ${res.status}</span>`; return; }
    const data = await res.json();
    if (data.error) { box.innerHTML = `<span style="color:#ef4444">Error: ${escHtml(data.error)}</span>`; return; }
    if (!data.lines || !data.lines.length) {
      box.innerHTML = `<span style="color:#6b7280">Log kosong. Path: ${escHtml(data.log_path || data.message || 'â€”')}</span>`;
      return;
    }
    box.innerHTML = data.lines.map(l => {
      let color = '#a3a3a3';
      if (l.match(/ERROR|âŒ|Failed|Traceback/i)) color = '#ef4444';
      else if (l.match(/âœ…|Synced|ready|on_ready/i)) color = '#22c55e';
      else if (l.match(/âš |WARNING|warn/i)) color = '#f59e0b';
      else if (l.match(/Loaded:|INFO/i)) color = '#60a5fa';
      return `<div style="color:${color};white-space:pre-wrap">${escHtml(l)}</div>`;
    }).join('');
    box.scrollTop = box.scrollHeight;
  } catch (e) {
    box.innerHTML = `<span style="color:#ef4444">Error: ${escHtml(e.message)}</span>`;
    console.error('loadBotLogs error:', e);
  }
}

// â”€â”€ Utils â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// â”€â”€ Streamer Tracker â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

let _streamerData     = [];
let _streamerPlatform = 'youtube';
let _editStreamerId   = null;

function switchStreamerTab(platform) {
  _streamerPlatform = platform;
  document.querySelectorAll('.streamer-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + platform).classList.add('active');
  renderStreamerTable();
}

async function loadStreamers() {
  const guildId = document.getElementById('st-guild').value.trim();
  if (!guildId) return alert('Masukkan Guild ID dulu!');
  const tbody = document.getElementById('streamer-tbody');
  tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Loading...</td></tr>';
  try {
    const res = await apiFetch('/api/streamers/' + guildId);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    _streamerData = data.streamers || [];
    updateStreamerBadges();
    renderStreamerTable();
  } catch(e) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center" style="color:#ef4444">Error: ' + escHtml(e.message) + '</td></tr>';
  }
}

function updateStreamerBadges() {
  const yt = _streamerData.filter(s => s.platform === 'youtube').length;
  const tt = _streamerData.filter(s => s.platform === 'tiktok').length;
  document.getElementById('yt-count').textContent = yt + '/30';
  document.getElementById('tt-count').textContent = tt + '/10';
}

function renderStreamerTable() {
  const search = (document.getElementById('streamer-search') ? document.getElementById('streamer-search').value : '').toLowerCase();
  const rows = _streamerData.filter(function(s) {
    return s.platform === _streamerPlatform &&
      (!search || (s.channel_name||'').toLowerCase().includes(search) || (s.channel_url||'').toLowerCase().includes(search));
  });
  const empty = document.getElementById('streamer-empty');
  const wrap  = document.getElementById('streamer-table-wrap');
  const tbody = document.getElementById('streamer-tbody');
  if (!tbody) return;
  if (rows.length === 0) {
    if (empty) empty.style.display = 'block';
    if (wrap)  wrap.style.display  = 'none';
    return;
  }
  if (empty) empty.style.display = 'none';
  if (wrap)  wrap.style.display  = '';
  const platLabel = _streamerPlatform === 'youtube'
    ? '<span style="color:#FF0000">&#9654; YouTube</span>'
    : '<span style="color:#fe2c55">&#127925; TikTok</span>';
  tbody.innerHTML = rows.map(function(s) {
    return '<tr>' +
      '<td>' + platLabel + '</td>' +
      '<td><a href="' + escHtml(s.channel_url) + '" target="_blank" style="color:var(--accent)">' + escHtml(s.channel_name || s.channel_url) + '</a></td>' +
      '<td><code>' + (s.discord_channel_id || '&#8212;') + '</code></td>' +
      '<td><code>' + (s.ping_role_id || '&#8212;') + '</code></td>' +
      '<td>' +
        '<label class="toggle-switch">' +
          '<input type="checkbox" ' + (s.status === 'running' ? 'checked' : '') + ' onchange="toggleStreamerStatus(' + s.id + ', this.checked)"/>' +
          '<span class="toggle-track"></span>' +
        '</label>' +
        '<span style="font-size:11px;color:' + (s.status==='running'?'#22c55e':'#6b7280') + ';margin-left:4px">' + (s.status === 'running' ? 'Running' : 'Paused') + '</span>' +
      '</td>' +
      '<td>' +
        '<button class="btn-sm" onclick="openEditStreamerModal(' + s.id + ')" title="Edit">&#9998;</button> ' +
        '<button class="btn-sm" style="color:#ef4444" onclick="deleteStreamer(' + s.id + ')" title="Hapus">&#128465;</button>' +
      '</td>' +
    '</tr>';
  }).join('');
}

function filterStreamerList() { renderStreamerTable(); }

function openAddStreamerModal() {
  _editStreamerId = null;
  document.getElementById('streamerModalTitle').textContent = 'Add Channel';
  document.getElementById('sm-save-btn').textContent = '+ Add Channel';
  document.getElementById('sm-url').value = '';
  document.getElementById('sm-url').disabled = false;
  document.getElementById('sm-platform').value = _streamerPlatform;
  document.getElementById('sm-platform').disabled = false;
  document.getElementById('sm-discord-ch').value = '';
  document.getElementById('sm-ping-role').value = '';
  document.getElementById('sm-status').value = 'running';
  document.getElementById('sm-content-type').value = 'all';
  document.getElementById('sm-video-msg').value = '{channel} just posted a new video!';
  document.getElementById('sm-live-msg').value = '{channel} is live!';
  document.getElementById('streamerModal').style.display = 'flex';
}

function openEditStreamerModal(id) {
  var s = _streamerData.find(function(r){ return r.id === id; });
  if (!s) return;
  _editStreamerId = id;
  document.getElementById('streamerModalTitle').textContent = 'Edit Channel';
  document.getElementById('sm-save-btn').textContent = 'Simpan';
  document.getElementById('sm-url').value = s.channel_url || '';
  document.getElementById('sm-url').disabled = true;
  document.getElementById('sm-platform').value = s.platform;
  document.getElementById('sm-platform').disabled = true;
  document.getElementById('sm-discord-ch').value = s.discord_channel_id || '';
  document.getElementById('sm-ping-role').value = s.ping_role_id || '';
  document.getElementById('sm-status').value = s.status || 'running';
  document.getElementById('sm-content-type').value = s.content_type || 'all';
  document.getElementById('sm-video-msg').value = s.video_message || '{channel} just posted a new video!';
  document.getElementById('sm-live-msg').value = s.live_message || '{channel} is live!';
  document.getElementById('streamerModal').style.display = 'flex';
}

function closeStreamerModal() {
  document.getElementById('streamerModal').style.display = 'none';
  _editStreamerId = null;
}

async function saveStreamerChannel() {
  const guildId = document.getElementById('st-guild').value.trim();
  if (!guildId) return alert('Load guild dulu!');
  const btn = document.getElementById('sm-save-btn');
  btn.disabled = true;
  btn.textContent = _editStreamerId ? 'Menyimpan...' : 'Menambahkan...';
  const payload = {
    platform:           document.getElementById('sm-platform').value,
    channel_url:        document.getElementById('sm-url').value.trim(),
    discord_channel_id: document.getElementById('sm-discord-ch').value.trim(),
    ping_role_id:       document.getElementById('sm-ping-role').value.trim() || null,
    status:             document.getElementById('sm-status').value,
    content_type:       document.getElementById('sm-content-type').value,
    video_message:      document.getElementById('sm-video-msg').value.trim(),
    live_message:       document.getElementById('sm-live-msg').value.trim(),
  };
  try {
    var res;
    if (_editStreamerId) {
      res = await apiFetch('/api/streamers/' + guildId + '/' + _editStreamerId, { method: 'PATCH', body: JSON.stringify(payload) });
    } else {
      if (!payload.channel_url) throw new Error('Channel URL wajib diisi!');
      res = await apiFetch('/api/streamers/' + guildId, { method: 'POST', body: JSON.stringify(payload) });
    }
    if (!res.ok) {
      const err = await res.json().catch(function(){ return {detail: 'Unknown error'}; });
      throw new Error(err.detail || JSON.stringify(err));
    }
    closeStreamerModal();
    await loadStreamers();
  } catch(e) {
    alert('Error: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = _editStreamerId ? 'Simpan' : '+ Add Channel';
  }
}

async function toggleStreamerStatus(id, isRunning) {
  const guildId = document.getElementById('st-guild').value.trim();
  if (!guildId) return;
  await apiFetch('/api/streamers/' + guildId + '/' + id, {
    method: 'PATCH',
    body: JSON.stringify({ status: isRunning ? 'running' : 'paused' })
  });
  var row = _streamerData.find(function(s){ return s.id === id; });
  if (row) row.status = isRunning ? 'running' : 'paused';
  renderStreamerTable();
}

async function deleteStreamer(id) {
  if (!confirm('Hapus tracked channel ini?')) return;
  const guildId = document.getElementById('st-guild').value.trim();
  if (!guildId) return;
  try {
    const res = await apiFetch('/api/streamers/' + guildId + '/' + id, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    _streamerData = _streamerData.filter(function(s){ return s.id !== id; });
    updateStreamerBadges();
    renderStreamerTable();
  } catch(e) { alert('Gagal hapus: ' + e.message); }
}

// Auto-detect platform dari URL
(function() {
  function bindUrlDetect() {
    var urlInput   = document.getElementById('sm-url');
    var platSelect = document.getElementById('sm-platform');
    if (urlInput && platSelect) {
      urlInput.addEventListener('input', function() {
        var url = urlInput.value.toLowerCase();
        if (url.includes('tiktok.com'))                       platSelect.value = 'tiktok';
        else if (url.includes('youtube') || url.includes('youtu.be')) platSelect.value = 'youtube';
      });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindUrlDetect);
  else bindUrlDetect();
})();

// __ Daily Restart Schedule ___________________________________________________

let _schedSaving = false;

async function loadSchedule() {
  try {
    const res = await apiFetch('/api/schedule');
    if (!res.ok) return;
    const data = await res.json();
    const enabledEl = document.getElementById('sched-enabled');
    const timeEl    = document.getElementById('sched-time');
    if (!enabledEl) return;
    enabledEl.checked = !!data.daily_restart_enabled;
    timeEl.value      = data.daily_restart_time || '04:00';
    _updateSchedUI(data.daily_restart_enabled, data.daily_restart_time);
  } catch(e) { console.error('loadSchedule:', e); }
}

function _updateSchedUI(enabled, time) {
  const nextEl   = document.getElementById('sched-next');
  const statusEl = document.getElementById('sched-status');
  if (!nextEl) return;
  if (enabled) {
    nextEl.textContent = 'Aktif — restart pukul ' + time + ' WIB';
    nextEl.style.color = '#22c55e';
    if (statusEl) { statusEl.textContent = 'Auto restart aktif setiap pukul ' + time + ' WIB'; statusEl.style.color = '#22c55e'; }
  } else {
    nextEl.textContent = 'Tidak aktif';
    nextEl.style.color = 'var(--text3)';
    if (statusEl) statusEl.textContent = '';
  }
}

async function saveSchedule() {
  if (_schedSaving) return;
  const enabledEl = document.getElementById('sched-enabled');
  const timeEl    = document.getElementById('sched-time');
  const alertEl   = document.getElementById('sched-alert');
  if (!enabledEl || !timeEl) return;
  _schedSaving = true;
  try {
    const payload = { daily_restart_enabled: enabledEl.checked, daily_restart_time: timeEl.value || '04:00' };
    const res  = await apiFetch('/api/schedule', { method: 'POST', body: JSON.stringify(payload) });
    const data = await res.json();
    if (data.ok) {
      _updateSchedUI(payload.daily_restart_enabled, payload.daily_restart_time);
      if (alertEl) {
        alertEl.textContent = enabledEl.checked ? 'Jadwal restart disimpan: ' + payload.daily_restart_time + ' WIB' : 'Auto restart dimatikan';
        alertEl.style.display = 'block';
        setTimeout(function(){ alertEl.style.display='none'; }, 3000);
      }
    } else { alert('Gagal: ' + (data.error||'Unknown')); }
  } catch(e) { alert('Error: ' + e.message); }
  finally { _schedSaving = false; }
}
