# Dasbor Penambang Bitcoin Rumahan

Dasbor pemantauan dan kontrol untuk perangkat penambang Bitcoin rumahan Anda — **berjalan 100% lokal**, tanpa layanan cloud, tanpa telemetri. Backend Python (FastAPI), frontend React + TypeScript + Tailwind. Dijalankan di komputer sendiri atau Raspberry Pi, diakses lewat browser di ponsel atau laptop mana pun di jaringan yang sama.

## Fitur

- **Deteksi otomatis** perangkat penambang di jaringan lokal Anda (dan opsi tambah manual via IP).
- **Ringkasan per perangkat**: hash rate, suhu, kecepatan kipas, daya, efisiensi (J/TH), shares, uptime.
- **Halaman detail** per perangkat dengan grafik riwayat (1 jam / 24 jam / 7 hari / 30 hari).
- **Kompatibel dengan**: Bitaxe, NerdQaxe(+), Avalon Nano (Canaan), Braiins OS+, dan LuxOS (khusus mode pantau/*read-only*).
- **Kontrol sederhana** bila didukung perangkat: mode kipas (otomatis/manual), target suhu otomatis, jeda/lanjut, restart.
- **Lapisan keamanan suhu independen**: bila suhu perangkat apa pun melewati ambang aman selama beberapa siklus polling berturut-turut, dasbor mencoba menjeda penambangan secara otomatis dan mengirim notifikasi — terlepas dari apakah perangkat itu punya kontrol kipas atau tidak.
- **Notifikasi**: rekor *best share* baru dan (untuk perangkat AxeOS/Bitaxe-NerdQaxe) blok ditemukan.
- **Tanpa cloud, tanpa telemetri**: semua data tersimpan di berkas SQLite lokal; semua koneksi keluar dibatasi ke alamat IP privat di jaringan Anda sendiri.

## Persyaratan

- **Python 3.10+** (untuk menjalankan backend — ini satu-satunya yang wajib ada di Raspberry Pi/PC Anda).
- **Node.js 18+** — **hanya diperlukan jika** Anda ingin mengubah kode frontend dan membangunnya ulang. Hasil build (`frontend/dist/`) sudah disertakan dan siap pakai, jadi untuk sekadar menjalankan dasbor, Node.js **tidak diperlukan**.

## Menjalankan — cara tercepat

### Linux / macOS / Raspberry Pi

```bash
cd backend
./run.sh
```

Skrip ini otomatis membuat virtual environment Python, memasang dependensi, lalu menjalankan server. Setelah muncul tulisan `Uvicorn running on http://0.0.0.0:8420`, buka `http://<ip-komputer-ini>:8420` dari browser ponsel/laptop mana pun di jaringan yang sama (atau `http://localhost:8420` dari komputer itu sendiri).

### Windows

```
cd backend
run.bat
```

### Lewat Docker (opsional)

```bash
docker compose up -d --build
```

> Di Linux/Raspberry Pi, `docker-compose.yml` memakai `network_mode: host` agar fitur pindai jaringan bisa melihat LAN Anda secara langsung. Di Docker Desktop (Mac/Windows) mode ini tidak tersedia — lihat komentar di dalam berkas tersebut untuk alternatifnya (tambah perangkat manual via IP tetap berfungsi).

### Setup awal

Saat pertama kali membuka dasbor, Anda akan diminta membuat **satu akun operator** (username + password, minimal 8 karakter). Akun ini tersimpan lokal di perangkat yang menjalankan dasbor dan hanya dipakai untuk mengamankan akses — tidak terhubung ke layanan apa pun di luar.

### Menjalankan otomatis saat boot (Raspberry Pi)

Lihat `backend/miner-dashboard.service` — salin ke `/etc/systemd/system/`, sesuaikan path-nya, lalu `sudo systemctl enable --now miner-dashboard`. Detail lengkap ada sebagai komentar di dalam berkas tersebut.

## Kompatibilitas perangkat & kontrol yang tersedia

| Perangkat | Protokol | Pemantauan | Kontrol tersedia |
|---|---|---|---|
| Bitaxe | HTTP JSON (AxeOS) | Lengkap | Mode kipas, target suhu otomatis, jeda/lanjut, restart, identify |
| NerdQaxe / NerdQaxe+ | HTTP JSON (AxeOS, API sama dgn Bitaxe) | Lengkap | Sama seperti Bitaxe |
| Avalon Nano | TCP/JSON (keluarga cgminer) | Lengkap | Restart saja — firmware resminya tidak mengekspos kontrol kipas via API |
| Braiins OS+ | REST API resmi (perlu versi **25.07+**) | Lengkap | Mode kipas, target suhu otomatis, jeda/lanjut, restart |
| LuxOS | TCP/JSON (keluarga cgminer) | Lengkap | **Tidak ada — selalu read-only**, sesuai permintaan; dasbor tidak pernah mengirim perintah pengaturan ke rig LuxOS dalam bentuk apa pun |

Catatan jujur soal variasi firmware: pemetaan nama field untuk `bestDiff`/suhu/kipas diambil langsung dari dokumentasi resmi masing-masing vendor, namun firmware ASIC sering memiliki variasi kecil antar versi. Setiap halaman detail perangkat punya tombol **"Tampilkan data mentah dari perangkat"** — kalau ada angka yang terlihat aneh di perangkat Anda, cek di situ untuk melihat field asli apa saja yang dikirim perangkat, lalu bandingkan dengan `backend/app/adapters/<nama_perangkat>.py` bila ingin menyesuaikan sendiri.

### Soal notifikasi "blok ditemukan"

Untuk keluarga Bitaxe/NerdQaxe (AxeOS), firmware-nya sendiri sudah melacak jumlah blok yang ditemukan (ia tahu *network difficulty* dari job stratum), jadi dasbor tinggal membaca angka itu — **tidak ada panggilan keluar ke internet sama sekali** untuk ini. Untuk perangkat lain, sinyal setara belum tersedia dari API-nya, sehingga notifikasi ini belum akan muncul untuk Avalon Nano/Braiins/LuxOS. Kami sengaja **tidak** menambahkan panggilan ke *block explorer* pihak ketiga untuk menutupi ini secara diam-diam, karena itu akan melanggar prinsip "tanpa layanan cloud" yang Anda minta.

### Soal notifikasi saat browser ditutup

Notifikasi (toast di dalam aplikasi + notifikasi native browser) bekerja selama tab dasbor masih terbuka, walau di-*background*-kan (cocok untuk tablet/monitor yang selalu menyala). Notifikasi push yang tetap muncul saat browser **benar-benar ditutup** secara teknis memerlukan relai cloud milik penyedia browser (Google/Mozilla/Apple) — ini sengaja tidak diimplementasikan agar konsisten dengan prinsip "tanpa cloud".

## Keamanan

Ini adalah ringkasan langkah-langkah yang diambil, bukan klaim bahwa perangkat lunak ini mustahil diretas — tidak ada yang bisa menjamin itu selamanya, terutama seiring ditemukannya kerentanan baru di masa depan pada dependensi apa pun. Yang bisa kami pastikan adalah kelas-kelas kerentanan berikut sudah ditangani secara spesifik dan **diuji langsung** (bukan sekadar ditulis di kode):

- **SQL Injection** — seluruh query memakai parameter binding (`?`), tidak ada satu pun string SQL yang dirakit dari input pengguna.
- **RCE** — tidak ada `eval`/`exec`/`os.system` dengan input tak tepercaya di mana pun; jenis perangkat dipetakan lewat tabel tetap, bukan `import` dinamis dari string.
- **LFI / Path traversal** — rute penyajian frontend memvalidasi bahwa path hasil resolusi tetap berada di dalam folder yang dimaksud sebelum membuka berkas apa pun; sudah diuji dengan berbagai payload traversal.
- **SSRF** — setiap koneksi keluar (baik untuk pemindaian jaringan maupun ke perangkat yang sudah ditambahkan) divalidasi hanya boleh menuju alamat IP privat (RFC1918/link-local/loopback), dengan pengecualian tegas untuk endpoint metadata cloud (`169.254.169.254`).
- **XSS** — frontend React (auto-escape bawaan, tanpa `dangerouslySetInnerHTML` di mana pun) + header `Content-Security-Policy` yang ketat.
- **CSRF** — cookie sesi `SameSite=Strict` + token CSRF *double-submit* wajib pada setiap request yang mengubah data.
- **Bypass rate limit** — pembatas laju memakai alamat IP klien sesungguhnya dari koneksi TCP, bukan header yang bisa dipalsukan klien (`X-Forwarded-For` tidak dipercaya).
- **Bypass tamper / mass assignment** — semua skema Pydantic menolak field tak dikenal (`extra="forbid"`), semua nilai numerik kontrol (persen kipas, target suhu) divalidasi batasnya di server, dan status *read-only* LuxOS diperiksa ulang di server pada setiap permintaan kontrol — bukan cuma disembunyikan di UI.
- **Kata sandi** — di-hash dengan Argon2id (rekomendasi OWASP saat ini), perbandingan token sesi memakai *constant-time comparison*.
- **Sesi** — token ditandatangani HMAC-SHA256 buatan sendiri, sengaja **tidak** memakai pustaka JWT untuk menghindari seluruh kelas bug *algorithm-confusion* yang pernah jadi CVE berulang kali di berbagai pustaka JWT.
- **Dependensi** — versi dikunci; saat membangun proyek ini kami menjalankan `npm audit` dan langsung menaikkan versi `react-router-dom` setelah ditemukan 2 CVE moderat di dalamnya.

### Rekomendasi tambahan dari kami

- **Jangan** buka port dasbor ini ke internet publik (jangan port-forward di router Anda). Untuk akses dari luar rumah, gunakan VPN pribadi seperti Tailscale atau WireGuard, lalu akses dasbor seolah-olah Anda masih di jaringan rumah.
- Pertimbangkan mengaktifkan `MINER_DASH_ENABLE_TLS=true` di `.env` bila dasbor ini bisa diakses perangkat lain di Wi-Fi bersama (kos-kosan, kantor) — ini mengenkripsi lalu lintas login/sesi dengan sertifikat self-signed yang dibuat otomatis (browser akan menampilkan peringatan "not secure" karena sertifikatnya tidak diterbitkan otoritas publik; ini normal untuk perangkat pribadi di jaringan lokal).
- Jalankan `pip-audit` (backend) dan `npm audit` (frontend) sesekali untuk memeriksa kerentanan baru pada dependensi.

## Privasi

- Tidak ada panggilan ke layanan cloud atau analitik pihak ketiga di mana pun dalam kode ini.
- Font di-*self-host* (paket `@fontsource`), bukan dimuat dari Google Fonts — browser Anda tidak akan menghubungi server luar sama sekali saat membuka dasbor.
- Semua data historis, kredensial perangkat (mis. akun Braiins OS+ Anda), dan notifikasi tersimpan di satu berkas SQLite lokal (`~/.miner-dashboard/dashboard.sqlite3` secara default).

## Struktur proyek

```
miner-dashboard/
├── backend/            # FastAPI (Python)
│   ├── app/
│   │   ├── adapters/   # Satu adapter per jenis perangkat
│   │   ├── security/   # Auth, rate limit, header keamanan, anti-SSRF
│   │   ├── discovery/  # Pemindai jaringan lokal
│   │   ├── services/   # Poller, notifikasi, kontrol suhu aman
│   │   ├── db/         # SQLite + query
│   │   └── api/routes/ # Endpoint REST + WebSocket
│   ├── run.sh / run.bat
│   └── miner-dashboard.service
└── frontend/           # React + TypeScript + Tailwind (Vite)
    ├── src/
    │   ├── pages/       # Dashboard, DeviceDetail, Settings, Login
    │   ├── components/  # Kartu perangkat, grafik, kontrol, dll.
    │   └── hooks/       # React Query + WebSocket live-update
    └── dist/            # Hasil build siap pakai (sudah disertakan)
```

## Mengembangkan lebih lanjut

```bash
# Frontend, mode pengembangan dengan hot-reload (proxy otomatis ke backend di :8420)
cd frontend
npm install
npm run dev

# Setelah selesai mengubah, build ulang untuk dipakai backend:
npm run build
```

Menambah jenis adapter perangkat baru: buat berkas baru di `backend/app/adapters/`, ikuti pola di `adapters/base.py` (`MinerAdapter`), lalu daftarkan di `adapters/registry.py`.

## Troubleshooting singkat

- **Pindai jaringan tidak menemukan perangkat apa pun** — pastikan perangkat penambang dan komputer/Pi yang menjalankan dasbor berada di subnet yang sama; jika menjalankan lewat Docker di Mac/Windows, mode jaringan default Docker tidak bisa melihat LAN fisik Anda (tambahkan perangkat secara manual sebagai gantinya).
- **Suhu/kipas menampilkan "—"** — buka data mentah di halaman detail perangkat untuk melihat field apa yang sebenarnya dikirim firmware Anda; kemungkinan versi firmware Anda menamai field itu sedikit berbeda dari yang diasumsikan adapter.
- **Perangkat Braiins OS+ gagal terhubung** — pastikan firmware sudah versi 25.07 atau lebih baru (REST API baru tersedia sejak versi itu) dan username/password yang dimasukkan sama dengan akun BOS+ Anda.
