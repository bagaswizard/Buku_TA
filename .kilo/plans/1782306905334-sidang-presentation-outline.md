# Plan: Streamline Region Switcher Flowchart

## Target
`bab/Metodologi/tikz_region_switcher.tex` — ganti flowchart region switcher dengan desain yang lebih ringkas.

## Diagram Baru

```
Mulai
  ↓
ROI window scan di transition costmap
Hitung dual centroids (T & E)
  ↓
[Robot di sel transisi?]
  ├── Tidak → ↺ loop back
  └── Ya
      ↓
    ICP disabled
      ↓
    [Pitch trigger atau timer selesai?]
      ├── Tidak → ↺ loop back
      └── Ya
          ↓
        Lakukan lompatan ke centroid E
          ↓
        Ganti pose
        q_new = q_region · q_current
          ↓
        Selesai
```

## Yang Dihapus Dibanding Sebelumnya
| Dihapus | Alasan |
|---|---|
| `Terima transition costmap terisolasi` | Tidak perlu box terpisah, ROI scan sudah menyiratkan sumber data |
| `Startup < 5 s? ICM belum siap? Cooldown aktif?` | Guard checks tidak perlu di flowchart utama |
| `20 Hz checkTimerCallback` | Detail implementasi, dihilangkan dari diagram |
| `Publish /initialpose, /transition_jumped` | Digabung implisit di "Lakukan lompatan" |

## Yang Diubah
| Lama | Baru |
|---|---|
| `isTransitionCost(c)? c ∈ {1,2}` | `Robot di sel transisi?` — lebih deskriptif |
| `Waiting Mode` sebagai process box + ICP disabled di samping | ICP disabled sebagai process box sebelum waiting decision |
| `executeJump` → publish → selesai | `Lakukan lompatan ke centroid E` → `Ganti pose` → `Selesai` — lebih sederhana |

## Kode Tikz Pengganti

```latex
\begin{tikzpicture}[
    node distance=1.0cm and 2.0cm,
    startstop/.style={
        rectangle, rounded corners=3pt, minimum width=2.8cm, minimum height=0.8cm,
        align=center, draw, fill=colTransCost, font=\small\bfseries
    },
    process/.style={
        rectangle, rounded corners=2pt, minimum width=5.0cm, minimum height=0.8cm,
        align=center, draw, font=\small
    },
    decision/.style={
        diamond, aspect=1.5, minimum width=3.5cm, minimum height=1cm,
        align=center, draw, fill=colTransCost!40, font=\small
    },
    arrow/.style={thick, ->, >=Stealth}
]

\definecolor{colTransCost}{HTML}{E1BEE7}

% --- Main flow ---
\node[startstop] (start) {Mulai};
\node[process, below=of start] (roi) {ROI \emph{window scan} di \emph{transition costmap}\\[2pt]\footnotesize Hitung \emph{dual centroids} ($T$ \& $E$)};
\node[decision, below=of roi, yshift=-0.2cm] (trans) {Robot di\\sel transisi?};
\node[process, below=of trans] (icp) {ICP \emph{disabled}};
\node[decision, below=of icp, yshift=-0.2cm] (wait) {Pitch \emph{trigger} atau\\\emph{timer} selesai?};
\node[process, below=of wait] (jump) {Lakukan lompatan ke centroid $E$};
\node[process, below=of jump] (pose) {Ganti pose\\[2pt]\footnotesize $\mathbf{q}_{\text{new}} = \mathbf{q}_{\text{region}} \cdot \mathbf{q}_{\text{current}}$};
\node[startstop, below=of pose] (end) {Selesai};

% --- Forward arrows ---
\draw[arrow] (start) -- (roi);
\draw[arrow] (roi) -- (trans);
\draw[arrow] (trans) -- node[right] {Ya} (icp);
\draw[arrow] (icp) -- (wait);
\draw[arrow] (wait) -- node[right] {Ya} (jump);
\draw[arrow] (jump) -- (pose);
\draw[arrow] (pose) -- (end);

% --- Loop back: Tidak dari trans → back to trans check ---
\draw[arrow] (trans.west) -- node[above] {Tidak} ++(-2.8,0) |- (trans.north);

% --- Loop back: Tidak dari wait → back to wait check ---
\draw[arrow] (wait.west) -- node[above] {Tidak} ++(-2.8,0) |- (wait.north);
\end{tikzpicture}
```

## File yang Diubah
- `bab/Metodologi/tikz_region_switcher.tex` — ganti seluruh isi (69 baris → 50 baris)
