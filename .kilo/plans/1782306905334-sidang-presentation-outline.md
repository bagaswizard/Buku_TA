# Plan: Perubahan Slide Presentasi Sidang TA

## Target
Edit `generate_presentation.py` untuk menerapkan perubahan konten dan layout pada slide metode, hasil, dan struktur presentasi.

---

## Task List

### Task 1: Slide 11 (ICP) — hapus gambar sim
- **Fungsi:** `slide_icp` (line ~1096)
- Hapus `sim_RA.png` (line ~1217–1227) — gambar arena + label
- Region Switcher & zona transisi text tetap

### Task 2: Tambah slide flowchart setelah Slide 8
- **Fungsi baru:** `slide_nav_flow` — letakkan di antara `slide_system_overview` dan `slide_map_processing`
- **Konten:** Judul "DETAIL ALUR NAVIGASI" + gambar `gambar/main_nav_flow_split.png` (752×542, img_h=Inches(4.5))
- Update `main()`: panggil `slide_nav_flow(prs)` setelah `slide_system_overview`
- Slide numbering di-offset +1 untuk semua slide setelahnya
- Buat fungsi `add_table_from_csv(slide, left, top, width, height, csv_path, title)` helper untuk membuat tabel dari CSV

### Task 3: Slide 12 (Path Planning) — hapus CSF, perluas global planner
- **Fungsi:** `slide_path_planning` (line ~1233)
- Hapus seluruh section kanan: CSF cards (lines ~1279–1303), key finding box (lines ~1305–1312), path_all_RA image (lines ~1314–1326)
- Ganti sisi kanan dengan penjelasan teknis Global Planner:
  - **Global Costmap Integration:** "Global planner menggunakan static layer dari global costmap untuk menghitung cost gradient pada occupancy grid. Setiap sel memiliki nilai biaya berdasarkan jarak ke obstacle terdekat dan CSF."
  - **Quadratic Potential:** "Untuk setiap node n, cost g(n) dihitung menggunakan quadratic potential: cost = k * d², di mana d adalah jarak dari obstacle. Ini menghasilkan gradien biaya yang halus dan mendorong path menjauhi obstacle."
  - **Multi-Region Path Interception:** "Path interceptor memecah rute global menjadi segmen per region: Region A → titik transisi → Region B → titik transisi → Region C → goal. Setiap segmen di-plan secara independen oleh A* pada costmap region masing-masing."
- Tambah juga ilustrasi sederhana dengan shapes (kotak bertumpuk mewakili path interceptor)

### Task 4: Ganti Slide 16 jadi 3 slide hasil path planning (Region A, B, C)
- **Hapus:** `slide_results_path` (line ~1522)
- **Buat 3 fungsi baru:**
  - `slide_results_path_RA` — Region A
  - `slide_results_path_RB` — Region B
  - `slide_results_path_RC` — Region C
- Masing-masing slide berisi:
  1. **Gambar:** `gambar/map_with_paths_RA.svg` / `_RB.svg` / `_RC.svg` (SVG, convert via cairosvg atau gunakan PNG fallback; atau embed langsung jika pptx mendukung SVG)
     - Jika SVG tidak didukung pptx, gunakan `gambar/path_all_RA.png` dll sebagai fallback
  2. **Tabel CSF:** dari `lampiran/path_CSF_RA.csv` dll — kolom: CSF, Panjang (m), Waktu (ms), Clearance (m), Waypoint
  3. **Tabel Deviasi:** dari `lampiran/path_stats_RA.csv` dll — kolom: CSF, Mean CT (m), Max CT (m), SD (m)
  4. **Key finding** box di bawah tabel
- Update `main()`: ganti panggilan `slide_results_path` dengan 3 panggilan baru

### Task 5: Slide Navigasi (17) — tambah tabel data
- **Fungsi:** `slide_results_navigation` (line ~1657)
- Layout: kiri — DWA explanation cards tetap, kanan — highlight "127.26 detik" tetap
- Tambah di bawah: **2 tabel** side-by-side (atau stacked jika sempit):
  - Tabel Normal: dari `lampiran/path_track.csv` — kolom: Region, Waktu (s), Mean CTE (m), Max CTE (m)
  - Tabel Rough: dari `lampiran/path_track_rough.csv` — kolom sama

### Task 6: Slide ICP (15) — tetap image-based
- Tidak ada CSV data untuk ICP. Pertahankan 2 gambar ICP errors (normal + rough floor) + key finding

### Task 7: Hapus fungsi tidak terpakai
- Hapus `slide_results_icp_costmap` (line ~1580) — tidak dipanggil dari `main()`

### Task 8: Update main() call order
- Setelah perubahan, urutan panggilan di `main()`:
  1. slide_title
  2. slide_outline
  3. slide_background
  4. slide_problem
  5. slide_objectives
  6. slide_literature
  7. slide_prior_research
  8. slide_system_overview
  9. **slide_nav_flow** ← NEW
  10. slide_map_processing
  11. slide_costmap_structure
  12. slide_icp
  13. slide_path_planning
  14. slide_dwa
  15. slide_arena
  16. slide_results_icp
  17. **slide_results_path_RA** ← NEW (menggantikan slide_results_path)
  18. **slide_results_path_RB** ← NEW
  19. **slide_results_path_RC** ← NEW
  20. slide_results_navigation
  21. slide_conclusion
  22. slide_future_work
  23. slide_thanks

---

## Data Files Referenced

| Data | CSV Path | Kolom |
|---|---|---|
| CSF Region A | `lampiran/path_CSF_RA.csv` | CSF, Panjang path (m), Waktu komputasi (ms), min clearance (m), Jumlah waypoint |
| CSF Region B | `lampiran/path_CSF_RB.csv` | (sama) |
| CSF Region C | `lampiran/path_CSF_RC.csv` | (sama) |
| Deviasi Region A | `lampiran/path_stats_RA.csv` | CSF, mean cross track (m), max cross track (m), SD (m) |
| Deviasi Region B | `lampiran/path_stats_RB.csv` | (sama) |
| Deviasi Region C | `lampiran/path_stats_RC.csv` | (sama, hanya CSF 20/50/100) |
| Path Track Normal | `lampiran/path_track.csv` | region, Waktu (s), Mean CTE (m), Max CTE (m) |
| Path Track Rough | `lampiran/path_track_rough.csv` | (sama) |

## Images Referenced

| Slide | Image Path |
|---|---|
| Nav Flow (new) | `gambar/main_nav_flow_split.png` |
| Path RA (new) | `gambar/map_with_paths_RA.svg` |
| Path RB (new) | `gambar/map_with_paths_RB.svg` |
| Path RC (new) | `gambar/map_with_paths_RC.svg` |

---

## Implementation Notes

1. **SVG in pptx:** python-pptx tidak mendukung SVG native. Gunakan `cairosvg` untuk konversi SVG→PNG saat runtime, atau render ulang sebagai PNG dari matplotlib. Sebagai alternatif: gunakan `path_all_RA.png` etc yang sudah ada.
2. **Tabel CSV:** Buat helper `add_table_from_csv(slide, x, y, w, csv_path)` yang membaca CSV dengan `csv.DictReader` dan membuat `slide.shapes.add_table()`.
3. **Nomor slide:** Semua `add_slide_number()` harus diupdate untuk merefleksikan nomor slide baru.
