# Plan: Topological Graph Representation untuk Map Transisi

## Objective
Tambahkan penjelasan konsep topological graph (node dan edge) pada map transisi, lengkap dengan formulasi matematis dan visual TikZ.

## File yang Dimodifikasi

### Edit: `bab/Metodologi/pengolahan_map.tex`
- Tambah `\subsection{Representasi Topologi Graph}` **setelah** seluruh isi `\subsection{Map Transisi}` (setelah tabel posisi inisial, line 157).

### Buat (opsional): `bab/Metodologi/tikz_topologi_graph.tex`
- TikZ figure dapat ditulis inline di `pengolahan_map.tex` dalam `figure` environment, atau di file terpisah. Pilih pendekatan inline untuk konsistensi dengan gaya existing.

## Konten Subbab Baru

### 1. Paragraf Pembuka
Jelaskan bahwa map transisi direpresentasikan sebagai graph tak-berarah G = (V, E) untuk memodelkan hubungan spasial antar region secara formal dan memungkinkan path planning multi-region.

### 2. Tabel Node (6 nodes)
| Node | Label | Deskripsi | Region |
|------|-------|-----------|--------|
| v₀ | Init | Posisi awal robot | A |
| v₁ | Entry_AB | Titik transisi sisi A (pair 0) | A |
| v₂ | Exit_AB | Titik transisi sisi B (pair 0) | B |
| v₃ | Entry_BC | Titik transisi sisi B (pair 1) | B |
| v₄ | Exit_BC | Titik transisi sisi C (pair 1) | C |
| v₅ | Goal | Posisi tujuan | C |

### 3. Definisi Matematis
- V = {v₀, v₁, v₂, v₃, v₄, v₅}
- E = {(v₀,v₁), (v₁,v₂), (v₂,v₃), (v₃,v₄), (v₄,v₅)}
- Klasifikasi edge:
  - Intra-region (solid): (v₀,v₁) di A, (v₂,v₃) di B, (v₄,v₅) di C — dapat dilalui global planner standar
  - Inter-region (dashed): (v₁,v₂) pair 0, (v₃,v₄) pair 1 — memerlukan region switcher (jump)
- Region partitioning: R_A={v₀,v₁}, R_B={v₂,v₃}, R_C={v₄,v₅}
- Adjacency matrix A (6×6, symmetric, tridiagonal):
  ```
  A_ij = 1 untuk |i-j| = 1, 0 lainnya
  ```
- Path: untuk graph linear, path dari v_s ke v_t adalah unik dan merupakan sub-barisan kontinu dari indeks node

### 4. TikZ Figure
Desain visual:
```
┌────────────┐  ┌────────────┐  ┌────────────┐
│  Region A  │  │  Region B  │  │  Region C  │
│            │  │            │  │            │
│  (v₀)─→(v₁)│  │(v₂)─→(v₃) │  │(v₄)─→(v₅) │
│ Init Entry │  │Exit Entry  │  │ Exit Goal  │
└─────╖──────┘  └─────╖──────┘  └─────╖──────┘
      ║ pair 0       ║ pair 1        ║
      ╚══════════════╝                ╚══════════════
```

- 3 kotak region dengan fill color berbeda (gunakan warna dari skema tikz_arsitektur.tex: colMultiMap, colLokalisasi, colGlobalPlan atau variasi)
- 6 node circular (minimum size 0.7cm), fill white
- Intra-region edges: `\draw[->, thick]` warna solid
- Inter-region edges: `\draw[->, thick, dashed]` dengan label "pair 0", "pair 1"
- Label "Init", "Entry_AB", "Exit_AB", "Entry_BC", "Exit_BC", "Goal" di bawah masing-masing node
- Label region "A", "B", "C" di bagian atas setiap kotak

### 5. Kaitan dengan Path Antar Region
Jelaskan bahwa path_interceptor::buildPath('A','C') menghasilkan dua step transisi sesuai jalur graph:
P = (v₀, v₁, v₂, v₃, v₄, v₅)

Sebutkan bahwa untuk arah sebaliknya (C→A), graph yang sama berlaku karena edge tak-berarah.

## Tidak Diubah
- `main.tex` — semua TikZ library sudah di-load
- `sistem_navigasi.tex` — tidak ada perubahan
- Tabel-tabel existing di pengolahan_map.tex tetap utuh

## Validasi
- Kompilasi dengan `latexmk` — pastikan tidak ada error
- Verifikasi TikZ figure tidak tumpang tindih
- Verifikasi cross-references (jika ada)
