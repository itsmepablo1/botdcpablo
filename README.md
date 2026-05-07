# 🤖 Discord Bot Full Featured

Bot Discord lengkap dengan Web Panel VPS dan kontrol via Slash Command.

---

## ✨ Fitur

| Fitur | Slash Command | Panel |
|-------|--------------|-------|
| 👋 Welcome Message + Custom Background | `/welcome channel`, `/welcome background` | ✅ |
| 👋 Leave Message + Custom Background | `/leave channel`, `/leave background` | ✅ |
| 🎵 Music Realtime (no delay) | `/play`, `/skip`, `/stop`, `/queue`, `/pause`, `/resume`, `/volume` | — |
| 🎭 Role Selector (Multiple Dropdown) | `/roles create`, `/roles add`, `/roles post` | ✅ |
| 🔊 Auto Voice Channel | `/autovoice setup`, `/vc name`, `/vc limit`, `/vc lock` | ✅ |
| 📊 Status Channel (Total Member, Online) | `/status setup`, `/status refresh` | ✅ |
| 🔴 Streaming Notif (TikTok/YouTube/Twitch) | `/streaming setup`, `/streaming test` | ✅ |
| 🌐 Web Panel VPS | — | ✅ |

---

## 🚀 Cara Deploy ke VPS (Ubuntu/Debian)

### 1. Install Dependencies

```bash
# Update & install system packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip ffmpeg git

# Verify FFmpeg
ffmpeg -version
```

### 2. Clone / Upload Project

```bash
# Upload ke VPS (dari Windows pakai WinSCP atau rsync)
# Atau clone dari git:
git clone <your-repo-url> /home/botdc
cd /home/botdc
```

### 3. Buat Virtual Environment & Install

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Konfigurasi .env

```bash
cp .env.example .env
nano .env
```

Isi semua nilai:

```env
DISCORD_TOKEN=your_bot_token_here
PANEL_SECRET_KEY=random_string_yang_panjang
PANEL_USERNAME=admin
PANEL_PASSWORD=password_kuat_kamu
PANEL_HOST=0.0.0.0
PANEL_PORT=8080
DATABASE_PATH=./data/bot.db
FFMPEG_PATH=ffmpeg
YOUTUBE_API_KEY=           # opsional
```

### 5. Cara Dapat Bot Token Discord

1. Buka [Discord Developer Portal](https://discord.com/developers/applications)
2. Klik **New Application** → beri nama
3. Menu **Bot** → **Add Bot** → copy **Token**
4. Di menu **Privileged Gateway Intents**, aktifkan:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
   - ✅ **Presence Intent**
5. Menu **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Administrator`
6. Copy URL → buka di browser → undang bot ke server

### 6. Jalankan dengan systemd (Auto-Start)

#### Bot Service

```bash
sudo nano /etc/systemd/system/discordbot.service
```

```ini
[Unit]
Description=Discord Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/botdc
ExecStart=/home/botdc/venv/bin/python -m bot.main
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

#### Panel Service

```bash
sudo nano /etc/systemd/system/botpanel.service
```

```ini
[Unit]
Description=Discord Bot Web Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/botdc
ExecStart=/home/botdc/venv/bin/uvicorn panel.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Aktifkan & jalankan
sudo systemctl daemon-reload
sudo systemctl enable discordbot botpanel
sudo systemctl start discordbot botpanel

# Cek status
sudo systemctl status discordbot
sudo systemctl status botpanel
```

### 7. Buka Web Panel

Buka browser: `http://YOUR_VPS_IP:8080`

---

## 📋 Semua Slash Commands

### 👋 Welcome / Leave
| Command | Deskripsi |
|---------|-----------|
| `/welcome channel [channel_id]` | Set channel welcome (gunakan Channel ID) |
| `/welcome message [text]` | Set teks welcome. Variabel: `{member}`, `{server}`, `{count}` |
| `/welcome background [file]` | Upload gambar background card |
| `/welcome bgremove` | Reset background ke default |
| `/welcome test` | Preview welcome card |
| `/leave channel [channel_id]` | Set channel leave |
| `/leave message [text]` | Set teks leave |
| `/leave background [file]` | Upload background leave card |

### 🎵 Music
| Command | Deskripsi |
|---------|-----------|
| `/play [query/URL]` | Putar lagu dari YouTube |
| `/skip` | Skip lagu |
| `/stop` | Stop dan keluar dari VC |
| `/pause` | Pause |
| `/resume` | Lanjutkan |
| `/volume [0-100]` | Atur volume |
| `/queue` | Lihat antrian |
| `/nowplaying` | Lagu sekarang |

### 🎭 Role Selector
| Command | Deskripsi |
|---------|-----------|
| `/roles create [channel_id]` | Buat panel role baru |
| `/roles addgroup [panel_id] [nama]` | Tambah kategori grup |
| `/roles add [group_id] [role_id]` | Tambah role ke grup (gunakan Role ID) |
| `/roles post [panel_id]` | Kirim panel ke channel |
| `/roles list` | Lihat semua panel |
| `/roles delete [panel_id]` | Hapus panel |

### 🔊 Auto Voice
| Command | Deskripsi |
|---------|-----------|
| `/autovoice setup [channel_id]` | Set trigger channel (Voice Channel ID) |
| `/autovoice disable` | Matikan auto VC |
| `/vc name [nama]` | Ganti nama VC kamu |
| `/vc limit [0-99]` | Set batas member |
| `/vc lock` | Kunci VC |
| `/vc unlock` | Buka VC |
| `/vc kick [user_id]` | Kick dari VC |
| `/vc claim` | Ambil ownership VC |
| `/vc info` | Info VC |

### 📊 Status Channel
| Command | Deskripsi |
|---------|-----------|
| `/status setup` | Buat kategori & channel otomatis |
| `/status setmember [channel_id]` | Set channel member counter |
| `/status setonline [channel_id]` | Set channel online counter |
| `/status refresh` | Force update sekarang |
| `/status disable` | Hapus status channel |

### 🔴 Streaming
| Command | Deskripsi |
|---------|-----------|
| `/streaming setup [channel_id] [role_id]` | Setup notif (Channel ID + Role ID) |
| `/streaming info` | Lihat config |
| `/streaming test` | Test notif |
| `/streaming disable` | Matikan |

---

## ❓ FAQ

**Q: Bot tidak merespons slash command?**  
A: Tunggu 1-2 menit setelah bot online, slash command butuh waktu sync.

**Q: Music tidak berbunyi?**  
A: Pastikan FFmpeg terinstall (`ffmpeg -version`), dan bot punya permission di VC.

**Q: Welcome card tidak muncul?**  
A: Pastikan bot punya permission `Send Messages` dan `Attach Files` di channel welcome.

**Q: Auto VC tidak terbuat?**  
A: Bot memerlukan permission `Manage Channels` di server.

---

## 📁 Struktur Folder

```
bot dc final/
├── bot/           # Source code bot Discord
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── cogs/      # Semua fitur sebagai cog
│   └── utils/     # Card generator & stream checker
├── panel/         # Web Panel VPS
│   ├── main.py
│   ├── routers/
│   └── static/    # HTML, CSS, JS
├── assets/        # Background images
├── data/          # SQLite database (auto-created)
├── .env           # Konfigurasi (buat dari .env.example)
└── requirements.txt
```
