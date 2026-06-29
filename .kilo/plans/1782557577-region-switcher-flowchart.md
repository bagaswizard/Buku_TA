# Plan: Flowchart Horizontal per Subsection Bab 3

## Objective
Buat 4 flowchart TikZ horizontal untuk masing-masing subsection di Bab 3 (sistem_navigasi.tex): ICP, Global Planner, Path Router, DWA.

## Files to Create (4 TikZ files in `bab/Metodologi/`)

### 1. `tikz_icp_flow.tex`
- Warna: cyan (`colLokalisasi`, #B2EBF2)
- Node (5): LiDAR Scan → KNN Lookup (precomputed) → Scan Matching → SVD Solver → Pose (x, y, θ)
- Insert: setelah `\subsection{Lokalisasi Iterative Closest Point (ICP)}` line 55

### 2. `tikz_global_planner_flow.tex`
- Warna: hijau (`#C8E6C9`)
- Node (6): Costmap + Goal → Cost Calculation (c_eff) → Quadratic Potential → A* Expansion → Gradient Path → Waypoints / Path
- Insert: setelah `\subsection{Global Planner}` line 683

### 3. `tikz_path_router_flow.tex`
- Warna: ungu (`colTransCost`, #E1BEE7)
- Node (5): Multi-Region Goal → Graph Nodes (v₀-v₅) → Build Route (A→B→C) → Sequential Sub-Goals → Send to Global Planner
- Insert: setelah `\subsection{Path Router}` line 852

### 4. `tikz_dwa_flow.tex`
- Warna: oranye (`#FFE0B2`)
- Node (6): Path + Costmap + Pose → Velocity Sampling → Trajectory Sim → 7 Critics Scoring → Select Best → Velocity (v_x, v_y, ω)
- Insert: setelah `\subsection{Local Planner DWA}` line 895

## File to Edit (1 file)

### `sistem_navigasi.tex`
Tambah `\input` dalam `figure` environment setelah masing-masing `\subsection` header:

```latex
\begin{figure}[H]
\centering
\input{bab/Metodologi/tikz_icp_flow.tex}
\caption{Diagram alir proses ICP}
\label{fig:icp_flow}
\end{figure}
```

(Pattern sama untuk keempatnya, dengan label unik: `fig:icp_flow`, `fig:global_planner_flow`, `fig:path_router_flow`, `fig:dwa_flow`)

## Style TikZ
- Kotak: `rectangle, draw, rounded corners=3pt, minimum width=2.5cm, minimum height=1cm, align=center, font=\small`
- Panah: `->`, `>=Stealth`
- Label input/output: `font=\footnotesize\itshape` di bawah node
- Kecilkan `node distance` agar muat horizontal (0.8cm antar node)

## Validation
- `latexmk -pdf` — pastikan semua 4 figure terkompilasi tanpa error
- Verifikasi caption konsisten antar keempat figure
- Verifikasi label unik tidak bentrok
