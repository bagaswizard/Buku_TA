# Global Planner — Penjelasan Lengkap

Dokumen ini menjelaskan cara kerja **global_planner** — algoritma global path planning untuk ROS navigation stack. Sistem menggunakan `global_planner/GlobalPlanner` (dengan fallback `navfn/NavfnROS`). Semua kode sumber ada di `src/global_planner/` dan `src/navfn/`.

---

## Arsitektur

```
move_base
  └── GlobalPlanner (global_planner/GlobalPlanner)
        ├── Expander (base class)
        │     ├── DijkstraExpansion  (default)
        │     └── AStarExpansion
        ├── PotentialCalculator (base class)
        │     └── QuadraticCalculator (default)
        ├── Traceback (base class)
        │     ├── GradientPath (default)
        │     └── GridPath
        └── OrientationFilter
              └── 7 modes (FORWARD, INTERPOLATE, dll)
```

---

## 1. Konsep Dasar — Potential Field Path Planning

Global planner menggunakan algoritma **wavefront expansion** (Dijkstra atau A*) untuk menghitung potential field dari goal menuju start. Setiap cell dalam costmap diberi nilai **potential** — semakin jauh dari goal, semakin tinggi nilainya. Path kemudian diekstrak dengan **gradient descent** dari start menuju goal (menuruni potential).

$$\text{potential}(x, y) = \text{jarak dari goal dalam satuan effective cost}$$

---

## 2. Cost Calculation

### 2.1 Raw Costmap → Effective Cost

File: `dijkstra.h:86-95`

Raw costmap values (0–255) dikonversi ke effective cost untuk planning:

$$c_{\text{eff}} = \text{costmap}[n] \cdot f + c_{\text{neutral}}$$

$$c_{\text{eff}} = \begin{cases} c_{\text{eff}} & \text{if } c_{\text{eff}} < c_{\text{lethal}} \\ c_{\text{lethal}} - 1 & \text{if } c_{\text{eff}} \geq c_{\text{lethal}} \\ c_{\text{lethal}} & \text{if } \text{costmap}[n] \geq c_{\text{lethal}} \text{ and not unknown} \end{cases}$$

Default parameter:
- $f = 3.0$ (`cost_factor`)
- $c_{\text{neutral}} = 50$ (`neutral_cost`)
- $c_{\text{lethal}} = 253$ (`lethal_cost`)

Implementasi:

```cpp
float getCost(unsigned char* costs, int n) {
    float c = costs[n];
    if (c < lethal_cost_ - 1 || (unknown_ && c==255)) {
        c = c * factor_ + neutral_cost_;
        if (c >= lethal_cost_)
            c = lethal_cost_ - 1;
        return c;
    }
    return lethal_cost_;
}
```

Contoh untuk free space (costmap = 0):
$$c_{\text{eff}} = 0 \cdot 3.0 + 50 = 50$$

Untuk cell dengan cost 100:
$$c_{\text{eff}} = 100 \cdot 3.0 + 50 = 350 \rightarrow \text{clamp ke } 252$$

### 2.2 Konfigurasi Sistem

```yaml
GlobalPlanner:
  lethal_cost: 253
  neutral_cost: 66      # lebih tinggi dari default (50)
  cost_factor: 0.55     # lebih rendah dari default (3.0)
```

Perhatikan bahwa konfigurasi sistem menggunakan `cost_factor = 0.55` (jauh lebih rendah dari default 3.0) dan `neutral_cost = 66` (lebih tinggi). Ini membuat gradient cost lebih landai sehingga path lebih smooth.

$$c_{\text{eff}} = \text{costmap}[n] \cdot 0.55 + 66$$

---

## 3. Potential Calculation

### 3.1 PotentialCalculator (Linear)

File: `potential_calculator.h`

Base class — kalkulasi potential linear (Manhattan):

$$P(n) = \min(P_{\text{left}}, P_{\text{right}}, P_{\text{up}}, P_{\text{down}}) + c_{\text{eff}}$$

### 3.2 QuadraticCalculator

File: `quadratic_calculator.cpp`

Kalkulasi potensial kuadratik — aproksimasi Euclidean wavefront yang lebih akurat. Diberikan dua neighbor terkecil dari arah horizontal dan vertikal:

$$t_c = \min(P_{\text{left}}, P_{\text{right}}), \quad t_a = \min(P_{\text{up}}, P_{\text{down}})$$

Selisih: $\Delta = |t_c - t_a|$ (jika $t_c < t_a$, tukar).

**Jika $\Delta \geq c_{\text{eff}}$:**

$$P(n) = t_a + c_{\text{eff}}$$

**Jika $\Delta < c_{\text{eff}}$** (interpolasi kuadratik):

$$d = \frac{\Delta}{c_{\text{eff}}}$$

$$v = -0.2301 \cdot d^2 + 0.5307 \cdot d + 0.7040$$

$$P(n) = t_a + c_{\text{eff}} \cdot v$$

Koefisien polinomial `-0.2301, 0.5307, 0.7040` adalah hasil least-squares fit dari fungsi $\sqrt{1 + d^2}$ (jarak Euclidean sebenarnya dari point source). Kurva ini mendekati:

$$v(d) \approx \sqrt{1 + d^2}$$

dengan galat minimal.

---

## 4. Wavefront Expansion (Path Planning)

### 4.1 DijkstraExpansion

File: `dijkstra.cpp`

Algoritma **Dijkstra** — memperluas wavefront secara seragam ke semua arah dari goal.

**Priority buffer system:** Tiga ring buffer dengan ukuran `PRIORITYBUFSIZE = 10000`.

**Threshold system:** Cells diproses dalam batch berdasarkan priority threshold:

$$\text{threshold}_k = c_{\text{lethal}} + k \cdot \text{priorityIncrement}$$

$$\text{priorityIncrement} = 2 \cdot c_{\text{neutral}}$$

Default: $\text{priorityIncrement} = 2 \cdot 50 = 100$

**Algoritma:**

```
1. Set goal cell → potential = 0
   Jika precise = true (default):
     Distribusi bilinear ke 4 cell sekitar goal:
       P(k)       = 2 * c_neutral * dx * dy
       P(k+1)     = 2 * c_neutral * (1-dx) * dy
       P(k+nx)    = 2 * c_neutral * dx * (1-dy)
       P(k+nx+1)  = 2 * c_neutral * (1-dx) * (1-dy)
     (dx, dy = fractional offset dalam cell)

2. Push 4 cell tetangga ke buffer

3. Loop utama:
   a. Pop cell dari buffer priority saat ini
   b. updateCell(n):
        c = getCost(costs, n)
        if c >= lethal: return  (obstacle — skip)
        P_new = calculatePotential(potential, c, n)
        if P_new < P[n]:
            P[n] = P_new
            Push tetangga dengan cost diagonal:
              le = INVSQRT2 * cost(n-1)    // 0.7071
              re = INVSQRT2 * cost(n+1)
              ue = INVSQRT2 * cost(n-nx)
              de = INVSQRT2 * cost(n+nx)
   c. Jika buffer kosong, naikkan threshold
   d. Ulangi sampai start tercapai atau buffer habis
```

**INVSQRT2 = 0.7071** adalah $1/\sqrt{2}$ — faktor yang mengkompensasi jarak diagonal $\sqrt{2}$ kali lebih jauh dari orthogonal.

### 4.2 AStarExpansion

File: `astar.cpp`

Perbedaan dengan Dijkstra: menggunakan **heuristic** untuk memprioritaskan ekspansi ke arah goal:

$$\text{priority} = P(n) + \text{ManhattanDistance}(n, \text{goal}) \cdot c_{\text{neutral}}$$

$$\text{ManhattanDistance}(x, y) = |x_{\text{goal}} - x| + |y_{\text{goal}} - y|$$

Heuristic ini membuat A* lebih cepat dari Dijkstra karena mengeksplorasi lebih sedikit cell, terutama ketika goal jauh.

Dijkstra berekspansi seperti lingkaran dari goal, A* berekspansi seperti ellips yang condong ke start:

```
Dijkstra:    A*:
  ###         ###
 #####       #####
 ###G#       ##G##
 #####       #####
  ###         ###
   #           #
   S           S
```

### 4.3 clearEndpoint

Setelah potential selesai, area 2×2 cell di sekitar goal di-clear:

```cpp
void clearEndpoint(unsigned char* costs, float* potential, int gx, int gy, int s) {
    int startCell = toIndex(gx, gy);
    for(int i=-s; i<=s; i++)
      for(int j=-s; j<=s; j++){
        int n = startCell + i + nx_*j;
        if(potential[n] < POT_HIGH) continue;  // skip if already set
        float c = costs[n] + neutral_cost_;
        float pot = p_calc_->calculatePotential(potential, c, n);
        potential[n] = pot;
      }
}
```

Ini memastikan gradient path bisa menemukan jalan ke goal area meskipun goal berada di obstacle.

---

## 5. Path Extraction (Traceback)

Setelah potential field terbentuk, path diekstrak dari **start menuju goal** dengan mengikuti gradient potential (dari potensial tinggi ke rendah).

### 5.1 GridPath

File: `grid_path.cpp`

8-neighbor steepest descent — sederhana dan cepat:

```
current = start
path = [current]

while current != goal:
    P_min = infinity
    for each tetangga (xd, yd) dalam [-1, 0, 1]:
        if potential[tetangga] < P_min:
            P_min = potential[tetangga]
            next = tetangga
    path.append(next)
    current = next
```

Menghasilkan path **grid-aligned** (hanya pada batas integer cell). Tidak mulus secara sub-cell.

### 5.2 GradientPath

File: `gradient_path.cpp`

**Default — menghasilkan path smooth dengan interpolasi sub-cell.**

**pathStep = 0.5** cell per langkah.

#### 5.2.1 Gradient Computation (`gradCell`)

Central difference approximation:

$$g_x = \frac{P(x-1, y) - P(x+1, y)}{2}$$

$$g_y = \frac{P(x, y-1) - P(x, y+1)}{2}$$

Normalisasi:

$$\hat{g}_x = \frac{g_x}{\sqrt{g_x^2 + g_y^2}}, \quad \hat{g}_y = \frac{g_y}{\sqrt{g_x^2 + g_y^2}}$$

Untuk cell yang berada di obstacle (potential = `POT_HIGH`), gradient dihitung dari tetangga terdekat yang valid.

#### 5.2.2 Bilinear Interpolation

Karena posisi sub-cell $p = (x_{\text{int}} + d_x, y_{\text{int}} + d_y)$:

$$g_x(p) = (1-d_y) \cdot ((1-d_x) \cdot g_x(i,j) + d_x \cdot g_x(i+1,j)) + d_y \cdot ((1-d_x) \cdot g_x(i,j+1) + d_x \cdot g_x(i+1,j+1))$$

$$g_y(p) = (1-d_y) \cdot ((1-d_x) \cdot g_y(i,j) + d_x \cdot g_y(i+1,j)) + d_y \cdot ((1-d_x) \cdot g_y(i,j+1) + d_x \cdot g_y(i+1,j+1))$$

#### 5.2.3 Path Step

$$\text{step} = \frac{\text{pathStep}}{\sqrt{g_x(p)^2 + g_y(p)^2}}$$

$$d_x \gets d_x + g_x(p) \cdot \text{step}, \quad d_y \gets d_y + g_y(p) \cdot \text{step}$$

**Cell overflow:** Ketika $|d_x| \geq 1.0$ atau $|d_y| \geq 1.0$, pindah ke cell tetangga:

```
int new_i = i + (int)round(dx_overflow)
int new_j = j + (int)round(dy_overflow)
dx -= round(dx_overflow)
dy -= round(dy_overflow)
```

---

## 6. Orientation Filter

File: `orientation_filter.cpp`

Menambahkan orientasi (yaw) ke setiap path point.

### Modes

| Mode | Nilai | Deskripsi |
|---|---|---|
| `NONE` | 0 | Tidak ada orientasi |
| `FORWARD` | 1 | Orientasi = arah pergerakan maju |
| `INTERPOLATE` | 2 | Interpolasi linear dari start ke goal |
| `FORWARDTHENINTERPOLATE` | 3 | FORWARD lalu INTERPOLATE di akhir |
| `BACKWARD` | 4 | Maju + 180° |
| `LEFTWARD` | 5 | Maju − 90° |
| `RIGHTWARD` | 6 | Maju + 90° |

**FORWARD mode:**

$$\theta_k = \text{atan2}(y_{k+w} - y_{k-w}, x_{k+w} - x_{k-w})$$

dimana $w$ adalah `orientation_window_size` (default 1, jadi gunakan tetangga terdekat).

**INTERPOLATE mode:**

$$\theta_k = \theta_{\text{start}} + \frac{k}{N-1} \cdot (\theta_{\text{end}} - \theta_{\text{start}})$$

Konfigurasi sistem: `orientation_mode: 2` (INTERPOLATE).

---

## 7. Alur Data End-to-End

```
move_base menerima goal (PoseStamped)
    │
    ▼
GlobalPlanner::makePlan(start, goal, plan)
    │
    ├── 1. worldToMap(start, &start_x, &start_y)
    │         Jika old_navfn_behavior=false:
    │           mx = (wx - origin_x) / resolution - 0.5   (sub-cell precision)
    │         Jika true:
    │           mx = (wx - origin_x) / resolution          (integer cell)
    │
    ├── 2. outlineMap() — set cell border ke lethal (jika enabled)
    │
    ├── 3. planner_->calculatePotentials(costs, start_x, start_y,
    │                                      goal_x, goal_y, max_steps)
    │         │
    │         ├── DijkstraExpansion::calculatePotentials()
    │         │     │
    │         │     ├── Init: set goal → potential = 0
    │         │     │   (bilinear distribution jika precise)
    │         │     │
    │         │     ├── Priority queue loop:
    │         │     │     updateCell(n):
    │         │     │       c = getCost(costs, n)
    │         │     │       if c >= lethal: skip
    │         │     │       P_new = calculatePotential(c, n)
    │         │     │       if P_new < P[n]:
    │         │     │           set P[n] = P_new
    │         │     │           push neighbors (cost scaled by INVSQRT2)
    │         │     │
    │         │     └── Selesai ketika start tercapai
    │         │
    │         └── potential_array: float[nx * ny]
    │               Setiap cell berisi potential dari goal
    │               POT_HIGH = 1e10 untuk unreachable
    │
    ├── 4. clearEndpoint() — isi area 2×2 di sekitar goal
    │
    ├── 5. path_maker_->getPath(potential, start_x, start_y,
    │                              goal_x, goal_y, path_map)
    │         │
    │         ├── GradientPath (default):
    │         │     Ikuti negative gradient dari goal ke start
    │         │     Langkah 0.5 cell dengan interpolasi bilinear
    │         │
    │         └── GridPath:
    │               Steepest descent 8-neighbor
    │
    ├── 6. mapToWorld() untuk setiap path point
    │
    └── 7. orientation_filter_->processPath(plan)
              Sesuai orientation_mode (default: FORWARD)
              Jika INTERPOLATE: atan2, lalu smoothing
    │
    ▼
Plan (nav_msgs::Path) dikirim ke move_base
    │
    ▼
DWAPlannerROS mengikuti path (local planner)
```

---

## 8. Parameter Global Planner

### 8.1 Dari Config (`config/global_planner.yaml`)

```yaml
GlobalPlanner:
  allow_unknown: true
  default_tolerance: 0.15
  visualize_potential: true
  use_dijkstra: true
  use_quadratic: true
  use_grid_path: false
  old_navfn_behavior: true
  lethal_cost: 253
  neutral_cost: 66
  cost_factor: 0.55
  orientation_mode: 2
  orientation_window_size: 1
  outline_map: true
```

### 8.2 Interpretasi Parameter

| Parameter | Nilai | Efek |
|---|---|---|
| `use_dijkstra: true` | Dijkstra | Ekspansi seragam ke semua arah (default) |
| `use_quadratic: true` | Quadratic | Interpolasi kuadratik untuk potential Euclidean |
| `use_grid_path: false` | GradientPath | Path smooth dengan sub-cell interpolation |
| `old_navfn_behavior: true` | Navfn compat | `convert_offset_=0`, integer cell, tanpa clearEndpoint |
| `allow_unknown: true` | Unknown passable | Robot bisa melewati area unknown (cost 255) |
| `default_tolerance: 0.15` | 15 cm | Toleransi goal position |
| `cost_factor: 0.55` | Rendah | Gradient cost landai → path lebih smooth |
| `neutral_cost: 66` | Tinggi | Base cost per cell lebih tinggi |
| `lethal_cost: 253` | 253 | Threshold obstacle |
| `orientation_mode: 2` | INTERPOLATE | Orientasi diinterpolasi linear |
| `outline_map: true` | Border lethal | Setiap cell di border map dianggap obstacle |

### 8.3 Rumus Cost dengan Konfigurasi Sistem

$$c_{\text{eff}} = \text{costmap}[n] \cdot 0.55 + 66$$

| Skenario | costmap[n] | $c_{\text{eff}}$ |
|---|---|---|
| Free space | 0 | 66 |
| Transit area (cost 1) | 1 | 66.55 |
| Expansion buffer (cost 5) | 5 | 68.75 |
| Inflasi ringan (cost 50) | 50 | 93.5 |
| Inflasi berat (cost 200) | 200 | 176 |
| Lethal obstacle | 253+ | 253 (obstacle) |
| Unknown | 255 | 255 (passable jika allow_unknown) |

---

## 9. Perbandingan global_planner vs navfn

| Aspek | `global_planner` | `navfn` |
|---|---|---|
| Plugin name | `global_planner/GlobalPlanner` | `navfn/NavfnROS` |
| Arsitektur | Modular (Expander, Calculator, Traceback terpisah) | Monolitik (semua di NavFn) |
| Cost mapping | $c \cdot f + c_n$ (configurable) | $c \cdot 0.8 + 50$ (hardcoded) |
| Sub-cell precision | Ya (convert_offset=0.5) | Tidak |
| Orientation | 7 modes | Tidak ada |
| A* heuristic | Manhattan distance | Euclidean distance |
| Dynamic reconfigure | Ya (GlobalPlanner.cfg) | Tidak |

### `old_navfn_behavior: true` mengaktifkan:

1. `convert_offset_ = 0.0` — koordinat integer cell (seperti navfn)
2. **Tidak** `setPreciseStart(true)` — tanpa bilinear initial potential
3. **Tidak** `clearEndpoint()` — tanpa explicit goal area clearing
4. Goal pose ditambahkan di akhir plan

---

## 10. Kompleksitas

| Operasi | Kompleksitas | Keterangan |
|---|---|---|
| Cost calculation | $O(1)$ per cell lookup |
| Dijkstra expansion | $O(N \log N)$ | $N$ = jumlah cell reachable |
| A* expansion | $O(N \log N)$ | Biasanya $N$ lebih kecil dari Dijkstra (heuristic) |
| Gradient path | $O(L)$ | $L$ = panjang path dalam steps |
| Grid path | $O(L)$ | $L$ = panjang path dalam cells |
| Orientation filter | $O(L)$ | Per point atan2 atau interpolasi |
| **Total** | $O(N \log N + L)$ | Didominasi oleh wavefront expansion |

---

## 11. Referensi File

| File | Isi |
|---|---|
| `planner_core.h/.cpp` | GlobalPlanner class: makePlan, orchestrasi seluruh pipeline |
| `dijkstra.h/.cpp` | DijkstraExpansion: wavefront propagation dengan priority buffer |
| `astar.h/.cpp` | AStarExpansion: Dijkstra dengan heuristic (Manhattan distance) |
| `expander.h` | Base class Expander: getCost, clearEndpoint, setup |
| `potential_calculator.h` | PotentialCalculator: linear potential (base class) |
| `quadratic_calculator.cpp` | QuadraticCalculator: interpolasi kuadratik (Euclidean approx) |
| `gradient_path.h/.cpp` | GradientPath: path extraction via gradient descent (sub-cell) |
| `grid_path.h/.cpp` | GridPath: path extraction via steepest descent 8-neighbor |
| `traceback.h` | Base class Traceback |
| `orientation_filter.h/.cpp` | OrientationFilter: 7 modes untuk orientasi path point |
| `navfn/src/navfn.cpp` | Implementasi NavFn asli (navfn behavior) |
| `navfn/src/navfn_ros.cpp` | ROS wrapper NavfnROS |
| `cfg/GlobalPlanner.cfg` | Dynamic reconfigure parameter definitions |
