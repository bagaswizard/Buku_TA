# Plan: Rapikan `\subsection{Local Planner DWA}`

## Objective
Perbaiki tata bahasa, struktur, dan konsistensi pada section Local Planner DWA (baris 901–1061 di `sistem_navigasi.tex`). Hapus komentar pseudocode yang tidak terpakai, ganti judul campuran Inggris-Indonesia, dan tambah paragraf penjelas.

## File
`bab/Metodologi/sistem_navigasi.tex` — baris 901–1061

## Current Issues
| Baris | Masalah |
|-------|---------|
| 955 | Rumus total cost terlalu panjang dalam satu baris |
| 957–963 | 7 critic weights dalam komentar |
| 965 & 979 | Rumus `C_obs` duplikasi |
| 977 | `Mode sum scores` judul Inggris |
| 983 | `\subsubsection{kalkulasi Cost}` — huruf kecil, campuran Inggris-Indonesia |
| 985 | Paragraf fragment satu kalimat |
| 987–996 | `Wavefront Propagation` — komentar pseudocode |
| 1000–1045 | 6 judul (Scoring Mode, dst) sebagai teks biasa tanpa format |
| 1046 | `Seleksi Trajectory terbaik` tanpa subbab |
| spread | Komentar `%` pseudocode tak terpakai di banyak tempat |

## Restructured Plan

Replace lines 901–1061 with:

### 1. Paragraf pembuka (baris 900–912 diganti)
Penjelasan singkat DWA sebagai local planner, peran dalam navigasi. Pertahankan 5 langkah utama dengan bahasa yang lebih lancar.

### 2. `\subsubsection{Velocity Window}` (existing, perbaiki)
- Rapikan penjelasan dynamic window
- Rumus `v_min`, `v_max` dipisah per baris

### 3. `\subsubsection{Velocity Sampling}` (existing, biarkan)
Sudah cukup rapi.

### 4. `\subsubsection{Model Kinematik}` (existing, biarkan)
Sudah cukup rapi.

### 5. `\subsubsection{Penilaian Trajectory}` (baru — ganti "Penilaian Trayektori")
- Rumus total cost dipecah per komponen (multi-line)
- Tabel 7 critics dengan bobot default (ganti komentar lines 957–963)
- Rumus `C_obs` (satu saja, hapus duplikasi)
- Collision checking diintegrasikan ke paragraf
- Hapus komentar `%` pseudocode

### 6. `\subsubsection{Kalkulasi Biaya dengan MapGrid}` (baru — ganti "kalkulasi Cost")
- Judul Indonesia konsisten
- BFS wavefront propagation: komentar `%` diintegrasikan ke paragraf
- Path costs, goal costs, forward point shift, goal front, alignment costs sebagai sub-paragraf dengan `\textbf{bold}`
- Hapus komentar `%` pseudocode

### 7. `\subsubsection{Seleksi Trajectory}` (baru)
- Paragraf pembuka singkat
- Listing pseudocode tetap dipertahankan
- Early termination sebagai paragraf

## Changes Summary
| Perubahan | Detail |
|-----------|--------|
| Hapus | Duplikasi rumus `C_obs` (baris 979) |
| Hapus | Semua komentar `%` pseudocode (lines 957–963, 969–971, 989–995, 1012–1024, 1036, 1048) |
| Ganti | `Penilaian Trayektori` → `Penilaian Trajectory` (konsisten) |
| Ganti | `kalkulasi Cost` → `Kalkulasi Biaya dengan MapGrid` |
| Ganti | `Wavefront Propagation` → diintegrasi ke paragraf |
| Ganti | `Scoring Mode`, `Forward Point Shift`, dll → sub-paragraf dalam subbab |
| Tambah | Tabel 7 critics (ganti komentar) |
| Tambah | Paragraf penjelas untuk setiap subbab |
| Biarkan | Rumus, listing pseudocode, konten teknis yang valid |

## Validation
- Kompilasi `latexmk -pdf` — pastikan tidak ada error
- Verifikasi semua `\label` dan `\ref` masih valid
- Pastikan tidak ada duplikasi konten
