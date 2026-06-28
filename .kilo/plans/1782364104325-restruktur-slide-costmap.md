# Restruktur Slide Costmap

## Latar Belakang

Saat ini slide costmap (S12 "STRUKTUR LAYERED COSTMAP") mencakup semua konten
costmap dalam satu slide: 3 layer, fungsi inflasi, tabel konstanta — terlalu padat.

## Tujuan

Pisahkan menjadi **4 slide** sesuai arahan:
1. Slide overview Costmap (konsep + tabel)
2. Slide Global Costmap (static + inflation)
3. Slide Local Costmap (obstacle + inflation + rolling window)
4. Slide Transition Costmap (transition layer + BFS)

## Keputusan

| Keputusan | Pilihan |
|-----------|---------|
| Fungsi inflasi $C(d)$ | Di slide **Global Costmap** |
| Tabel konstanta costmap | Di slide **Overview** |
| Tabel komposisi 3 layer | Di slide **Overview** |
| BFS expansion algorithm | Di slide **Transition Costmap** |
| Path Interceptor | Tetap di slide **Path Planning** |

## Dampak Slide Number

**Sebelum** (24 slide):
```
S12: Struktur Layered Costmap (1 slide)
S13: ICP
S14: Path Planning
S15: DWA
S16: Arena
S17: ICP Results
S18-S20: Path Results RA/RB/RC
S21: Nav Results
S22: Conclusion
S23: Future Work
S24: Thanks
```

**Sesudah** (27 slide — +3):
```
S12: COSTMAP — Overview
S13: GLOBAL COSTMAP
S14: LOCAL COSTMAP
S15: TRANSITION COSTMAP
S16: ICP
S17: Path Planning
S18: DWA
S19: Arena
S20: ICP Results
S21-S23: Path Results RA/RB/RC
S24: Nav Results
S25: Conclusion
S26: Future Work
S27: Thanks
```

Semua slide setelah S12 renumbered (+3).

## Konten Per Slide

### S12: COSTMAP — Overview

Judul: "COSTMAP — Representasi Biaya Navigasi"

**Kiri:**
- Paragraf pengertian costmap (grid 2D, nilai 0–255, rendah=aman, tinggi=berbahaya)
- Tabel **komposisi 3 layer** (global=static+inflasi, local=obstacle+inflasi,
  transition=static+transition)

**Kanan:**
- Tabel **konstanta costmap** (NO_INFORMATION=255, LETHAL=254, INSCRIBED=253,
  INFLATED=1-252, TRANSITION_CELL=1-5, FREE_SPACE=0)
- Catatan: konstanta dijelaskan secara singkat

### S13: GLOBAL COSTMAP

Judul: "GLOBAL COSTMAP — Perencanaan Jalur Skala Luas"

- Definisi: mencakup seluruh area yang diketahui dari peta
- Digunakan oleh global planner (A*) untuk perencanaan path skala luas
- **Static layer**: obstacle tetap dari peta (occupancy grid → cost internal)
- **Inflation layer**: zona aman di sekitar obstacle
- **Fungsi inflasi** $C(d)$:
  \[
  C(d) = 253 \cdot e^{-\alpha \cdot (d - r_{\text{inscribed}})}
  \]
  dengan parameter $d$, $R$, $r_{\text{inscribed}}$, $\alpha$

### S14: LOCAL COSTMAP

Judul: "LOCAL COSTMAP — Navigasi Jangka Pendek Real-Time"

- Definisi: mencakup area di sekitar robot (rolling window)
- Digunakan oleh DWA local planner untuk trajectory planning
- Rolling window: grid bergerak mengikuti robot, origin digeser sesuai pose
- **Obstacle layer**: rintangan dinamis dari scan LiDAR real-time
  - Konversi endpoint → transformasi → mark obstacle (254)
  - Bresenham ray tracing untuk clear area antara robot dan endpoint
- **Inflation layer**: sama dengan global, menjaga jarak aman

### S15: TRANSITION COSTMAP

Judul: "TRANSITION COSTMAP — Perpindahan Antar Region"

- Definisi: menggabungkan data transisi dengan peta statis
- Digunakan oleh region switcher untuk deteksi batas region
- **Static layer**: obstacle tetap dari peta
- **Transition layer**: dua jenis nilai:
  - $T = 1$: garis transisi utama (tempat lompatan pose dieksekusi)
  - $E = 5$: zona buffer di sekitar garis transisi (robot bersiap)
- BFS expansion dari seed T=1 hingga radius $R$ sel, stop jika nemu lethal
- Region switcher: deteksi $E=5$ → prepare, deteksi $T=1$ → execute jump

## File yang Dimodifikasi

### generate_presentation.py

1. **Hapus** fungsi `slide_costmap_structure` (diganti 4 fungsi baru)
2. **Tambah** 4 fungsi:
   - `def slide_costmap_overview(prs):`  — S12
   - `def slide_costmap_global(prs):`   — S13
   - `def slide_costmap_local(prs):`    — S14
   - `def slide_costmap_transition(prs):` — S15
3. **Update main()**: ganti `slide_costmap_structure(prs)` dengan 4 calls
4. **Renumber** semua slide S16-S27 (+3):
   - `slide_icp`: docstring "Slide 11" → "Slide 16", add_num 13 → 16
   - `slide_path_planning`: docstring "Slide 14" → "Slide 17", add_num 14 → 17
   - `slide_dwa`: docstring "Slide 15" → "Slide 18", add_num 15 → 18
   - `slide_arena`: docstring "Slide 16" → "Slide 19", add_num 16 → 19
   - `slide_results_icp`: docstring "Slide 17" → "Slide 20", add_num 17 → 20
   - `slide_results_path_RA`: slide_num 18 → 21, docstring "18" → "21"
   - `slide_results_path_RB`: slide_num 19 → 22, docstring "19" → "22"
   - `slide_results_path_RC`: slide_num 20 → 23, docstring "20" → "23"
   - `slide_results_navigation`: docstring "Slide 21" → "Slide 24", add_num 21 → 24
   - `slide_conclusion`: docstring "Slide 22" → "Slide 25", add_num 22 → 25
   - `slide_future_work`: docstring "Slide 23" → "Slide 26", add_num 23 → 26
   - `slide_thanks`: docstring "Slide 24" → "Slide 27"

## Verifikasi

1. `python generate_presentation.py` — harus 27 slide
2. `python pptx_check5.py` — 0 float EMU, 0 content-content overlap
3. Slide 12-15 sesuai isi yang direncanakan
