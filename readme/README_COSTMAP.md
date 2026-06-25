# Costmap2D — Penjelasan Lengkap

Dokumen ini menjelaskan cara kerja **costmap_2d** — framework ROS untuk representasi grid bernilai biaya (cost) yang digunakan dalam navigasi robot. Semua kode sumber ada di `src/costmap_2d/`.

---

## Arsitektur

```
Costmap2DROS        (ROS node wrapper)
  └── LayeredCostmap  (aggregator)
        ├── Costmap2D (master grid)
        └── Layer plugins (via pluginlib)
              ├── StaticLayer      — dari /map
              ├── ObstacleLayer    — dari /scan atau point cloud
              ├── VoxelLayer       — variant 3D dari ObstacleLayer
              ├── InflationLayer   — inflasi obstacle dengan gradient cost
              ├── TransitionLayer  — kustom: data transisi area
              └── TransitionExpansionLayer — kustom: perluasan transisi
```

---

## 1. Core Data Structure: `Costmap2D`

### 1.1 Grid Representation

File: `costmap_2d.h` / `costmap_2d.cpp`

Costmap2D menyimpan grid 2D sebagai array 1D bertipe `unsigned char`:

```cpp
unsigned char* costmap_;   // array of size size_x_ * size_y_
```

Setiap cell menyimpan nilai 0–255 yang merepresentasikan tingkat bahaya:

| Nama Konstanta | Nilai | Makna |
|---|---|---|---|
| `NO_INFORMATION` | 255 | Tidak diketahui (unknown) |
| `LETHAL_OBSTACLE` | 254 | Obstacle mematikan — robot tidak boleh masuk |
| `INSCRIBED_INFLATED_OBSTACLE` | 253 | Batas terluar inflasi obstacle |
| `FREE_SPACE` | 0 | Ruang bebas — aman dilalui |
| `TRANSITION_EXPANSION` | 5 | Buffer area transisi — **navigable** (khusus layer transisi) |
| `TRANSITION_MAIN_DATA` | 1 | Garis transisi utama — **navigable** (khusus layer transisi) |

Nilai 2–4 dan 6–252 digunakan untuk gradient cost hasil inflasi: semakin tinggi nilainya, semakin dekat ke obstacle. Nilai 1 dan 5 dicadangkan untuk data transisi, dan **bersifat navigable** (aman dilalui robot) karena berada di bawah 253.

### 1.2 Indeks Grid

Konversi dari koordinat grid 2D $(m_x, m_y)$ ke flat index 1D:

$$i = m_y \cdot W + m_x$$

dimana $W$ adalah lebar grid (jumlah cell per baris).

### 1.3 Koordinat Dunia ↔ Grid

Diberikan origin grid di $(o_x, o_y)$ dan resolusi $r$ (meter per cell):

**World → Grid:**

$$m_x = \left\lfloor \frac{w_x - o_x}{r} \right\rfloor, \qquad m_y = \left\lfloor \frac{w_y - o_y}{r} \right\rfloor$$

**Grid → World** (pusat cell):

$$w_x = o_x + \left(m_x + \frac{1}{2}\right) \cdot r, \qquad w_y = o_y + \left(m_y + \frac{1}{2}\right) \cdot r$$

Implementasi (`costmap_2d.cpp`):

```cpp
void mapToWorld(unsigned int mx, unsigned int my, double& wx, double& wy) const {
    wx = origin_x_ + (mx + 0.5) * resolution_;
    wy = origin_y_ + (my + 0.5) * resolution_;
}

void worldToMap(double wx, double wy, unsigned int& mx, unsigned int& my) const {
    mx = (int)floor((wx - origin_x_) / resolution_);
    my = (int)floor((wy - origin_y_) / resolution_);
}
```

### 1.4 Rolling Window

Untuk local costmap yang bergerak mengikuti robot, origin grid digeser:

$$\Delta_x = \lfloor \text{new\_origin}_x - \text{old\_origin}_x \rfloor, \quad \Delta_y = \lfloor \text{new\_origin}_y - \text{old\_origin}_y \rfloor$$

Array costmap digeser sebesar $(\Delta_x, \Delta_y)$ dan cell baru diisi dengan `NO_INFORMATION`.

---

## 2. Layered Architecture

### 2.1 Layer Plugin Interface

File: `layer.h`

Setiap plugin layer mengimplementasikan dua metode utama:

**`updateBounds()`** — Mendeklarasikan region yang berubah:

```cpp
virtual void updateBounds(
    double robot_x, double robot_y, double robot_yaw,
    double* min_x, double* min_y, double* max_x, double* max_y
);
```

Layer menghitung bounding box (dalam meter) dari area yang perlu diperbarui. LayeredCostmap mengambil union dari semua bounding box.

**`updateCosts()`** — Menulis data cost ke master grid:

```cpp
virtual void updateCosts(
    Costmap2D& master_grid,
    int min_i, int min_j, int max_i, int max_j
);
```

Layer menulis nilai cost ke dalam region yang diminta pada master grid.

### 2.2 CostmapLayer — Strategi Penggabungan

File: `costmap_layer.cpp`

`CostmapLayer` adalah base class untuk layer yang memiliki Costmap2D internal sendiri. Empat strategi untuk menggabungkan layer ke master:

**Overwrite (True):** Timpa semua cell tanpa terkecuali:

$$C_{\text{master}}(i,j) = C_{\text{layer}}(i,j)$$

**Overwrite (Skip Unknown):** Timpa hanya jika layer bukan NO_INFORMATION:

$$C_{\text{master}}(i,j) = \begin{cases} C_{\text{layer}}(i,j) & \text{if } C_{\text{layer}}(i,j) \neq 255 \\ C_{\text{master}}(i,j) & \text{otherwise} \end{cases}$$

**Maximum:** Ambil nilai maksimum:

$$C_{\text{master}}(i,j) = \max\left(C_{\text{master}}(i,j),\; C_{\text{layer}}(i,j)\right)$$

**Addition:** Jumlahkan, batasi hingga 252 (sebelum INSCRIBED_INFLATED_OBSTACLE):

$$C_{\text{master}}(i,j) = \min\left(C_{\text{master}}(i,j) + C_{\text{layer}}(i,j),\; 252\right)$$

### 2.3 LayeredCostmap — Orchestrator

File: `layered_costmap.cpp`

Alur `updateMap(robot_x, robot_y, robot_yaw)`:

```
1. Jika rolling window, geser origin ke pusat robot
2. Reset bounds: min_x = max_x = robot_x, min_y = max_y = robot_y
3. Untuk setiap layer (urut):
     layer->updateBounds(robot_x, robot_y, robot_yaw, &min_x, &min_y, &max_x, &max_y)
     → perluas bounds sesuai kebutuhan layer
4. Konversi bounds ke cell coordinates:
     worldToMapEnforceBounds(min_x, min_y, &cell_min_x, &cell_min_y)
     worldToMapEnforceBounds(max_x, max_y, &cell_max_x, &cell_max_y)
5. Reset region [cell_min..cell_max] ke nilai default
6. Untuk setiap layer (urut):
     layer->updateCosts(master, cell_min_x, cell_min_y, cell_max_x, cell_max_y)
     → layer menulis cost ke master
```

Urutan layer penting: layer belakang menimpa atau menambah layer depan.

---

## 3. Static Layer

File: plugin `costmap_2d::StaticLayer`

Memuat peta statis dari topic `/map` (tipe `nav_msgs::OccupancyGrid`).

Konversi nilai OccupancyGrid (−1, 0–100) ke costmap internal (0–255):

$$C_{\text{internal}} = \begin{cases} 255 & \text{if } OG = -1 \text{ (unknown)} \\ 0 & \text{if } OG = 0 \text{ (free)} \\ 254 & \text{if } OG \geq 100 \text{ (occupied)} \\ 253 & \text{otherwise} \end{cases}$$

Strategi penggabungan: **Overwrite (Skip Unknown)** — hanya area yang diketahui peta yang ditulis.

---

## 4. Obstacle Layer

File: plugin `costmap_2d::ObstacleLayer`

Memproses data sensor (LaserScan atau PointCloud) untuk menandai obstacle.

### 4.1 Marking

Untuk setiap beam laser dengan range $r$ dan sudut $\theta$:

1. Hitung endpoint dalam frame sensor: $(r\cos\theta,\; r\sin\theta)$
2. Transform ke frame map via TF
3. Konversi ke cell: $(m_x, m_y) = \text{worldToMap}(x, y)$
4. Set cell ke `LETHAL_OBSTACLE` (254)

### 4.2 Clearing (Raytracing)

Gunakan algoritma **Bresenham 2D** untuk menggambar garis dari robot ke endpoint sensor. Semua cell yang dilewati garis (sebelum endpoint) di-clear:

$$C_{\text{master}}(m_x, m_y) = 0 \quad \forall \text{cell di sepanjang ray} \text{ (kecuali endpoint)}$$

### 4.3 Bresenham 2D Raytracing

File: `costmap_2d.h:359–412`

Algoritma Bresenham memilih pixel-pixel yang mendekati garis lurus antara dua titik grid. Untuk setiap langkah, algoritma memutuskan apakah akan bergerak di sumbu x, y, atau keduanya berdasarkan error accumulator:

Diberikan titik awal $(x_0, y_0)$ dan titik akhir $(x_1, y_1)$:

$$\Delta_x = |x_1 - x_0|, \quad \Delta_y = |y_1 - y_0|$$

$$\text{err} = \Delta_x - \Delta_y, \quad s_x = \text{sign}(x_1 - x_0), \quad s_y = \text{sign}(y_1 - y_0)$$

Perulangan:

```
while (x != x1 || y != y1):
    e2 = 2 * err
    if e2 > -Δy: err -= Δy, x += sx
    if e2 < Δx:  err += Δx, y += sy
    raytrace_function(x, y)
```

Kelebihan: hanya menggunakan integer arithmetic — cepat dan deterministik.

### 4.4 Parameter

| Parameter | Fungsi |
|---|---|
| `observation_sources` | Daftar topic sensor |
| `<source>/data_type` | `LaserScan` atau `PointCloud` |
| `<source>/topic` | Topic sensor |
| `<source>/marking` | Apakah source ini menandai obstacle? |
| `<source>/clearing` | Apakah source ini melakukan clearing? |
| `obstacle_range` | Jarak maksimum obstacle dianggap |
| `raytrace_range` | Jarak maksimum raytracing |

---

## 5. Inflation Layer

File: plugin `costmap_2d::InflationLayer`

Layer ini memperluas obstacle dengan gradient cost, sehingga perencana path dapat menjaga jarak dari obstacle.

### 5.1 Algoritma Inflasi

Untuk setiap obstacle cell, terapkan cost ke semua cell dalam radius inflasi $R$.

Cost pada jarak $d$ dari obstacle dihitung dengan fungsi eksponensial:

$$C(d) = \begin{cases} 253 \cdot e^{-\alpha \cdot (d - r_{\text{inscribed}})} & \text{if } d \leq R \\ 0 & \text{otherwise} \end{cases}$$

Atau dalam bentuk weight:

$$C(d) = 252 \cdot \left( e^{-\alpha \cdot (d - r_{\text{inscribed}})} \right)$$

dimana:
- $d$ = jarak Euclidean dari cell ke obstacle terdekat
- $R$ = inflation radius (jarak maksimum inflasi)
- $r_{\text{inscribed}}$ = inscribed radius (radius robot, cost = 253 pada jarak ini)
- $\alpha$ = scaling factor (mengontrol kecuraman kurva cost)

Cost dibulatkan ke integer 0–252 (253 digunakan untuk batas INSCRIBED_INFLATED_OBSTACLE).

### 5.2 Sel Cells Inflasi

Implementasi menggunakan **priority queue (Dijkstra)** untuk efisiensi:

```
1. Untuk setiap LETHAL_OBSTACLE cell, push ke queue dengan priority = 0
2. Pop cell dengan priority tertinggi (jarak terdekat)
3. Untuk setiap tetangga dalam radius inflasi:
     d = jarak Euclidean dari obstacle cell
     C(d) = hitung cost sesuai rumus
     Jika cost yang dihitung > cost yang ada, update dan push tetangga
4. Ulangi sampai queue kosong
```

Kompleksitas: $O(N \log N)$ dimana $N$ adalah jumlah cell dalam area inflasi.

### 5.3 Parameter

| Parameter | Default | Fungsi |
|---|---|---|
| `inflation_radius` | 0.55 m | Radius maksimum inflasi |
| `cost_scaling_factor` | 10.0 | $\alpha$ — faktor skala gradient |

### 5.4 Kurva Cost

```
Cost
  ^
  | 253 ────────── INSCRIBED_INFLATED_OBSTACLE (d = r_inscribed)
  |       \
  |        \        C(d) = 253 * exp(-α * (d - r_inscribed))
  |         \
  |          \
  |           \
  |            \
  |             \
  0 ─────────────┴───────────────────> d
  0            R                (meter)
          inflation_radius
```

---

## 6. Transition Layer (`costmap_2d::TransitionLayer`)

File: `plugins/transition_layer.cpp`, `include/costmap_2d/transition_layer.h`

### 6.1 Tujuan

TransitionLayer adalah **custom plugin** yang menambahkan data **area transisi** (doorway/pintu antara dua ruangan) ke dalam costmap. Data ini digunakan oleh node `costmap_jumper` untuk mendeteksi kapan robot melewati pintu dan melakukan "lompatan" pose antar area.

Berbeda dengan layer standar yang membaca dari `/map`, layer ini membaca dari topic terpisah:

```
/multimap_server/maps/transition/localization/map
```

### 6.2 Nilai Cost Khusus

TransitionLayer menggunakan nilai cost **rendah** agar **navigable** — robot dan path planner dapat melewati area ini:

| Konstanta | Nilai | Makna |
|---|---|---|
| `TRANSITION_EXPANSION` | 5 | Buffer hasil ekspansi (dari TransitionExpansionLayer) — navigable |
| `TRANSITION_MAIN_DATA` | 1 | Data transisi utama — area pintu — navigable |
| `TRANSITION_LETHAL` | 1 | Sama dengan MAIN_DATA (tidak dibedakan) |
| `TRANSITION_MAX_INTERMEDIATE` | 1 | Semua pixel non-255 dianggap sama |

Nilai 1 dan 5 sengaja dibuat **sangat rendah** agar tidak mempengaruhi path planning. Fungsinya murni sebagai **marker** untuk dideteksi oleh `costmap_jumper`. Layer `layer_publisher.cpp` yang menangani visualisasi dengan memetakan nilai-nilai ini ke OG 100 dan 50 agar terlihat di RViz.

### 6.3 Interpretasi Pixel PGM

File PGM transisi adalah grayscale (0–255). Konversi ke nilai cost internal:

$$C_{\text{internal}} = \begin{cases} 1 & \text{if pixel} = 255 \text{ (data transisi)} \\ \text{NO\_INFORMATION} & \text{if track\_unknown\_space and value = unknown} \\ 0 & \text{if pixel} = 0 \text{ (free)} \\ 1 & \text{if pixel} \geq 100 \text{ (occupied)} \\ 1 & \text{otherwise (all scaled to 1)} \end{cases}$$

Fungsi `interpretValue()` di `transition_layer.cpp:179`:

```cpp
unsigned char TransitionLayer::interpretValue(unsigned char value) {
    if (value == 255)
        return TRANSITION_MAIN_DATA;     // 1
    else if (track_unknown_space_ && value == unknown_cost_value_)
        return NO_INFORMATION;            // 255
    else if (!track_unknown_space_ && value == unknown_cost_value_)
        return FREE_SPACE;               // 0
    else if (value == 0)
        return FREE_SPACE;               // 0
    else if (value >= lethal_threshold_)
        return TRANSITION_LETHAL;        // 1
    // Scale intermediate values - but MAX_INTERMEDIATE = 1, so all return 1
    return 1;
}
```

Catatan: Karena `TRANSITION_MAX_INTERMEDIATE = 1`, semua pixel non-255 dan non-0 menghasilkan **1**. Tidak ada gradient — semuanya marker seragam.

### 6.4 Alur Kerja

```
1. Subscribe ke topic transisi (/multimap_server/...)
2. Terima OccupancyGrid pertama → resize layer/costmap
3. Iterasi semua cell:
     pixel 255 → cost 1 (TRANSITION_MAIN_DATA)
     pixel ≥ 100 → cost 1 (TRANSITION_LETHAL)
     pixel 0 → cost 0 (FREE_SPACE)
     lainnya → cost 1
4. updateBounds(): deklarasi update untuk seluruh area layer
5. updateCosts(): copy semua cost ke master grid
     Jika use_maximum_ = true: master = max(master, layer)
     Jika false: master = layer (overwrite)
```

### 6.5 Parameter Konfigurasi

| Parameter | Default | Fungsi |
|---|---|---|
| `map_topic` | `"transition_map"` | Topic sumber data transisi |
| `lethal_cost_threshold` | 100 | Threshold pixel dianggap lethal |
| `track_unknown_space` | true | Apakah unknown space dilacak |
| `use_maximum` | true | Strategi merge: max atau overwrite |
| `transition_expansion` | 0.0 | Radius ekspansi (sekarang di-handle ExpansionLayer) |
| `publish_grid` | false | Publikasi grid individual untuk debugging |

### 6.6 Contoh Data Transisi

File `multimap_server/maps/transition/transition_map.yaml`:

```yaml
image: transition_map.pgm
resolution: 0.01
origin: [-2.56, -2.56, 0.0]
transitions:
  - {first_pixel_A: [354, 206], first_pixel_B: [106, 328], pair: 0}
  - {first_pixel_A: [106, 436], first_pixel_B: [135, 187], pair: 1}
initial_pose: [375, 75]
region_orientations:
  C: {x: 0.0, y: 0.0, z: -0.7046, w: 0.7096}
```

Field `transitions` mendefinisikan pasangan area transisi:
- `pair: 0` menghubungkan pixel A (354,206) dengan pixel B (106,328) — dua sisi pintu yang berbeda (area berbeda)
- `first_pixel_A` dan `first_pixel_B` adalah titik awal (seed) untuk tracing garis transisi
- Saat robot menyentuh garis A, `costmap_jumper` akan memindahkannya ke posisi yang sesuai di garis B

Pixel 255 dalam PGM menandai area transisi — inilah yang menjadi `TRANSITION_MAIN_DATA (1)` dalam costmap.

---

## 7. Transition Expansion Layer (`costmap_2d::TransitionExpansionLayer`)

File: `plugins/transition_expansion_layer.cpp`, `include/costmap_2d/transition_expansion_layer.h`

### 7.1 Tujuan

Layer ini memperluas (expand) area transisi dengan radius tertentu, sehingga robot dapat mendeteksi transisi **sebelum** benar-benar mencapai garis transisi. Layer ini membuat **buffer zona deteksi** di sekitar data transisi.

### 7.2 Algoritma Ekspansi (BFS)

Menggunakan **Breadth-First Search (BFS)** untuk memperluas seed cells:

```
1. Terima map transisi dari topic
2. Reset semua cell layer ke 0 (NO_INFORMATION)
3. Kumpulkan semua seed cells:
     seed_cells = { (x, y) | pending_map.data[y * W + x] > 0 }
4. cell_expansion_radius = ceil(expansion_radius_m / resolution)
5. BFS dari semua seed cells secara simultan:
     q = queue berisi semua seed cells
     distance[seed] = 0
     while q tidak kosong:
         (x, y) = q.pop()
         d = distance[(x, y)]
         if d >= cell_expansion_radius: continue
         for each tetangga (nx, ny) dalam 4 arah:
             if (nx, ny) valid dan bukan LETHAL_OBSTACLE:
                 distance[(nx, ny)] = d + 1
                 if pending_map.data[ny * W + nx] <= 0:   // bukan seed
                      setCost(nx, ny, TRANSITION_EXPANSION) // nilai 5
                 q.push((nx, ny))
```

**Ilustrasi:**

```
Sebelum ekspansi:             Setelah ekspansi (radius = 2 cell):
                                . . . . . . .
  . . . . . . .                 . E E E E E .
  . . . T . . .                 . E T T T E .
  . . T T T . .                 . E T T T E .
  . . . T . . .                 . E T T T E .
  . . . . . . .                 . E E E E E .
                                . . . . . . .

T = TRANSITION_MAIN_DATA (1)
E = TRANSITION_EXPANSION (5)
```

### 7.3 Batasan Ekspansi

Ekspansi **berhenti** jika bertemu `LETHAL_OBSTACLE` (254) dari layer lain:

```cpp
if (master_grid.getCost(nx, ny) == costmap_2d::LETHAL_OBSTACLE)
    continue;   // tidak expand ke obstacle
```

### 7.4 Penggabungan ke Master Grid

Di `updateCosts()`, layer hanya menulis ke cell yang **pasti free** di master:

```
for cell in [min_i..max_j]:
    if local_cost == NO_INFORMATION: skip
    if master_cost == LETHAL_OBSTACLE: skip   // jangan timpa obstacle
    if master_cost == NO_INFORMATION: skip     // jangan timpa unknown
    master_cost = max(local_cost, master_cost)
```

Ini memastikan expansion layer tidak menimpa obstacle atau area unknown.

### 7.5 Parameter Konfigurasi

| Parameter | Default | Fungsi |
|---|---|---|
| `expansion_radius` | 0.0 | Radius ekspansi dalam meter (konversi ke cell: $r_{\text{cell}} = \lceil r / \text{resolution} \rceil$) |
| `map_topic` | `"transition_map"` | Topic sumber data transisi |
| `publish_grid` | false | Publikasi grid untuk debugging |

Contoh konfigurasi di `global_costmap.yaml`:

```yaml
transition_expansion_layer:
  enabled: true
  expansion_radius: 0.45        # radius 45 cm di sekitar transisi
  map_topic: /multimap_server/maps/transition/localization/map
  publish_grid: true
```

### 7.6 Interaksi dengan Layer Lain

Urutan plugin di `global_costmap.yaml` penting:

```yaml
plugins:
  - static_layer                 # Static map dari /map
  - transition_layer             # Data transisi (cost 1)
  - transition_expansion_layer   # Ekspansi transisi (cost 5)
  - inflation_layer              # Inflasi obstacle (cost 2-4, 6-250)
```

**Alur data:**

```
static_layer        transition_layer     transition_expansion_layer   inflation_layer
    │                     │                       │                       │
    ▼                     ▼                       ▼                       ▼
┌─────────┐         ┌──────────┐           ┌──────────────┐          ┌──────────┐
│ 0 / 254 │         │ 1 / 0    │           │ 5 / 0        │          │ 2-252    │
│(free/   │  ───►   │(marker   │    ───►   │(expansion    │   ───►   │(gradient)│
│obstacle)│         │ transisi)│           │ buffer)      │          └──────────┘
└─────────┘         └──────────┘           └──────────────┘
```

Pada master costmap setelah semua layer:
- 0 = free space
- 1 = `TRANSITION_MAIN_DATA` — marker transisi (navigable)
- 2–4 = gradient inflasi rendah
- 5 = `TRANSITION_EXPANSION` — buffer deteksi (navigable)
- 6–250 = gradient inflasi (semakin tinggi semakin dekat ke obstacle)
- 251–252 = (dicadangkan untuk inflasi)
- 253 = INSCRIBED_INFLATED_OBSTACLE
- 254 = LETHAL_OBSTACLE
- 255 = NO_INFORMATION

### 7.7 Interaksi dengan costmap_jumper

Nilai 1 dan 5 inilah yang dideteksi oleh `costmap_jumper`:

```cpp
// costmap_jumper.cpp:32-34
const unsigned char COST_TRANSITION_EXPANSION = 5;
const unsigned char COST_TRANSITION_MAIN_DATA = 1;
const unsigned char COST_TRANSITION_LETHAL = 1;
```

Saat robot memasuki cell dengan cost **5** (expansion buffer), `costmap_jumper` mulai mempersiapkan lompatan (jika `enable_waiting`). Saat robot mencapai cell **1** (garis transisi), lompatan dieksekusi — pose robot dipindahkan ke pasangan transisi yang sesuai.

Nilai 1 dan 5 sengaja dibuat navigable (di bawah `INSCRIBED_INFLATED_OBSTACLE = 253`) agar tidak mengganggu path planning. Robot bisa berjalan di atas area ini tanpa masalah — fungsinya murni sebagai marker untuk dideteksi oleh costmap_jumper.

---



## 8. Transformasi Publikasi (`Costmap2DPublisher`)

File: `costmap_2d_publisher.cpp`

Costmap internal (0–255) dikonversi ke `nav_msgs::OccupancyGrid` (−1, 0–100). Terdapat **dua mekanisme publikasi**:

### 8.1 Publikasi Standar (`Costmap2DPublisher`)

Menggunakan lookup table (`costmap_2d_publisher.cpp:56-71`):

$$T[i] = \begin{cases}
0 & \text{if } i = 0 \text{ (FREE)} \\
1 + \frac{97 \cdot (i - 1)}{251} & \text{if } 1 \leq i \leq 252 \\
99 & \text{if } i = 253 \text{ (INSCRIBED)} \\
100 & \text{if } i = 254 \text{ (LETHAL)} \\
-1 & \text{if } i = 255 \text{ (UNKNOWN)}
\end{cases}$$

Hasil lookup table:

| Internal | OG | Makna |
|---|---|---|
| 0 | 0 | Free |
| 1 | 1 | TRANSITION_MAIN_DATA (tampil sebagai cost rendah) |
| 2–4 | 1–3 | Gradient cost rendah (inflasi) |
| 5 | 2 | TRANSITION_EXPANSION (tampil sebagai cost rendah) |
| 6–252 | 3–98 | Gradient cost (hasil inflasi) |
| 253 | 99 | INSCRIBED_INFLATED_OBSTACLE |
| 254 | 100 | LETHAL_OBSTACLE |
| 255 | −1 | NO_INFORMATION (unknown) |

### 8.2 Publikasi Kustom untuk Visualisasi (`layer_publisher.cpp`)

Karena nilai 1 dan 5 tampil hampir seperti free space di RViz (OG 1–2), terdapat `layer_publisher.cpp` yang memetakan ulang untuk visualisasi:

| Internal | OG | Warna di RViz |
|---|---|---|
| `TRANSITION_MAIN_DATA` (1) | 100 | Merah/cyan (lethal color) |
| `TRANSITION_EXPANSION` (5) | 50 | Hijau/kuning (occupied) |
| `LETHAL_OBSTACLE` (254) | 100 | Merah |
| `FREE_SPACE` (0) | 0 | Hitam |

Ini memungkinkan area transisi terlihat jelas di RViz meskipun nilai internalnya rendah (navigable).

Incremental updates dipublikasikan di topic `costmap_updates` (tipe `map_msgs::OccupancyGridUpdate`) yang hanya mengirim cell yang berubah — mengurangi bandwidth secara signifikan.

---

## 9. Costmap2DROS — Node Wrapper

File: `costmap_2d_ros.cpp`

### 9.1 Inisialisasi

Di constructor:

1. Load parameter plugin dari `~<name>/plugins` (YAML list)
2. Load masing-masing plugin via `pluginlib`
3. Inisialisasi LayeredCostmap
4. Start background thread `mapUpdateLoop()`

### 9.2 Map Update Loop

```
while (ros::ok()):
    getRobotPose()       → cari pose robot via TF
    updateMap(x, y, yaw) → layered_costmap_->updateMap()
    publishCostmap()     → Costmap2DPublisher
    sleep(1/frequency)
```

Frequency default: 1–5 Hz untuk global costmap, hingga 20 Hz untuk local costmap.

### 9.3 Footprint

Robot footprint (polygon 2D) digunakan untuk:
- Menentukan cell mana yang termasuk INSCRIBED (robot menyentuh obstacle)
- Validasi pose: apakah robot dalam keadaan collision?

$$r_{\text{inscribed}} = \max_{\text{footprint vertices}} \|v_i\|$$

---

## 10. Alur Data End-to-End

```
/map (OccupancyGrid)          /multimap/transition/map         /scan (LaserScan)
       │                            │                              │
       ▼                            ▼                              ▼
 StaticLayer                 TransitionLayer              ObstacleLayer
 (overwrite skip unknown)    (pixel 255 → cost 1)         (mark + clear via Bresenham)
       │                            │                              │
       │                            ▼                              │
       │                     TransitionExpansionLayer               │
       │                     (BFS expand → cost 5)                │
       │                            │                              │
       ▼                            ▼                              ▼
 ┌─────────────────────────────────────────────────────────────────────┐
 │                     LayeredCostmap.updateMap()                       │
 │   1. updateBounds() → union semua bounding box                      │
 │   2. Reset region                                                    │
 │   3. updateCosts() → static → transition → expansion → inflation    │
 └─────────────────────────────────────────────────────────────────────┘
       │
       ▼
 Master Costmap2D (unsigned char array, 0–255)
       │   FREE=0, TRANSITION_MAIN=1, EXPANSION=5, 6-252=inflasi,
       │   253=INSCRIBED, 254=LETHAL, 255=UNKNOWN
       ▼
 Costmap2DPublisher (cost_translation_table_)
 serta layer_publisher (visualisasi OG 100/50)
       │
       ├── /move_base_node/global_costmap/costmap (OccupancyGrid, -1..100)
       ├── /move_base_node/global_costmap/costmap_updates (incremental)
       │
       ▼
 costmap_jumper (kustom)      move_base (planner + controller)
 (deteksi cost 1 dan 5)       (path planning + obstacle avoidance)
```

Untuk local costmap:

```
/scan (LaserScan)
  │
  ▼
ObstacleLayer (rolling window, 8×8 m)
  │
  ▼
InflationLayer
  │
  ▼
LayeredCostmap → master → publisher
                     │
                     ▼
              move_base (local planner / DWA)
```

---

## 11. Kompleksitas

| Operasi | Kompleksitas | Keterangan |
|---|---|---|
| World ↔ Grid | $O(1)$ | Operasi aritmatika sederhana |
| Raytracing Bresenham | $O(L)$ | $L$ = panjang ray dalam cell |
| Mark obstacle | $O(N)$ | $N$ = jumlah sensor beams |
| Inflasi (Dijkstra) | $O(N \log N)$ | $N$ = cell dalam radius inflasi |
| Publikasi | $O(W \cdot H)$ | Seluruh grid dikonversi dan dikirim |

---

## 12. Konfigurasi (`config/*.yaml`)

### global_costmap.yaml (dengan transition layers)

```yaml
global_costmap:
  global_frame: map
  robot_base_frame: base_link
  update_frequency: 5.0
  publish_frequency: 1.0
  static_map: true
  resolution: 0.01
  plugins:
    - {name: static_layer,               type: "costmap_2d::StaticLayer"}
    - {name: transition_layer,           type: "costmap_2d::TransitionLayer"}
    - {name: transition_expansion_layer, type: "costmap_2d::TransitionExpansionLayer"}
    - {name: inflation_layer,            type: "costmap_2d::InflationLayer"}

  static_layer:
    enabled: true
    map_topic: /map

  transition_layer:
    enabled: true
    map_topic: /multimap_server/maps/transition/localization/map
    lethal_cost_threshold: 100
    transition_expansion: 0
    publish_grid: true

  transition_expansion_layer:
    enabled: true
    expansion_radius: 0.45
    map_topic: /multimap_server/maps/transition/localization/map
    publish_grid: true

  inflation_layer:
    enabled: true
    inflation_radius: 0.2
    cost_scaling_factor: 5.0
```

### local_costmap.yaml

```yaml
local_costmap:
  global_frame: /odom
  robot_base_frame: /base_link
  update_frequency: 5.0
  publish_frequency: 2.0
  static_map: false
  rolling_window: true
  width: 8.0
  height: 8.0
  resolution: 0.05
  plugins:
    - {name: obstacle_layer, type: costmap_2d::ObstacleLayer}
    - {name: inflation_layer, type: costmap_2d::InflationLayer}
```

### costmap_common.yaml

```yaml
robot_radius: 0.25
obstacle_range: 3.0
raytrace_range: 3.5
inflation_radius: 0.3
cost_scaling_factor: 5.0
observation_sources: scan
scan: {sensor_frame: /laser, data_type: LaserScan, topic: /scan, marking: true, clearing: true}
```

---

## 13. Referensi File

| File | Isi |
|---|---|
| `costmap_2d.h/.cpp` | Class Costmap2D: grid, koordinat, Bresenham raytracing |
| `cost_values.h` | Konstanta cost (FREE, LETHAL, INSCRIBED, NO_INFORMATION) |
| `layer.h` | Abstract class Layer: interface plugin |
| `costmap_layer.h/.cpp` | Base class CostmapLayer: strategi merge (Overwrite, Max, Add) |
| `layered_costmap.h/.cpp` | LayeredCostmap: aggregator multi-layer |
| `costmap_2d_ros.h/.cpp` | Costmap2DROS: node wrapper, TF, update loop |
| `costmap_2d_publisher.h/.cpp` | Publisher: costmap → OccupancyGrid + incremental updates |
| `costmap_math.h/.cpp` | Fungsi matematika: distanceToLine, intersects |
| `inflation_layer.cpp` | Implementasi inflasi dengan priority queue |
| `obstacle_layer.cpp` | Implementasi obstacle marking + clearing |
| `static_layer.cpp` | Implementasi static map dari /map |
| `transition_layer.h/.cpp` | Custom layer: data transisi area (cost 1) |
| `transition_expansion_layer.h/.cpp` | Custom layer: ekspansi transisi via BFS (cost 5) |
| `layer_publisher.cpp` | Publisher kustom: visualisasi OG (TRANSITION_MAIN→100, EXPANSION→50) |
| `costmap_plugins.xml` | Registrasi plugin untuk pluginlib |
