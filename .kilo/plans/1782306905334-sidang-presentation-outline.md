# Outline Presentasi Sidang Tugas Akhir

## Navigasi Robot Berbasis Layered Costmap untuk Pergerakan Antar Lantai pada Lingkungan Indoor Pasca Gempa Bumi

**Bahasa:** Bahasa Indonesia (istilah teknis dalam Bahasa Inggris)
**Rasio:** 16:9 Widescreen
**Estimasi total slide:** 14–16 slides
**Target durasi:** 12–15 menit presentasi

---

## Design System & Aesthetic Guide

### Palet Warna
| Elemen | Warna | Hex |
|---|---|---|
| Background utama | Putih bersih | `#FFFFFF` |
| Aksen primer | Biru elektro ITS | `#003A70` |
| Aksen sekunder | Biru muda | `#4A90D9` |
| Teks heading | Biru tua | `#1A2B4C` |
| Teks body | Abu-abu gelap | `#333333` |
| Highlight / emphasis | Oranye hangat | `#F08C2E` |
| Diagram box fill | Biru sangat muda | `#E8F0FE` |

### Tipografi
| Elemen | Font | Ukuran |
|---|---|---|
| Judul slide | Montserrat Bold | 32–36pt |
| Subjudul | Montserrat SemiBold | 22–26pt |
| Body text | Lato / Source Sans Pro | 16–18pt |
| Kode / teknis | Fira Code / Consolas | 14–16pt |
| Caption diagram | Lato Italic | 12–14pt |

### Layout Rules
- Margin konten: 7% dari setiap sisi slide
- Jarak antar elemen vertikal: minimal 16pt
- Maksimal 5–6 bullet points per slide (tanpa sub-bullet berlebihan)
- Setiap slide memiliki satu *focal point* utama
- Gunakan whitespace agresif — jangan padatkan konten
- Diagram/flownya: box dengan rounded corner (radius 8px), shadow subtle
- Semua gambar/foto: berikan border subtle `#E0E0E0` 1px

---

## Struktur Slide (Slide-by-Slide)

### Slide 1 — Title Slide 🎯
Lihat **Detailed Content: Title Slide** di bawah.

### Slide 2 — Outline / Daftar Isi
**Isi konten:** 5–6 poin utama presentasi dalam layout grid 2×3 atau vertikal.
- Latar Belakang
- Rumusan Masalah & Tujuan
- Metodologi & Desain Sistem
- Hasil Pengujian
- Kesimpulan & Saran

**Layout:** Grid 2×3 dengan ikon bulat di atas setiap label. Setiap item diberi nomor urut besar (01–05) dengan warna aksen.

### Slide 3 — Latar Belakang 🎯
Lihat **Detailed Content: Latar Belakang** di bawah.

### Slide 4 — Rumusan Masalah 🎯
Lihat **Detailed Content: Rumusan Masalah** di bawah.

### Slide 5 — Tujuan & Manfaat
**Isi konten:**
- **Tujuan:**
  1. Mengembangkan representasi lingkungan multi-lantai menggunakan *layered costmap*
  2. Merancang algoritma lokalisasi, *path planning*, dan *path tracking* untuk navigasi antar lantai
  3. Menguji sistem di lingkungan simulasi untuk evaluasi efektivitas
- **Manfaat:**
  1. Kontribusi pada sistem navigasi robot otonom di lingkungan kompleks
  2. Dasar awal navigasi robot di area bertingkat/runtuh pasca gempa
  3. Fondasi penelitian lanjutan robot SAR otonom

**Layout:** Dua kolom sejajar — kiri (Tujuan), kanan (Manfaat). Gunakan ikon target dan bintang.

### Slide 6 — Tinjauan Pustaka (Opsional — bisa dilewati jika waktu terbatas)
**Isi konten:**
- **Layered Costmap:** Representasi grid 2D bertingkat (macenski2023)
- **ICP Localization:** Scan matching berbasis point cloud
- **A* Path Planning:** BFS dengan fungsi heuristik f(n)=g(n)+h(n)
- **DWA Local Planner:** Dynamic Window Approach untuk trajectory generation
- **State of the Art:** Penelitian navigasi antar lantai (elevator, tangga, multi-floor)

**Layout:** 4 kartu horizontal dengan ikon dan satu kalimat penjelasan per konsep.

### Slide 7 — Gambaran Umum Sistem
**Isi konten:**
- Diagram arsitektur sistem navigasi secara keseluruhan
- 4 komponen utama: Occupancy Grid → Costmap → Lokalisasi → Path Planning & Tracking
- Flow: Sensor → Lokalisasi (ICP) → Costmap → Global Planner (A*) → Local Planner (DWA) → Motor

**Layout:** Diagram blok horizontal dengan arrow flow. Setiap blok diberi warna berbeda dari palet biru.

### Slide 8 — Pengolahan Data Map (Multi-Region)
**Isi konten:**
- Lingkungan 3D dibagi menjadi beberapa *region* 2D (Region A, B, C)
- Setiap region = proyeksi 2D dari sub-bagian lingkungan 3D
- ROI detection: deteksi area non-putih pada peta → bounding box
- **Combined Map:** gabungan ketiga region dalam satu frame
- **Transition Map:** menyimpan koneksi spasial antar region (koordinat konektor, orientasi quaternion, pose awal robot)

**Layout:** Diagram 3-kolom: kiri (3D environment) → tengah (slicing menjadi A, B, C) → kanan (combined map + transition map). Tampilkan screenshot small dari peta asli.

### Slide 9 — Struktur Layered Costmap
**Isi konten:**
- **3 layer utama costmap:**
  1. **Global Costmap** — static layer (obstacle tetap), inflation layer
  2. **Local Costmap** — obstacle layer (LiDAR real-time), inflation layer
  3. **Transition Costmap** — menyimpan informasi koneksi antar region
- Fungsi inflasi: $$C(d) = 253 \cdot e^{-\alpha \cdot (d - r_{\text{inscribed}})}, d \leq R$$
- Costmap values: `FREE_SPACE (0)` → `TRANSITION_CELL (1–5)` → `INFLATED (6–252)` → `LETHAL (254)` → `NO_INFO (255)`

**Layout:** Diagram 3-layer bertumpuk (stacked boxes) dengan transparansi. Formula di highlight box terpisah.

### Slide 10 — Lokalisasi ICP & Region Switcher
**Isi konten:**
- **ICP (Iterative Closest Point):**
  - Prekomputasi KNN dengan hash table (lookup O(1))
  - Correspondence matching → SVD solver → Rotasi & Translasi
  - Parameter: max_iter=50, k=8, r=10, t_norm=0.01m, r_norm=0.01rad
- **Region Switcher:** deteksi posisi robot memasuki zona transisi → switch ke region berikutnya
- Zona transisi: radius minimal 0.24–0.26 m dari ujung map

**Layout:** Kiri: diagram ICP pipeline (Scan → Match → Transform). Kanan: ilustrasi region switching dengan panah antar region A→B→C.

### Slide 11 — Path Planning (A* Global Planner)
**Isi konten:**
- **A* algorithm** dengan *quadratic potential* calculation
- **Path Interceptor:** memecah path multi-region menjadi segmen per region
  - Region A → titik transisi A-B → Region B → titik transisi B-C → Region C
- **Cost Scaling Factor (CSF):** mempengaruhi *cost gradient* dan bentuk path
  - CSF = 10: path di tengah (konservatif)
  - CSF = 100: path dekat obstacle, lebih pendek & lurus (optimal)

**Layout:** Atas: diagram A* grid dengan open/closed list. Bawah: perbandingan visual path CSF 10 vs CSF 100 pada peta Region A atau C.

### Slide 12 — Path Tracking (DWA Local Planner)
**Isi konten:**
- **DWA (Dynamic Window Approach):** 1080 trajectory per evaluasi
- 5 tahap: velocity sampling → kinematic simulation → trajectory scoring → best selection → send
- 7 kriteria scoring: oscillation, obstacle, goal front, alignment, path, goal, twirl
- Mampu menghindari obstacle dinamis yang tidak ada di global path

**Layout:** Flow diagram 5-step horizontal. Trajectory visualization: beberapa garis trajectory dari robot dengan satu yang terpilih (highlight).

### Slide 13 — Arena Pengujian & Skenario
**Isi konten:**
- **Simulator:** Mujoco
- **Robot:** Hexapod (6 kaki)
- **Arena:** 3 region (A, B, C) — lorong, area terbuka, tangga/ramp
- **2 skenario:**
  1. Normal: lantai rata, obstacle statis diketahui
  2. Pasca gempa: permukaan tidak rata (rough floor), obstacle tidak diketahui
- Tampilkan screenshot arena simulasi untuk kedua skenario

**Layout:** Grid 2×2: (1) Arena Region A, (2) Arena Region B, (3) Arena Region C, (4) Arena rough floor. Beri label di setiap gambar.

### Slide 14 — Hasil Pengujian: ICP & Costmap
**Isi konten (2 sub-slide atau split layout):**
- **ICP Localization:**
  - Region A (rata): error rendah, stabil. Lonjakan di t=50s (zona transisi)
  - Region A (rough floor): osilasi ↑ signifikan pada sumbu x dan yaw
  - Region C (kompleks): error lebih tinggi karena lebih banyak obstacle & trajectory rumit
  - Zona transisi: minimal 0.26 m untuk transisi aman
- **Costmap:**
  - CSF 100 → path terpendek, optimal di Region A & C
  - Region B (lorong sempit): CSF tidak signifikan berpengaruh
  - Trade-off: path pendek vs deviasi ground truth (CSF 100 deviasi tertinggi, tapi paling efisien)

**Layout:** Grafik error ICP vs waktu (dari pengujian). Bar chart perbandingan panjang path untuk CSF 10/20/50/100.

### Slide 15 — Hasil Pengujian: DWA & Navigasi Total
**Isi konten:**
- **DWA Planner:**
  - Kondisi normal: *mean cross track error* rendah, mengikuti global path baik
  - Kondisi gempa: *max cross track error* meningkat signifikan (ada obstacle unknown)
- **Navigasi Penuh (Region A → C):**
  - **Waktu tempuh: 127.26 detik**
  - Robot berhasil mencapai tujuan
  - Semua komponen bekerja terintegrasi

**Layout:** Tabel perbandingan metrik DWA (normal vs gempa) + highlight box besar untuk "127.26 detik — Navigasi Berhasil".

### Slide 16 — Kesimpulan
**Isi konten (5 poin kunci):**
1. Metode *layered costmap* berhasil merepresentasikan lingkungan multi-lantai sebagai kumpulan peta 2D region
2. ICP localization akurat untuk navigasi, dengan peningkatan error pada lantai tidak rata dan region kompleks
3. *Cost Scaling Factor* 100 menghasilkan jalur terpendek dengan tetap menghindari obstacle
4. *Costmap* transisi berhasil menggabungkan region pada radius transisi minimal 0.26 meter
5. DWA Planner mampu mengakomodasi obstacle tidak diketahui dan menghasilkan trajectory aman

**Layout:** 5 kartu horizontal dengan ikon centang (✓) besar. Setiap kartu satu poin.

### Slide 17 — Saran / Future Work
**Isi konten:**
1. **Prekomputasi KNN per region** — parameter radius & k optimal berbeda-beda tiap region
2. **Fusion ICP + IMU** — kompensasi lonjakan error di zona transisi
3. **Integrasi Depth Camera** — deteksi obstacle vertikal yang tidak terlihat LiDAR 2D
4. **Pengujian pada robot fisik** — validasi di lingkungan nyata

**Layout:** 4 kartu vertikal dengan ikon panah ke depan. Brief.

### Slide 18 — Penutup / Thank You
**Isi konten:**
- "Terima Kasih"
- Nama: Bagas Surya Wirawan | NRP: 5022221026
- Dosen Pembimbing: Dr. Ir. Djoko Purwanto, M.Eng. | Fajar Budiman, S.T., M.Sc.
- Departemen Teknik Elektro, FTEIC — ITS
- Kontak (email opsional)

**Layout:** Clean, centered. Background dengan subtle pattern atau gradient biru ITS. Foto formal (opsional, kecil di pojok).

---

## Detailed Content: Title Slide 🎯

### Slide Spec
- **Posisi:** Slide 1
- **Durasi:** ~15–20 detik (salam pembuka)
- **Fungsi:** Memberikan kesan pertama profesional, menyampaikan informasi inti karya tulis

### Text Content

```
NAVIGASI ROBOT BERBASIS
LAYERED COSTMAP
UNTUK PERGERAKAN ANTAR LANTAI
PADA LINGKUNGAN INDOOR PASCA GEMPA BUMI

┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈

Bagas Surya Wirawan
NRP. 5022221026

Dosen Pembimbing:
Dr. Ir. Djoko Purwanto, M.Eng.
Fajar Budiman, S.T., M.Sc.

Departemen Teknik Elektro
Fakultas Teknologi Elektro dan Informatika Cerdas
Institut Teknologi Sepuluh Nopember
Surabaya · 2025
```

### Visual Layout

| Elemen | Posisi & Styling |
|---|---|
| **Background** | Gradien diagonal dari `#003A70` (kiri atas) ke `#1A5276` (kanan bawah), dengan overlay pattern geometris subtle (hex grid atau dot matrix) pada opacity 8% |
| **Garis dekoratif** | Garis horizontal tipis (`#F08C2E`, 2pt, width 40%) di antara judul dan nama — sebagai *visual separator* |
| **Judul** | Montserrat Bold, 36pt, `#FFFFFF`, line spacing 1.3, rata kiri, margin kiri 10%. Tiga baris pertama lebih besar (sub-judul "UNTUK PERGERAKAN..." sedikit lebih kecil: 30pt) |
| **Nama & NRP** | Montserrat SemiBold, 20pt, `#FFFFFF` opacity 90% |
| **Pembimbing** | Lato Regular, 16pt, `#FFFFFF` opacity 75% |
| **Institusi** | Lato Light, 14pt, `#FFFFFF` opacity 65% |
| **Logo ITS** | Pojok kanan atas, ukuran ~2.5cm tinggi, versi putih (jika ada) |
| **Ilustrasi** | Pojok kanan bawah: siluet robot hexapod dengan gaya minimalis (line art putih, opacity 15%) — berfungsi sebagai elemen dekoratif subtle |

### Additional Notes
- Tidak ada bullet points pada title slide
- Pertahankan whitespace yang lapang — title slide harus terasa "ringan"
- Jika menggunakan foto robot atau screenshot simulasi, tempatkan sebagai background subtle dengan opacity sangat rendah (5–10%) agar teks tetap terbaca

---

## Detailed Content: Latar Belakang (Background) 🎯

### Slide Spec
- **Posisi:** Slide 3 (setelah Outline)
- **Durasi:** ~2 menit presentasi
- **Fungsi:** Membangun urgensi, menetapkan konteks masalah, dan memperkenalkan gap yang dijawab oleh penelitian

### Structured Content

#### Header
```
LATAR BELAKANG
```

#### Bullet Points

```
1. INDONESIA RAWAN GEMPA BUMI
   · Terletak di pertemuan 4 lempeng tektonik (Pasifik, Eurasia,
     Indo-Australia, Laut Filipina)
   · Rata-rata 18 gempa per hari — BMKG (2020)

2. OPERASI SAR PASCA GEMPA BERISIKO TINGGI
   · Petugas SAR menghadapi ancaman keselamatan di area terdampak
   · Bangunan rusak, atap hampir roboh, struktur tidak stabil
   · Contoh: robot darat digunakan pasca gempa Jepang untuk inspeksi
     bangunan (Lin et al., 2022)

3. ROBOT OTONOM DAPAT MEMBANTU MISI SAR
   · Robot UAV: gambaran medan dari udara
   · Robot darat (track / quadruped / hexapod): angkut barang berat,
     inspeksi area sempit dan berbahaya
   · Robot otonom krusial saat infrastruktur komunikasi rusak
```

```
4. TANTANGAN UTAMA: NAVIGASI INDOOR PASCA GEMPA
   · Lingkungan tidak terstruktur: puing, lantai tidak rata, tangga
   · Costmap 2D konvensional terbatas: hanya satu bidang datar
   · Robot perlu bernavigasi ANTAR LANTAI untuk misi di dalam bangunan

5. SOLUSI YANG DIUSULKAN: LAYERED COSTMAP
   · Menyederhanakan informasi 3D → beberapa bidang costmap 2D
   · Setiap layer mewakili satu lantai/region di dalam bangunan
   · Layer transisi menghubungkan antar lantai (tangga/ramp)
   · Robot berpindah layer sesuai posisinya di bangunan
```

### Visual Layout Recommendations

| Elemen | Deskripsi |
|---|---|
| **Layout keseluruhan** | Split 60/40 — kiri (teks bullet), kanan (visual support). Alternatif: full-width stacked jika visual terlalu kompleks |
| **Ikon per poin** | Gunakan ikon SVG sederhana di depan setiap angka (1–5): globe untuk poin 1, shield-cross untuk poin 2, robot untuk poin 3, building-crack untuk poin 4, layers untuk poin 5 |
| **Sisi kanan visual** | Tampilkan 3 elemen bertumpuk: (1) Peta Indonesia dengan titik gempa [atas], (2) Foto bangunan runtuh pasca gempa [tengah], (3) Ilustrasi konsep layered costmap: 3 layer 2D grid bertumpuk dengan robot kecil di atasnya [bawah]. Setiap gambar muncul bergantian (animasi fade in) seiring narasi poin |
| **Highlight box** | Di bawah poin 5, tambahkan callout box kecil berwarna `#FFF3E0` dengan border kiri oranye `#F08C2E` (4pt) berisi teks: "Pendekatan ini menyederhanakan kompleksitas 3D menjadi representasi 2D yang manageable, memungkinkan penggunaan sensor LiDAR 2D." |
| **Transisi** | Gunakan Morph transition (PowerPoint) atau fade untuk kemunculan setiap poin agar audiens fokus satu per satu |
| **Font emphasis** | Kata kunci di-bold + warna aksen: "4 lempeng tektonik", "18 gempa per hari", "ANTAR LANTAI", "Layered Costmap" |

### Narasi Lisan (Suggested Talking Points)
Slide ini dijelaskan dengan alur: **Masalah makro (gempa di Indonesia) → Dampak pada SAR → Peluang robot → Gap teknologi → Solusi yang diusulkan.** Jangan membaca bullet points. Gunakan sebagai jangkar visual sambil bercerita.

---

## Detailed Content: Rumusan Masalah (Problem Statement) 🎯

### Slide Spec
- **Posisi:** Slide 4 (setelah Latar Belakang)
- **Durasi:** ~1.5 menit presentasi
- **Fungsi:** Merumuskan pertanyaan penelitian yang dijawab secara eksplisit, menetapkan batasan

### Structured Content

#### Header
```
RUMUSAN MASALAH
```

#### Pertanyaan Penelitian (3 Questions)

```
1. REPRESENTASI LINGKUNGAN
   Bagaimana merepresentasikan informasi lingkungan multi-lantai
   menggunakan layered costmap agar dapat digunakan pada
   algoritma navigasi antar lantai?

2. ALGORITMA NAVIGASI
   Bagaimana merancang algoritma lokalisasi, path planning, dan
   path tracking yang bekerja pada sistem navigasi berbasis
   layered costmap?

3. VALIDASI SISTEM
   Apakah robot darat otonom dapat melakukan navigasi hingga
   mencapai tujuan pada arena uji menggunakan metode
   navigasi antar lantai yang dikembangkan?
```

#### Batasan Masalah (Constraints)

```
BATASAN PENELITIAN

  ➤ Pengujian dilakukan pada SIMULASI (Mujoco) — bukan kondisi
    pasca gempa sebenarnya, melainkan rekayasa arena uji
    (rintangan tidak diketahui, tanjakan, permukaan tidak rata)

  ➤ Robot yang digunakan: HEXAPOD (6 kaki), navigasi otonom
    dari titik awal ke tujuan yang telah ditentukan

  ➤ Algoritma navigasi bekerja pada kondisi rintangan statis
    yang SUDAH DIKETAHUI (known map)
```

### Visual Layout Recommendations

| Elemen | Deskripsi |
|---|---|
| **Layout keseluruhan** | Vertikal stacked: 3 kartu pertanyaan di atas, 1 panel batasan di bawah. Proporsi ~65/35 |
| **3 kartu pertanyaan** | Masing-masing kartu horizontal dengan: nomor besar (01, 02, 03) di kiri dalam lingkaran berwarna `#4A90D9`, judul pendek (REPRESENTASI LINGKUNGAN / ALGORITMA NAVIGASI / VALIDASI SISTEM) bold 18pt, diikuti pertanyaan lengkap 14pt. Background kartu `#F5F9FF`, border kiri warna aksen 4pt |
| **Batasan** | Panel bawah dengan background `#FFF8F0`, ikon peringatan segitiga kecil, 3 poin dengan bullet "➤". Font lebih kecil (13pt), warna teks lebih subtle (`#555`) untuk membedakan dari konten utama |
| **Animasi** | 3 kartu pertanyaan muncul satu per satu (fly-in from left). Panel batasan muncul terakhir (fade in) |
| **Visual cue** | Tanda tanya besar (watermark, opacity 8%) di background sebagai elemen dekoratif. Warna tanda tanya `#4A90D9` |

---

## Lampiran: Catatan Tambahan

### Slide Opsional (Backup Slides — ditampilkan hanya jika ditanya penguji)

1. **Backup 1 — Detail ICP Algorithm:** rumus matematis, pseudocode, parameter lengkap
2. **Backup 2 — Detail DWA Scoring:** 7 kriteria dengan bobot, formula trajectory scoring
3. **Backup 3 — Data Mentah Pengujian:** tabel lengkap cross-track error, path length comparison
4. **Backup 4 — Flowchart Sistem Lengkap:** diagram detail seluruh arsitektur dengan semua sub-komponen
5. **Backup 5 — Perbandingan dengan State of the Art**

### Tips Presentasi
- Gunakan **fitur Morph** PowerPoint untuk transisi halus antar diagram
- **Slide number** di pojok kanan bawah setiap slide (kecuali title slide)
- Konsisten gunakan **footer kecil** di setiap slide: "Sidang Tugas Akhir · Bagas Surya Wirawan · 5022221026"
- Untuk slide dengan grafik (Hasil Pengujian), label sumbu harus terbaca dari jarak 3 meter (font ≥ 12pt)
- Hindari penggunaan bullet points > 2 level kedalaman
- Setiap gambar/foto harus memiliki credit line kecil di bawahnya

### Referensi Desain
- Template serupa: rekomendasi menggunakan Slidesgo "Modern Blue" theme atau Canva "Tech Blue Presentation"
- Untuk diagram teknis: gunakan draw.io atau diagrams.net dengan palet warna yang disesuaikan
- Untuk grafik hasil: gunakan matplotlib (Python) dengan style `seaborn-v0_8-whitegrid`, ekspor SVG agar scalable
