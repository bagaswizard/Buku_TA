# Costmap Jumper — Penjelasan Lengkap

Dokumen ini menjelaskan cara kerja **`costmap_jumper`** — node kustom yang mendeteksi area transisi di costmap dan melakukan "lompatan" pose robot antar area. Kode sumber ada di `src/icp_loc/src/costmap_jumper.cpp`.

---

## Purpose

`costmap_jumper` memungkinkan robot untuk **berpindah antar area** yang terhubung melalui area transisi (pintu/koridor). Ketika robot memasuki area transisi di costmap, node ini menerbitkan `/initialpose` untuk "memindahkan" robot ke posisi yang sesuai di area tujuan.

Sistem ini bekerja bersama dengan:
- **`transition_layer` / `transition_expansion_layer`** — Memasukkan data transisi ke costmap (cost 1 dan 5)
- **`icp_loc_node`** — Menerima `/initialpose` dan meng-update pose robot via ICP
- **`path_interceptor`** — Mencegat navigation goal dan menyusun jalur melalui transisi
- **`jump_coordinator`** — Mengirim ulang goal setelah lompatan

---

## Arsitektur

```
┌──────────────────────────────────────────────────────────────────┐
│                       costmap_jumper                             │
│                                                                  │
│  costmapCallback()           checkTimerCallback()                │
│  ┌───────────────┐          ┌─────────────────┐                 │
│  │ Terima costmap│          │ Cek pose robot  │                 │
│  │ dari /costmap │──────────│ dari TF (20 Hz) │                 │
│  └───────┬───────┘          └────────┬────────┘                 │
│          │                           │                           │
│          ▼                           ▼                           │
│  ┌───────────────┐          ┌─────────────────────┐             │
│  │ Deteksi data  │          │ Apakah robot di     │             │
│  │ transisi      │          │ cell transisi?      │             │
│  │ (cost 1 atau 5)│         └──────────┬──────────┘             │
│  └───────┬───────┘                     │                         │
│          │                    ┌────────▼──────────┐             │
│          ▼                    │ enable_waiting?   │             │
│  ┌───────────────────┐       │ Tunggu dt = radius │             │
│  │ traceAllLines()   │       │ / speed sebelum    │             │
│  │ BFS 8-way flood   │       │ eksekusi lompatan   │             │
│  │ fill + ordering   │       └────────┬──────────┘             │
│  └───────────────────┘                │                         │
│                           ┌───────────▼───────────┐            │
│                           │ executeJump:          │            │
│                           │ Match posisi robot ke  │            │
│                           │ garis transisi sumber  │            │
│                           │ → Hitung posisi tujuan │            │
│                           │ → Publish /initialpose │            │
│                           │ → Publish /transition  │            │
│                           │   _jumped              │            │
│                           │ → Update current_region│            │
│                           └───────────────────────┘            │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. Deteksi Data Transisi

### 1.1 Cost Values

File: `costmap_jumper.cpp:32-40`

```cpp
const unsigned char COST_TRANSITION_EXPANSION = 5;
const unsigned char COST_TRANSITION_MAIN_DATA = 1;
const unsigned char COST_TRANSITION_LETHAL = 1;

// OccupancyGrid values setelah cost_translation_table_:
//   internal 1 → OG 1  (main/lethal)
//   internal 5 → OG 2  (expansion)
```

Nilai internal cost 1 (TRANSITION_MAIN_DATA) dan 5 (TRANSITION_EXPANSION) diterjemahkan oleh `costmap_2d_publisher` ke OG 1 dan OG 2. `costmap_jumper` menerima OccupancyGrid dan mendeteksi nilai OG ini:

```cpp
inline bool isTransitionCost(unsigned char c) {
    return c >= OG_TRANSITION_MIN && c <= OG_TRANSITION_MAIN;
    // return c >= 1 && c <= 2
}
```

### 1.2 Penerimaan Costmap (`costmapCallback`)

```
1. Copy data OG ke costmap_2d::Costmap2D internal
2. Cek hasTransitionData():
     Scan seluruh data — apakah ada cell dengan cost 1 atau 2?
3. Jika ya dan belum traced:
     traced_ = true
     traceAllLines()                     // trace semua garis transisi
     publishTransitionMarkers()          // label A/B di RViz
4. Jika belum ada data transisi:
     Setiap 10 detik: diagnoseTransitionCosts()  // histogram cost
```

---

## 2. Tracing Garis Transisi (`traceLine`)

File: `costmap_jumper.cpp:390`

Setiap pasangan transisi memiliki `seed_A` dan `seed_B` (dari YAML). Fungsi `traceLine(seed_x, seed_y)` menelusuri garis transisi dari seed pixel:

### 2.1 Konversi Pixel YAML ke Cell Costmap

```cpp
int si = yamlToCellI(pixel_x);   // (pixel_x * resolution + origin_x)
int sj = yamlToCellJ(pixel_y);   // height - 1 - pixel_y
```

Konversi pixel YAML $(p_x, p_y)$ ke koordinat grid costmap:

$$c_x = \left\lfloor \frac{o_x + p_x \cdot r_{\text{yaml}} - o_x^{\text{cm}}}{\text{resolution}} \right\rfloor, \qquad c_y = H_{\text{cm}} - 1 - p_y$$

### 2.2 Seed Search

Jika seed cell bukan transisi, cari cell transisi terdekat dalam radius 5 cell:

```
for r = 1 to 5:
    for di, dj pada lingkaran radius r:
        if cell[si+di, sj+dj] adalah transisi:
            set si,sj ke cell tersebut
```

### 2.3 Connected Component (8-way Flood Fill)

```cpp
// BFS untuk menemukan semua cell yang terhubung 8-way
// dengan nilai transisi yang sama
std::set<std::pair<int,int>> component;
std::queue<std::pair<int,int>> q;
q.push({si, sj});
component.insert({si, sj});

while (!q.empty() && component.size() < 20000) {
    auto [cx, cy] = q.front(); q.pop();
    for (int d = 0; d < 8; ++d) {
        nx = cx + dx8[d], ny = cy + dy8[d];
        if valid(nx, ny) && !visited && isTransitionCost(cell[nx, ny]):
            component.insert({nx, ny});
            q.push({nx, ny});
    }
}
```

### 2.4 BFS Ordering

Setelah component terkumpul, BFS kedua dilakukan dengan urutan kunjungan untuk mengubah set menjadi barisan terurut:

```cpp
std::vector<Pixel> line;
std::queue<std::pair<int,int>> bfs_q;
visited.insert({si, sj});
bfs_q.push({si, sj});

while (!bfs_q.empty()) {
    front = bfs_q.pop();
    line.push_back({front.x, front.y});  // urutan BFS
    for each tetangga dalam component:
        if belum visited:
            visited.insert(tetangga);
            bfs_q.push(tetangga);
}
```

Output: urutan cell dari seed ke ujung terjauh — merupakan representasi garis transisi.

### 2.5 Centroid Calculation

$$C_A = \left( \frac{1}{N_A} \sum_{p \in \text{line}_A} W(p_x, p_y),\; \frac{1}{N_A} \sum_{p \in \text{line}_A} W(p_y) \right)$$

dimana $W(p_x, p_y)$ adalah `mapToWorld(p_x, p_y)` — konversi ke koordinat dunia.

Centroids dikirim via topic `/transition_centroids` untuk dipakai oleh `path_interceptor`.

---

## 3. Deteksi & Eksekusi Lompatan (`checkTimerCallback`)

File: `costmap_jumper.cpp:596`

Timer callback berjalan pada **20 Hz**:

### 3.1 Flowchart

```
1. Lookup TF map → base_link
2. Konversi posisi robot ke cell costmap:
     ci, cj = worldToMap(rx, ry)
3. Baca cost di cell (ci, cj)
4. Guard checks:
     - Costmap belum diterima? → return
     - Belum 5 detik sejak startup? → return
     - Initial pose belum terkirim? → return (< 3 detik) → return
     - Robot > 1.5 m dari initial pose? → return (ICP belum koreksi)
     - Lompatan sebelumnya masih cooldown? → return
5. Apakah isTransitionCost(cost)?
     YA → eksekusi lompatan
     TIDAK → reset ICP toggle, return
```

### 3.2 Waiting Mode (`enable_waiting: true`)

Ketika robot memasuki expansion zone (cost 5), robot menunggu sebelum lompatan:

$$t_{\text{wait}} = \frac{r_{\text{expansion}}}{v_{\text{robot}}}$$

$$v_{\text{robot}} = \max(\sqrt{v_x^2 + v_y^2},\; 0.05)$$

dimana $r_{\text{expansion}} = 0.45$ m (dari `expansion_radius` TransitionExpansionLayer).

**State machine waiting:**
```
IDLE → [masuk transition zone] → WAITING
  ├── ICP disabled (toggle_icp = false) — freeze pose
  ├── transition_vel = true
  └── Countdown: 1 detik → log "waiting... Xs remaining"

WAITING → [timer habis] → EXECUTE JUMP
  └── Reset ICP toggle
```

### 3.3 Match Pair & Side

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

### 3.4 executeJump

File: `costmap_jumper.cpp:821`

**Mode traced (default — ada garis transisi hasil BFS):**

1. **Cari titik terdekat di garis sumber** — dari posisi robot ke garis transisi:

$$i^* = \arg\min_i \| p_{\text{src\_line}}[i] - p_{\text{robot}} \|^2$$

2. **Hitung rasio posisi** di sepanjang garis:

$$r = \frac{i^*}{N_{\text{src}} - 1}$$

3. **Petakan ke garis tujuan:**

$$i_{\text{dst}} = \text{round}(r \cdot (N_{\text{dst}} - 1))$$

4. **Konversi ke world coordinates:**

$$p_{\text{jump}} = \text{mapToWorld}(\text{line\_dst}[i_{\text{dst}}])$$

**Mode untraced (fallback):**

1. Hitung offset dari seed:
   $$\Delta x = c_i - \text{seed\_src}_x, \quad \Delta y = c_j - \text{seed\_src}_y$$

2. Terapkan offset yang sama ke seed tujuan:
   $$p_{\text{jump}} = \text{mapToWorld}(\text{seed\_dst}_x + \Delta x,\; \text{seed\_dst}_y + \Delta y)$$

### 3.5 Orientasi Lompatan

Jika ada `region_orientations` untuk region tujuan:

$$\text{q}_{\text{new}} = \text{q}_{\text{region}} \cdot \text{q}_{\text{current}}$$

Ini menerapkan rotasi relatif terhadap orientasi robot saat ini.

### 3.6 Publikasi

```cpp
// Publish new pose
initial_pose_pub_.publish(pose_msg);        // /initialpose

// Special: region C diulang 3x
if (dest_letter == 'C'):
    for i=0..2: publish lagi setiap 1 detik

// Signal jump selesai
transition_jumped_pub_.publish(Empty());    // /transition_jumped

// Update region
current_region_ = 'A' + pair_id + (on_side_a ? 1 : 0);
publishRegion();                            // /current_region

// Per-pair cooldown
pair_cooldown_end_[pair_id] = now + 100 detik
```

---

## 4. Interaksi dengan Node Lain

```
costmap_jumper  ──/initialpose──→  icp_loc_node
                                  (ICP memperbaiki pose)

costmap_jumper  ──/transition_jumped──→  path_interceptor
                                         (melanjutkan path)

costmap_jumper  ──/transition_jumped──→  jump_coordinator
                                         (kirim ulang goal ke move_base)

costmap_jumper  ──/current_region──→  icp_loc_node
                                      (mengaktifkan/nonaktifkan ICP)

costmap_jumper  ──transition_vel──→  path_interceptor / move_base
                                     (notifikasi kecepatan transisi)

costmap_jumper  ──/transition_centroids──→  path_interceptor
                                            (data centroid tracing)
```

---

## 5. Konfigurasi (`config/costmap_jumper.yaml`)

```yaml
pair_cooldown: 100.0       # cooldown antar lompatan pada pasangan yang sama (detik)
initial_pose_yaw: -90.0    # orientasi yaw initial pose (derajat)
enable_waiting: true       # tunggu sebelum lompatan (lewati expansion zone dulu)
jump_pose_duration: 1.0    # durasi republish jump pose (detik)
base_frame: "base_link"    # frame robot
check_rate: 20.0           # frekuensi pengecekan (Hz)
initial_jump_delay: 5.0    # delay sebelum lompatan pertama setelah startup (detik)
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
| `first_pixel_A/B` | Koordinat pixel (dalam PGM) seed untuk tracing garis A dan B |
| `pair` | ID pasangan (0, 1, …) |
| `initial_pose` | Pose awal robot saat startup [pixel_x, pixel_y] |
| `region_orientations` | Override orientasi per region (quaternion) |

---

## 6. Node Terkait

### 6.1 JumpPlanner (`jump_planner.cpp`)

Plugin `nav_core::BaseGlobalPlanner` kustom yang membuat **shortcut plan** antar area:

```cpp
bool JumpPlanner::makePlan(start, goal, plan) {
    // Konversi start & goal ke cell costmap
    sx, sy = worldToMap(start)
    gx, gy = worldToMap(goal)

    // Cari pasangan transisi yang memisahkan start dan goal
    for each pair:
        start_dekat_A = dist(sx, sy → seed_A) < dist(sx, sy → seed_B)
        goal_dekat_A  = dist(gx, gy → seed_A) < dist(gx, gy → seed_B)
        if start_dekat_A != goal_dekat_A:
            // Pair ini memisahkan — buat plan langsung
            plan = [start, seed_world, goal]
            return true

    // Tidak ada transisi → plan = [start, goal]
    plan = [start, goal]
}
```

Menggunakan `findSeparatingPair()`: pasangan transisi yang **memisahkan** start dan goal (start dekat seed A, goal dekat seed B, atau sebaliknya) berarti robot perlu melewati transisi tersebut.

### 6.2 JumpCoordinator (`jump_coordinator.cpp`)

Node sederhana yang **mengirim ulang goal** setelah lompatan:

```
1. Subscribes to /goal
   → Simpan original_goal, kirim ke move_base
2. Subscribes to /transition_jumped
   → Kirim ulang original_goal ke move_base
```

Alasan: setelah lompatan, move_base path menjadi tidak relevan (posisi robot berubah). Goal perlu dikirim ulang agar move_base menghasilkan plan baru dari posisi baru.

### 6.3 LocalPathPlanner (`local_path_planner.cpp`)

Membuat **local path** dari global plan yang ada di dalam local costmap. Berjalan pada 5 Hz:

```
1. Dapatkan pose robot dari TF
2. Cari nearest point pada global plan
3. Walk forward sejauh max_plan_lookahead (2m)
   → kumpulkan semua waypoint yang di dalam bounds local costmap
4. Untuk setiap waypoint: jika untraversable, snap ke cell traversable terdekat
5. Publish sebagai local path
```

### 6.4 SimpleTrajectoryFollower (`simple_trajectory_follower.cpp`)

Pure-pursuit controller sederhana:

```
1. Cari closest point pada plan ke robot
2. Walk forward sejauh lookahead_distance (0.5m) → target point
3. Hitung arah ke target → vektor (dx, dy)
4. Kecepatan trapezoidal:
     v = max_speed jika jauh
     v = min_speed + (max-min)*(dist/decel_dist) jika dekat goal
5. Kirim cmd_vel
```

$$v = \min\left(v_{\text{max}},\; v_{\text{min}} + (v_{\text{max}} - v_{\text{min}}) \cdot \frac{d_{\text{to\_goal}}}{d_{\text{decel}}}\right)$$

---

## 7. Kompleksitas

| Operasi | Kompleksitas | Keterangan |
|---|---|---|
| BFS tracing (8-way flood fill) | $O(N_t)$ | $N_t$ = jumlah cell transisi dalam satu komponen |
| BFS ordering | $O(N_t)$ | Satu kunjungan per cell |
| Seed search (radius 5) | $O(r^2) = 25$ | Konstan |
| Match pair & side | $O(P)$ | $P$ = jumlah pasangan (biasanya 1–3) |
| Check timer callback | $O(1)$ | Per 0.05 detik (20 Hz) |
| Publish centroid | $O(P \cdot N_t)$ | Per update costmap |

---

## 8. Referensi File

| File | Isi |
|---|---|
| `costmap_jumper.cpp` | Node utama: deteksi transisi, BFS tracing, eksekusi lompatan |
| `costmap_jumper.yaml` | Konfigurasi: cooldown, waiting, initial pose |
| `jump_planner.h/.cpp` | Plugin global planner: shortcut plan lewat transisi |
| `jump_coordinator.cpp` | Re-send goal setelah lompatan |
| `local_path_planner.cpp` | Ekstrak local path dari global plan |
| `simple_trajectory_follower.cpp` | Pure-pursuit controller |
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
