# Costmap Jumper — Penjelasan Lengkap

Dokumen ini menjelaskan cara kerja **`costmap_jumper`** — node kustom yang mendeteksi area transisi di costmap dan melakukan "lompatan" pose robot antar area. Kode sumber ada di `src/icp_loc/src/costmap_jumper.cpp`.

---

## Purpose

`costmap_jumper` memungkinkan robot untuk **berpindah antar area** yang terhubung melalui area transisi (pintu/koridor). Ketika robot memasuki area transisi di costmap, node ini menunggu hingga robot mencapai centroid lalu menerbitkan `/initialpose` untuk "memindahkan" robot ke centroid area tujuan.

Sistem ini bekerja bersama dengan:
- **`costmap_2d_node` (transition_costmap)** — Costmap terisolasi dengan `static_layer` + `transition_layer` + `transition_expansion_layer`. Dipisah dari global costmap agar A* global planner tidak terpengaruh cost transisi.
- **`icp_loc_node`** — Menerima `/initialpose` dan meng-update pose robot via ICP
- **`path_interceptor`** — Mencegat navigation goal dan menyusun jalur melalui transisi
- **`region_dwa_bridge`** — Mengganti konfigurasi DWA planner per region

---

## Arsitektur

```
┌──────────────────────────────────────────────────────────────────┐
│                       costmap_jumper                             │
│                                                                  │
│  costmapCallback()           checkTimerCallback() (20 Hz)        │
│  ┌───────────────┐          ┌─────────────────┐                 │
│  │ Terima costmap│          │ Cek pose robot  │                 │
│  │ dari /transi- │──────────│ dari TF          │                 │
│  │ tion_costmap  │          │ + regionOfPoint │                 │
│  └───────┬───────┘          └────────┬────────┘                 │
│          │                           │                           │
│          ▼                           ▼                           │
│  ┌───────────────┐          ┌─────────────────────┐             │
│  │ Deteksi data  │          │ Apakah robot di     │             │
│  │ transisi      │          │ expansion zone?     │             │
│  │ (OG 1 & 2)    │          │ (cost 5/OG 2)       │             │
│  └───────┬───────┘          └──────────┬──────────┘             │
│          │                    ┌────────▼──────────┐             │
│          ▼                    │ enable_waiting?   │             │
│  ┌───────────────────┐       │ Tunggu dt = 2×radius│            │
│  │ ROI window scan   │       │ / speed, atau      │             │
│  │ (±80 cells)       │       │ pitch trigger      │             │
│  │ → OG-1 centroid   │       └────────┬──────────┘             │
│  │ → OG-2 centroid   │                │                         │
│  └───────────────────┘       ┌────────▼──────────┐             │
│                              │ executeJump:       │             │
│                              │ Jump langsung ke   │             │
│                              │ OG-2 centroid      │             │
│                              │ → Publish /initial │             │
│                              │   pose             │             │
│                              │ → Publish /transi- │             │
│                              │   tion_jumped      │             │
│                              │ (region diupdate   │             │
│                              │  via TF tracking)  │             │
│                              └────────────────────┘             │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. Deteksi Data Transisi

### 1.1 Cost Values

```cpp
const unsigned char COST_TRANSITION_EXPANSION = 5;
const unsigned char COST_TRANSITION_MAIN_DATA = 1;

// OccupancyGrid values setelah cost_translation_table_:
//   internal 1 → OG 1  (main/lethal)
//   internal 5 → OG 2  (expansion)
```

Nilai internal cost 1 (TRANSITION_MAIN_DATA) dan 5 (TRANSITION_EXPANSION) diterjemahkan oleh `costmap_2d_publisher` ke OG 1 dan OG 2. `costmap_jumper` menerima OccupancyGrid dari **transition_costmap terisolasi** (bukan dari global costmap) dan mendeteksi nilai OG ini:

```cpp
inline bool isTransitionCost(unsigned char c) {
    return c >= OG_TRANSITION_MIN && c <= OG_TRANSITION_MAIN;
    // return c >= 1 && c <= 2
}
```

Digunakan untuk **deteksi** robot (checkTimerCallback). ROI window scan menggunakan perbandingan langsung terhadap `OG_TRANSITION_MIN` dan `OG_TRANSITION_MAIN`.

### 1.2 Penerimaan Costmap (`costmapCallback`)

```
1. Copy data OG ke costmap_2d::Costmap2D internal
2. Cek hasTransitionData():
     Scan seluruh data — apakah ada cell dengan cost 1 atau 2?
3. Jika ya dan belum traced:
     traced_ = true
     computeCentroids()                  // ROI window scan → OG-1 + OG-2 centroids
     publishTransitionMarkers()          // label A/B di RViz
4. Jika belum ada data transisi:
     Setiap 10 detik: diagnoseTransitionCosts()  // histogram cost
```

### 1.3 Subscription

Costmap_jumper subscribe ke **transition_costmap terisolasi** via param `~costmap_topic` (default `/transition_costmap/costmap/costmap`). Transition costmap berisi tiga layer:
- `static_layer` — data obstacle (untuk blocking BFS ekspansi)
- `transition_layer` — data transisi utama (OG 1)
- `transition_expansion_layer` — buffer ekspansi (OG 2)

---

## 2. Centroid Computation (ROI Window Scan)

Menggantikan BFS flood-fill sebelumnya. ROI window scan lebih sederhana dan menghasilkan dua set centroid: **OG-1** (untuk path_interceptor) dan **OG-2** (untuk jumping).

### 2.1 Konversi Pixel YAML ke Cell Costmap

```cpp
int si = yamlToCellI(pixel_x);   // (pixel_x * resolution + origin_x)
int sj = yamlToCellJ(pixel_y);   // height - 1 - pixel_y
```

### 2.2 ROI Window Scan

Dari setiap seed pixel, scan ±80 cell dalam rectangular window (mencakup seluruh expansion island, max radius 46 cell pada 0.01m resolution):

```cpp
const int WINDOW = 80;
for (int dx = -WINDOW; dx <= WINDOW; ++dx)
    for (int dy = -WINDOW; dy <= WINDOW; ++dy)
    {
        int nx = seed_ci + dx, ny = seed_cj + dy;
        auto c = cm_.getCost(nx, ny);
        if (c == OG_TRANSITION_MIN) {
            // accumulate to OG-1 centroid sums
        } else if (c == OG_TRANSITION_MAIN) {
            // accumulate to OG-2 centroid sums
        }
    }
// centroid = sum / count
```

### 2.3 Dual Centroids

Setiap pasangan transisi menghasilkan dua set centroid:

| Centroid | Digunakan oleh | Isi |
|---|---|---|
| **OG-1** (`cx_A, cy_A`) | path_interceptor | Center dari transition main data (sebagai navigation waypoint) |
| **OG-2** (`cx_A_exp, cy_A_exp`) | costmap_jumper (jump) | Center dari expansion zone (sebagai jump destination) |

OG-1 centroids dipublikasi ke `/transition_centroids` (format: `[pair_id, cx_A, cy_A, cx_B, cy_B, ...]`).

OG-2 centroids digunakan langsung oleh `executeJump()` sebagai tujuan lompatan.

---

## 3. Region Tracking (TF-based)

Region tracking telah diganti dari event-based (jump-driven) menjadi **continuous TF-based** seperti `path_interceptor::regionOfPoint()`.

### 3.1 World-Coord Seeds

Setiap seed memiliki world coordinate yang dihitung saat load YAML:

```cpp
p.awx = yaml_origin_x_ + p.seed_A.x * yaml_resolution_;
p.awy = -(yaml_origin_y_ + p.seed_A.y * yaml_resolution_);
```

### 3.2 regionOfPoint

```cpp
char regionOfPoint(double wx, double wy) const
{
    // Untuk setiap pair, hitung jarak ke seed_A dan seed_B
    // Min_dist[pair_id]   = min(min_dist, dist to seed_A)
    // Min_dist[pair_id+1] = min(min_dist, dist to seed_B)
    return 'A' + argmin(min_dist);
}
```

### 3.3 Continuous Update

Di `checkTimerCallback`, setiap kali TF lookup berhasil:

```cpp
char r = regionOfPoint(rx, ry);
if (r != current_region_) {
    current_region_ = r;
    publishRegion();  // /current_region
}
```

Region TIDAK diupdate oleh `executeJump()` — hanya berubah ketika robot benar-benar pindah region berdasarkan posisi TF.

---

## 4. Deteksi & Eksekusi Lompatan (`checkTimerCallback`)

Timer callback berjalan pada **20 Hz**:

### 4.1 Flowchart

```
1. Lookup TF map → base_link
2. Konversi posisi robot ke cell costmap:
     ci, cj = worldToMap(rx, ry)
3. Baca cost di cell (ci, cj)
4. Guard checks:
     - Costmap belum diterima? → return
     - Belum 5 detik sejak startup? → return
     - Initial pose belum terkirim? → return
     - Robot > 1.5 m dari initial pose? → return (ICP belum koreksi)
     - Lompatan sebelumnya masih cooldown? → return
5. Apakah isTransitionCost(cost)?
     YA → eksekusi lompatan
     TIDAK → reset ICP toggle, return
```

### 4.2 Waiting Mode (`enable_waiting: true`)

Ketika robot memasuki expansion zone (cost 5/OG 2), robot menunggu sebelum lompatan:

$$t_{\text{wait}} = \frac{2 \times r_{\text{expansion}}}{v_{\text{robot}}}$$

$$v_{\text{robot}} = \max(\sqrt{v_x^2 + v_y^2},\; 0.05)$$

Faktor **2×** karena robot melewati expansion zone di sisi masuk DAN sisi keluar. $r_{\text{expansion}} = 0.45$ m (dari `expansion_radius` TransitionExpansionLayer).

**State machine waiting:**
```
IDLE → [masuk expansion zone] → WAITING
  ├── ICP disabled (toggle_icp = false) — freeze pose
  ├── transition_vel = true
  ├── pitch_baseline_ captured (untuk pitch detection)
  └── Countdown: 1 detik → log "waiting... Xs remaining"

WAITING → [timer habis ATAU pitch trigger] → EXECUTE JUMP
  └── Reset ICP toggle
```

### 4.3 Pitch-based Jump Detection

Jika robot memiliki IMU dan region B adalah slope (region A/C flat), pitch detection bisa memicu lompatan lebih awal:

```cpp
if (pitch_jump_enabled_ && fabs(pitch_current_ - pitch_baseline_) >= pitch_threshold_)
    executeJump(...);  // jump sebelum timer habis
```

Timing: saat waiting dimulai → `pitch_baseline_` = pitch saat itu. Setiap cycle, cek `|pitch - baseline| ≥ threshold` (12° default, configurable dalam derajat di YAML).

Time-based waiting tetap sebagai **safety fallback** jika pitch tidak terdeteksi.

### 4.4 Match Pair & Side

Robot di cell $(c_i, c_j)$ dicocokkan ke pasangan transisi terdekat:

```cpp
for each pair in transition_pairs_:
    ax = yamlToCellI(pair.seed_A.x), ay = yamlToCellJ(pair.seed_A.y)
    bx = yamlToCellI(pair.seed_B.x), by = yamlToCellJ(pair.seed_B.y)
    da = (ax - ci)^2 + (ay - cj)^2
    db = (bx - ci)^2 + (by - cj)^2
    if da < best_d2: best = da, pair_id = p.id, side_a = true
    if db < best_d2: best = db, pair_id = p.id, side_a = false
```

### 4.5 executeJump

Jump dilakukan **langsung ke OG-2 centroid** pasangan tujuan:

```cpp
double dst_x = on_side_A ? pair_traced->cx_B_exp : pair_traced->cx_A_exp;
double dst_y = on_side_A ? pair_traced->cy_B_exp : pair_traced->cy_A_exp;
```

Tidak ada proportional mapping atau vector mirroring — robot melompat langsung ke centroid expansion zone tujuan.

### 4.6 Orientasi Lompatan

Jika ada `region_orientations` untuk region tujuan:

$$\text{q}_{\text{new}} = \text{q}_{\text{region}} \cdot \text{q}_{\text{current}}$$

Ini menerapkan rotasi relatif terhadap orientasi robot saat ini.

### 4.7 Publikasi

```cpp
// Publish new pose
initial_pose_pub_.publish(pose_msg);        // /initialpose

// Special: region C diulang 3x
if (dest_letter == 'C'):
    for i=0..2: publish lagi setiap 1 detik

// Signal jump selesai
transition_jumped_pub_.publish(Empty());    // /transition_jumped

// Per-pair cooldown
pair_cooldown_end_[pair_id] = now + 100 detik
```

Region **TIDAK** diupdate oleh `executeJump()` — region tracking dilakukan via TF-based `regionOfPoint()`.

---

## 5. Interaksi dengan Node Lain

```
costmap_jumper  ──/initialpose──→  icp_loc_node
                                   (ICP memperbaiki pose)

costmap_jumper  ──/transition_jumped──→  path_interceptor
                                         (melanjutkan path)

costmap_jumper  ──/transition_centroids──→  path_interceptor
                                            (OG-1 centroids)

costmap_jumper  ──/current_region──→  region_dwa_bridge
                                     (mengganti DWA config per region)

costmap_jumper  ──/icp_loc_node/toggle_icp──→  icp_loc_node
                                               (enable/disable ICP)

transition_costmap ──/transition_costmap/costmap/costmap──→ costmap_jumper
                                                            (isolated costmap)
```

---

## 6. Konfigurasi (`config/costmap_jumper.yaml`)

```yaml
pair_cooldown: 100.0       # cooldown antar lompatan pada pasangan yang sama (detik)
initial_pose_yaw: -90.0    # orientasi yaw initial pose (derajat)
enable_waiting: true       # tunggu sebelum lompatan (lewati expansion zone dulu)
jump_pose_duration: 0.0    # durasi republish jump pose (detik)
base_frame: "base_link"    # frame robot
check_rate: 20.0           # frekuensi pengecekan (Hz)
initial_jump_delay: 5.0    # delay sebelum lompatan pertama setelah startup (detik)
pitch_jump_enable: true    # aktifkan pitch-based jump detection
pitch_jump_threshold: 12.0 # threshold pitch dalam DERAJAT (12.0°)
region_orientations:       # override orientasi per region (quaternion)
  A: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
  B: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}
  C: {x: 0.0, y: 0.0, z: 0.676934, w: 0.736044}
```

### Parameter dari YAML Transisi

File: `multimap_server/maps/transition/transition_map.yaml`

```yaml
transitions:
  - {first_pixel_A: [354, 206], first_pixel_B: [106, 328], pair: 0}
  - {first_pixel_A: [106, 436], first_pixel_B: [135, 187], pair: 1}
initial_pose: [375, 75]
region_orientations:
  C: {x: 0.0, y: 0.0, z: -0.7046, w: 0.7096}
```

| Field | Fungsi |
|---|---|
| `first_pixel_A/B` | Koordinat pixel (dalam PGM) seed untuk ROI window scan |
| `pair` | ID pasangan (0, 1, …) |
| `initial_pose` | Pose awal robot saat startup [pixel_x, pixel_y] |
| `region_orientations` | Override orientasi per region (quaternion) — di-merge dengan costmap_jumper.yaml |

---

## 7. Referensi File

| File | Isi |
|---|---|
| `costmap_jumper.cpp` | Node utama: ROI window scan, pitch detection, TF-based region tracking, eksekusi lompatan |
| `costmap_jumper.yaml` | Konfigurasi: cooldown, waiting, pitch threshold |
| `region_dwa_bridge.cpp` | Bridge: ganti konfigurasi DWA per region |
| `region_dwa_params.yaml` | Parameter DWA per region (A, B, C dengan semua 29+ parameter) |
| `transition_costmap.yaml` | Konfigurasi costmap transisi terisolasi (static + transition + expansion) |
| `transition_map.yaml` | Definisi pasangan transisi dan initial pose |


# Path Interceptor — Penjelasan Lengkap

Dokumen ini menjelaskan cara kerja **`path_interceptor`** — node yang mencegat dan memodifikasi navigation goal untuk memungkinkan navigasi multi-area melalui transisi. Kode sumber di `src/icp_loc/src/path_interceptor.cpp`.

---

## Purpose

`path_interceptor` **mencegat goal navigation** dari user (via `/move_base_simple/goal`) dan jika goal berada di area yang berbeda dari posisi robot saat ini, node ini menyusun **multi-step plan** melalui serangkaian transition points.

Daripada mengirim goal langsung yang mungkin tidak bisa dijangkau (karena area berbeda secara topologi), path_interceptor:
1. Menentukan rute area: region A → region B → region C → ...
2. Mengirim goal bertahap ke setiap transition point
3. Menunggu robot melompat (via `costmap_jumper`) sebelum melanjutkan ke step berikutnya
4. Mengirim final goal hanya setelah semua transisi selesai

---

## State Machine

```
                     user mengirim goal
                           │
                    ┌──────▼──────┐
                    │ robot & goal│
                    │ di region    │───── YA ──→ DIRECT
                    │ yang sama?   │     (kirim goal langsung)
                    └──────┬──────┘
                           │ TIDAK
                           ▼
                    buildPath(robot_region, goal_region)
                           │
                    ┌──────▼──────┐
           ┌───────│ INTERCEPT    │──────────────┐
           │       │ (multi-step) │              │
           │       └──────┬──────┘              │
           │              │                     │
           │     sendInterceptGoal(step 0)      │
           │     goal = centroid transition     │
           │              │                     │
           │              ▼                     │
           │     ┌──────────────┐               │
           │     │ /transition  │               │
           │     │ _jumped      │               │
           │     │ received     │               │
           │     └──────┬───────┘               │
           │            │                       │
           │     advanceIntercept()             │
           │            │                       │
           │     ┌──────▼──────┐                │
           │     │ more steps? │── YA ──→ loop  │
           │     └──────┬──────┘                │
           │            │ TIDAK                 │
           │            ▼                       │
           └───────────→┐                       │
                        ▼                       │
                  ┌──────────┐                  │
                  │ FINAL_LEG│                  │
                  │ (goal    │                  │
                  │ asli)    │                  │
                  └──────────┘                  │
                        │                       │
                        ▼                       ▼
                       IDLE                 IDLE
```

---

## 1. Region Determination

### 1.1 Konsep Region

Sistem ini membagi dunia menjadi region-region yang dihubungkan oleh transition pairs:

```
Region A ←── pair 0 ──→ Region B ←── pair 1 ──→ Region C
```

- `pair 0` menghubungkan A ↔ B
- `pair 1` menghubungkan B ↔ C
- `seed_A` selalu di region dengan index lebih rendah

### 1.2 `regionOfPoint(x, y)`

Menentukan region suatu titik berdasarkan jarak ke seed transisi:

```cpp
char regionOfPoint(double wx, double wy):
    min_dist[i] = INF untuk i = 0..25  // maks 26 region

    for each seed in seeds:
        dA = hypot(wx - seed.awx, wy - seed.awy)
        dB = hypot(wx - seed.bwx, wy - seed.bwy)
        min_dist[seed.pair_id]     = min(min_dist[pair_id], dA)
        min_dist[seed.pair_id + 1] = min(min_dist[pair_id + 1], dB)

    return 'A' + argmin_i min_dist[i]
```

Jarak dihitung ke **semua seed**, dan region ditentukan oleh seed terdekat:

$$r = \arg\min_{i \in [0, N_{\text{seeds}}+1]} \min_{s \in \text{seeds\_in\_region}(i)} \|p - s\|$$

### 1.3 Robot Region Tracking

Timer callback setiap 0.5 detik meng-update `robot_region_` berdasarkan posisi robot dari TF:

```cpp
robot_region_ = regionOfPoint(robot_x, robot_y);
```

---

## 2. Goal Interception

### 2.1 `goalCallback`

Menerima goal dari `/move_base_simple/goal`:

```
1. Abort goal sebelumnya jika INTERCEPT/INTERCEPTING
2. Jika robot_region unknown → DIRECT
3. Tentukan goal_region = regionOfPoint(goal.x, goal.y)
4. Jika robot_region == goal_region → DIRECT
5. Jika berbeda → buildPath(robot, goal)
   → simpan final_goal, masuk state INTERCEPT
```

### 2.2 `buildPath(from, to)`

Membangun daftar terurut InterceptStep yang harus dilalui:

```cpp
void buildPath(char from, char to, vector<InterceptStep>& out):
    fi = from - 'A'
    ti = to - 'A'

    if fi < ti:                 // maju
        for i = fi to ti-1:
            step.pair_id = i
            step.enter_from_A = true           // masuk dari sisi A
            step.ix, step.iy = centroid_A[i]  // atau seed_A jika centroid belum ada
            out.push_back(step)

    else:                       // mundur
        for i = fi-1 down to ti:
            step.pair_id = i
            step.enter_from_A = false          // masuk dari sisi B
            step.ix, step.iy = centroid_B[i]
            out.push_back(step)
```

**Contoh:** Robot di region A, goal di region C:
- fi=0, ti=2 → i=0,1
- Step 0: pair 0, enter_from_A → centroid_A[0]
- Step 1: pair 1, enter_from_A → centroid_A[1]
- Robot melewati 2 transisi

Robot di region C, goal di region A:
- fi=2, ti=0 → i=1,0
- Step 0: pair 1, enter_from_A=false → centroid_B[1]
- Step 1: pair 0, enter_from_A=false → centroid_B[0]

---

## 3. Multi-Step Execution

### 3.1 `sendInterceptGoal(step_idx)`

Mengirim goal ke move_base untuk mencapai transition point:

```cpp
move_base_msgs::MoveBaseGoal goal;
goal.target_pose.position.x = step.ix;     // centroid transisi
goal.target_pose.position.y = step.iy;
goal.target_pose.orientation = currentRobotOrientation();  // jaga orientasi
ac_.sendGoal(goal);
```

### 3.2 `jumpedCallback`

Terima signal dari `/transition_jumped` (dikirim oleh `costmap_jumper`):

```cpp
void jumpedCallback():
    if state != INTERCEPT: return
    jumped_ = true
    retries_ = 0
    ac_.cancelAllGoals()              // batalkan goal menuju transition point
    ros::Duration(0.05).sleep()
    advanceIntercept()                // lanjut ke step berikutnya
```

### 3.3 `advanceIntercept`

```cpp
void advanceIntercept():
    current_step_++
    if current_step_ < pending_steps_.size():
        sendInterceptGoal(current_step_)     // masih ada step
    else:
        sendFinalGoal()                      // semua transisi selesai
        state_ = FINAL_LEG
```

### 3.4 `sendFinalGoal`

Kirim goal asli user ke move_base (sekarang robot sudah di region yang benar):

```cpp
goal.target_pose = final_goal_
goal.target_pose.pose.orientation = currentRobotOrientation()
ac_.sendGoal(goal);
```

---

## 4. Flow Lengkap: User Goal → Tujuan

```
User: "go to region C"
  │
  ▼
move_base_simple/goal: pose di region C
  │
  ▼
path_interceptor:
  robot_region = A, goal_region = C
  buildPath(A, C) = [
    { pair 0, enter_from_A, centroid_A[0] },
    { pair 1, enter_from_A, centroid_A[1] }
  ]
  │
  ▼
Step 0: send goal → centroid_A[0] (dekat transisi pair 0)
  │
  ▼
move_base: global plan A → centroid_A[0], robot bergerak
  │
  ▼
costmap_jumper: robot mencapai transisi pair 0 → JUMP phase
  │
  ▼
/transition_jumped: diterima path_interceptor
  │
  ▼
Step 1: send goal → centroid_A[1] (dekat transisi pair 1)
  │
  ▼
move_base: robot bergerak ke centroid_A[1], JUMP phase
  │
  ▼
/transition_jumped: diterima path_interceptor
  │
  ▼
FINAL_LEG: send goal → region C (actual user goal)
  │
  ▼
move_base: global plan → goal di region C → SUCCEEDED
```

---

## 5. Visualisasi

Path interceptor menerbitkan `visualization_msgs::MarkerArray` di `/path_interceptor/markers`:

- **LINE_STRIP** untuk setiap pasangan centroid(step_i) → centroid(step_i+1)
- Warna **cyan** (0, 1, 1)
- **DELETEALL** saat state berubah (membersihkan marker)

---

## 6. Centroid Callback

Menerima data centroid dari `/transition_centroids` (dipublikasi oleh `costmap_jumper`):

```cpp
void centroidCallback(Float64MultiArray msg):
    // Format: [pair_id, cx_A, cy_A, cx_B, cy_B, ...]  (5 elemen per entry)
    for i = 0 to size-1 step 5:
        pid = data[i]
        centroid_A[pid] = Point(data[i+1], data[i+2], 0)
        centroid_B[pid] = Point(data[i+3], data[i+4], 0)
```

Centroid ini digunakan sebagai **precise transition target** — lebih akurat daripada seed karena merupakan rata-rata dari seluruh garis transisi yang sudah di-trace.

---

## 7. Parameter Konfigurasi

| Parameter | Default | Fungsi |
|---|---|---|
| `transition_pairs_yaml` | `""` | Path ke file YAML definisi transisi |
| `MAX_RETRIES` | 1 | Maksimum retry untuk final goal |

---

## 8. Kompleksitas

| Operasi | Kompleksitas | Keterangan |
|---|---|---|
| regionOfPoint | $O(S)$ | $S$ = jumlah seed |
| buildPath | $O(|fi - ti|)$ | Jumlah step = selisih region index |
| centroidCallback | $O(P)$ | $P$ = jumlah pasangan |
| regionTimerCallback | $O(S)$ | 0.5 Hz |
| goalCallback | $O(S + |fi - ti|)$ | Per goal masuk |

---

## 9. Referensi File

| File | Isi |
|---|---|
| `path_interceptor.cpp` | Node utama: intercept goal, multi-step planning, centroid callback |
| `transition_map.yaml` | Definisi pasangan transisi dan seed pixels |
