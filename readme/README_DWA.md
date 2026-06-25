# DWA Local Planner — Penjelasan Lengkap

Dokumen ini menjelaskan cara kerja **Dynamic Window Approach (DWA)** — algoritma local planner yang digunakan untuk navigasi robot di lingkungan yang dinamis. Implementasi ada di `src/dwa_local_planner/` (ROS wrapper) dan `src/base_local_planner/` (infrastruktur trajectory generation dan scoring).

---

## Arsitektur

```
move_base
  └── Costmap2DROS (local_costmap)
        └── DWAPlannerROS (dwa_local_planner)
              └── DWAPlanner
                    ├── SimpleTrajectoryGenerator
                    │     └── VelocityIterator
                    ├── SimpleScoredSamplingPlanner
                    │     ├── OscillationCostFunction
                    │     ├── ObstacleCostFunction
                    │     │     └── CostmapModel
                    │     ├── MapGridCostFunction (path_costs_)
                    │     ├── MapGridCostFunction (goal_costs_)
                    │     ├── MapGridCostFunction (goal_front_costs_)
                    │     ├── MapGridCostFunction (alignment_costs_)
                    │     └── TwirlingCostFunction
                    └── LatchedStopRotateController
```

---

## 1. Dynamic Window Approach — Konsep Dasar

DWA adalah algoritma **local path planning** yang bekerja dengan cara:

1. **Sample** semua kemungkinan kecepatan $(v_x, v_y, \omega)$ yang **dapat dicapai** dalam satu control cycle (Dynamic Window)
2. **Simulasikan** trajectory untuk setiap sample kecepatan menggunakan model kinematik robot
3. **Skor** setiap trajectory berdasarkan:
   - Seberapa dekat ke global plan
   - Seberapa dekat ke goal
   - Seberapa jauh dari obstacle
   - Osilasi yang dicegah
4. **Pilih** trajectory dengan skor terbaik
5. **Kirim** perintah kecepatan dari trajectory terbaik ke motor

---

## 2. Dynamic Window (Velocity Search Space)

File: `simple_trajectory_generator.cpp`

### 2.1 Konsep Dynamic Window

Perbedaan utama DWA dengan Trajectory Rollout:

**DWA** — Velocity window dibatasi oleh apa yang **dapat dicapai dalam satu control cycle**:

$$v_{\text{min}} = \max\left(v_{\text{min\_limit}},\; v_{\text{current}} - \dot{v}_{\text{max}} \cdot \Delta t\right)$$

$$v_{\text{max}} = \min\left(v_{\text{max\_limit}},\; v_{\text{current}} + \dot{v}_{\text{max}} \cdot \Delta t\right)$$

dimana $\Delta t$ adalah `sim_period_` ≈ 0.05 s (waktu satu siklus kontrol).

**Trajectory Rollout** — Velocity window dibatasi oleh apa yang dapat dicapai **selama waktu simulasi penuh**:

$$v_{\text{max}} = \min\left(v_{\text{max\_limit}},\; v_{\text{current}} + \dot{v}_{\text{max}} \cdot T_{\text{sim}}\right)$$

dimana $T_{\text{sim}}$ adalah `sim_time_` ≈ 1.3–1.7 s.

### 2.2 Velocity Sampling

Untuk setiap dimensi $(v_x, v_y, \omega)$, rentang dibagi menjadi sample merata:

$$\Delta v_x = \frac{v_{x,\text{max}} - v_{x,\text{min}}}{N_{v_x} - 1}$$

$$\Delta v_y = \frac{v_{y,\text{max}} - v_{y,\text{min}}}{N_{v_y} - 1}$$

$$\Delta \omega = \frac{\omega_{\text{max}} - \omega_{\text{min}}}{N_{\omega} - 1}$$

Total trajectory yang di-sample:

$$N_{\text{total}} = N_{v_x} \times N_{v_y} \times N_{\omega}$$

Konfigurasi dari yaml: $N_{v_x} = 6$, $N_{v_y} = 6$, $N_{\omega} = 30$ → total 1080 trajectories per evaluasi.

---

## 3. Forward Simulation

File: `simple_trajectory_generator.cpp:180`

### 3.1 Model Kinematik

Untuk setiap sample kecepatan $(v_x, v_y, \omega)$, trajectory disimulasikan menggunakan model kinematik diferensial:

$$x_{t+1} = x_t + \left(v_x \cos\theta_t + v_y \cos\left(\frac{\pi}{2} + \theta_t\right)\right) \cdot \Delta t$$

$$y_{t+1} = y_t + \left(v_x \sin\theta_t + v_y \sin\left(\frac{\pi}{2} + \theta_t\right)\right) \cdot \Delta t$$

$$\theta_{t+1} = \theta_t + \omega \cdot \Delta t$$

Implementasi di `simple_trajectory_generator.cpp`:

```cpp
new_pos[0] = pos[0] + (vel[0] * cos(pos[2]) + vel[1] * cos(M_PI_2 + pos[2])) * dt;
new_pos[1] = pos[1] + (vel[0] * sin(pos[2]) + vel[1] * sin(M_PI_2 + pos[2])) * dt;
new_pos[2] = pos[2] + vel[2] * dt;
```

### 3.2 Number of Steps

Jumlah langkah simulasi ditentukan oleh granularity:

$$N_{\text{steps}} = \frac{T_{\text{sim}}}{\Delta t}$$

$$\Delta t = \min\left(\frac{\text{sim\_granularity}}{|v|},\; \frac{\text{angular\_sim\_granularity}}{|\omega|}\right)$$

### 3.3 Acceleration Modeling (Non-DWA mode only)

Pada mode Trajectory Rollout (`use_dwa = false`), kecepatan diperbarui setiap langkah menuju target sample velocity:

$$v_{t+1} = v_t + \dot{v}_{\text{sampel}} \cdot \Delta t$$

$$v_{t+1} = \text{clamp}(v_{t+1}, v_{\text{min}}, v_{\text{max}})$$

---

## 4. Trajectory Scoring Pipeline

File: `dwa_planner.cpp`, `simple_scored_sampling_planner.cpp`

### 4.1 Urutan Cost Functions

```cpp
critics[0] = oscillation_costs_      // Mencegah osilasi
critics[1] = obstacle_costs_         // Menghindari obstacle
critics[2] = goal_front_costs_       // Hidung robot mengarah ke goal
critics[3] = alignment_costs_        // Hidung robot sejajar path
critics[4] = path_costs_             // Robot mengikuti path
critics[5] = goal_costs_             // Robot menuju goal
critics[6] = twirling_costs_         // Penalti rotasi berlebih
```

### 4.2 Algoritma Scoring

```python
def scoreTrajectory(traj, best_cost):
    total_cost = 0
    for each critic c:
        if c.scale == 0: continue
        cost = c.scoreTrajectory(traj)
        if cost < 0:        # negative = invalid
            return cost
        total_cost += cost * c.scale
        if best_cost > 0 and total_cost > best_cost:
            break           # early termination
    return total_cost
```

### 4.3 Total Cost Function

$$C_{\text{total}} = C_{\text{osc}} + w_{\text{obs}} \cdot C_{\text{obs}} + w_{\text{gf}} \cdot C_{\text{gf}} + w_{\text{align}} \cdot C_{\text{align}} + w_{\text{path}} \cdot C_{\text{path}} + w_{\text{goal}} \cdot C_{\text{goal}} + w_{\text{twirl}} \cdot C_{\text{twirl}}$$

---

## 5. Cost Function Details

### 5.1 OscillationCostFunction

File: `oscillation_cost_function.cpp`

**Tujuan**: Mencegah robot bergerak maju-mundur atau berputar kiri-kanan secara bergantian (osilasi).

**Mekanisme**: Melacak arah pergerakan yang telah digunakan. Jika arah berlawanan dicoba, arah tersebut diblokir:

$$C_{\text{osc}} = \begin{cases} -5.0 & \text{if direction forbidden} \\ 0.0 & \text{otherwise} \end{cases}$$

**Reset**: Flag osilasi di-reset ketika robot bergerak lebih dari `oscillation_reset_dist_` (0.05 m) atau berputar lebih dari `oscillation_reset_angle_` (0.2 rad) dari posisi flag pertama kali diset.

Arah yang dilacak:
- Forward / Backward
- Strafe Left / Strafe Right
- Rotate Left / Rotate Right

### 5.2 ObstacleCostFunction

File: `obstacle_cost_function.cpp`

**Tujuan**: Memberi penalti pada trajectory yang mendekati atau menabrak obstacle.

#### 5.2.1 Footprint Scaling

Semakin cepat robot bergerak, footprint diperbesar untuk memberikan safety margin:

$$s = \begin{cases} 1.0 & \text{if } v \leq v_{\text{scaling}} \\ 1.0 + s_{\text{max}} \cdot \frac{v - v_{\text{scaling}}}{v_{\text{max}} - v_{\text{scaling}}} & \text{if } v > v_{\text{scaling}} \end{cases}$$

dimana:
- $v = \sqrt{v_x^2 + v_y^2}$ (linear velocity magnitude)
- $v_{\text{scaling}} = 0.25$ m/s (scaling_speed)
- $s_{\text{max}} = 0.2$ (max_scaling_factor)

#### 5.2.2 Collision Checking

Setiap titik sepanjang trajectory, footprint robot di-rasterize ke costmap:

```cpp
footprintCost(x, y, theta, scaled_footprint)
```

Menggunakan Bresenham line drawing untuk menelusuri setiap tepi footprint polygon di grid costmap.

#### 5.2.3 Agregasi Cost

Mode `sum_scores`:

$$C_{\text{obs}} = \begin{cases} \sum_{k=1}^{N} C_k & \text{if sum\_scores} \\ \max_k C_k & \text{otherwise} \end{cases}$$

**Collision detection**: Jika ada footprint cell dengan `LETHAL_OBSTACLE` (254), return `-6.0`. Jika off-map, return `-7.0`.

### 5.3 MapGridCostFunction

File: `map_grid_cost_function.cpp`

**Tujuan**: Menilai trajectory berdasarkan jarak ke global plan atau goal.

#### 5.3.1 Wavefront Propagation

`MapGrid` menggunakan BFS untuk menyebarkan nilai jarak dari target cells:

```
1. Reset semua cell ke obstacleCosts()
2. Set target cells (path waypoints atau goal point) → distance = 0
3. BFS: setiap tetangga yang bukan obstacle mendapat distance = parent_distance + 1
4. Berhenti di LETHAL_OBSTACLE, INSCRIBED_INFLATED_OBSTACLE, NO_INFORMATION
```

$$d_{\text{cell}} = \text{number of BFS steps from nearest target cell}$$

#### 5.3.2 Scoring Mode

Untuk setiap titik pada trajectory, nilai `target_dist` dari MapGrid dibaca.

**Aggregation type:**

| Mode | Formula | Kegunaan |
|---|---|---|
| `Last` | $C = d_N$ (jarak di titik terakhir) | Goal cost |
| `Sum` | $C = \sum_{k=1}^{N} d_k$ | Path cost |
| `Product` | $C = \prod_{k=1}^{N} d_k$ | Jarang digunakan |

#### 5.3.3 Forward Point Shift

Untuk `goal_front_costs_` dan `alignment_costs_`, titik scoring digeser ke depan sejauh `forward_point_distance_`:

$$p_{\text{score}} = p_{\text{robot}} + d_{\text{forward}} \cdot \begin{pmatrix} \cos\theta \\ \sin\theta \end{pmatrix}$$

#### 5.3.4 Path Costs ($C_{\text{path}}$)

```cpp
path_costs_.setTargetPoses(global_plan)
// Semua waypoints dalam local costmap menjadi seed BFS
```

Weight: $w_{\text{path}} = \text{resolution} \cdot \text{path\_distance\_bias}$

#### 5.3.5 Goal Costs ($C_{\text{goal}}$)

```cpp
goal_costs_.setLocalGoal(global_plan)
// Hanya titik terakhir yang reachable menjadi seed BFS
```

Weight: $w_{\text{goal}} = \text{resolution} \cdot \text{goal\_distance\_bias}$

#### 5.3.6 Goal Front Costs ($C_{\text{gf}}$)

Menggunakan forward point shift. Menilai apakah **hidung robot** mengarah ke goal.

$$p_{\text{hidung}} = p_{\text{robot}} + d_{\text{forward}} \cdot \hat{v}$$

$$C_{\text{gf}} = \text{target\_dist}(p_{\text{hidung}})$$

Weight: sama dengan goal costs, tetapi di-nol-kan jika `forward_point_distance <= 0`.

#### 5.3.7 Alignment Costs ($C_{\text{align}}$)

Sama dengan path costs, tetapi dengan forward point shift. Menilai apakah hidung robot sejajar dengan path.

Dinonaktifkan jika robot sudah dekat dengan goal:

$$\text{disabled if } \|p_{\text{robot}} - p_{\text{goal}}\| < d_{\text{forward}} \cdot \text{cheat\_factor}$$

### 5.4 TwirlingCostFunction

File: `twirling_cost_function.cpp`

**Tujuan**: Memberi penalti pada rotasi berlebih.

$$C_{\text{twirl}} = |\omega|$$

Weight: $w_{\text{twirl}} = \text{twirling\_scale}$ (default 0.0 — disabled).

---

## 6. Best Trajectory Selection

File: `simple_scored_sampling_planner.cpp:81`

```
1. Prepare semua critics:
     - MapGridCostFunction::prepare() → wavefront BFS propagation
2. Iterate semua trajectory dari generator:
     a. GenerateTrajectory(pos, vel, sample_vel, &traj)
     b. scoreTrajectory(traj, best_cost)
     c. Jika cost >= 0 dan cost < best_cost → update best trajectory
3. Jika tidak ada trajectory valid → gunakan zero velocity
```

**Early termination**: Jika total cost sudah melebihi `best_cost` saat menjumlahkan critics, evaluasi trajectory dihentikan lebih awal.

---

## 7. Stop and Goal Handling

File: `latched_stop_rotate_controller.cpp`

Saat robot mencapai goal position (dalam `xy_goal_tolerance`):

1. **Stop**: Kirim velocity = 0
2. **Rotate**: Putar ke goal orientation menggunakan:
   - Proportional controller: $\omega = \text{latch\_rot\_vel} \cdot \text{sign}(\theta_{\text{error}})$
3. **Selesai**: Ketika $\theta_{\text{error}} < \text{yaw\_goal\_tolerance}$

```python
def computeVelocityCommands(pose, cmd_vel):
    if robot_at_goal_position(pose, xy_goal_tolerance):
        if robot_at_goal_orientation(pose, yaw_goal_tolerance):
            return goal_reached()
        else:
            cmd_vel.linear.x = stop_linear_vel
            cmd_vel.angular.z = rotate_to_goal(latch_rot_vel)
    else:
        return dwaComputeVelocityCommands(pose, cmd_vel)
```

---

## 8. Alur Data End-to-End

```
move_base menerima goal (PoseStamped)
    │
    ▼
global_planner (navfn/NavfnROS)
    │   menghasilkan global plan (path dari start ke goal)
    ▼
DWAPlannerROS::computeVelocityCommands()
    │
    ├── 1. Get robot pose dari costmap TF
    ├── 2. Transform global plan ke local frame
    │         (potong start plan, ambil waypoints dalam local costmap)
    ├── 3. updatePlanAndLocalCosts()
    │         obstacle_cost.setFootprint(footprint)
    │         path_cost.setTargetPoses(global_plan)
    │         goal_cost.setLocalGoal(global_plan)
    │
    ├── 4. LatchedStopRotateController
    │         if at goal: stop + rotate to orientation
    │
    ├── 5. dwaComputeVelocityCommands()
    │
    │   DWAPlanner::findBestPath()
    │   ├── generator_.initialise(pos, vel, goal, limits, vsamples)
    │   │     └── Hitung Dynamic Window:
    │   │           vx ∈ [max(min_vx, vx - ax·dt),  min(max_vx, vx + ax·dt)]
    │   │           vy ∈ [max(min_vy, vy - ay·dt),  min(max_vy, vy + ay·dt)]
    │   │           ω  ∈ [max(min_ω, ω - aθ·dt),   min(max_ω, ω + aθ·dt)]
    │   │     └── VelocityIterator: Nx × Ny × Nθ = 1080 samples
    │   │
    │   ├── scored_sampling_planner_.findBestTrajectory()
    │   │     ├── prepare() → wavefront BFS untuk path/goal distances
    │   │     │
    │   │     ├── for each velocity sample:
    │   │     │     ├── generateTrajectory()
    │   │     │     │     └── Forward simulation selama sim_time
    │   │     │     │         pos(t+1) = pos(t) + vel·dt
    │   │     │     │
    │   │     │     └── scoreTrajectory()
    │   │     │           ├── OscillationCost:  0 atau -5.0
    │   │     │           ├── ObstacleCost:     footprint collision checking
    │   │     │           ├── GoalFrontCost:    jarak hidung → shifted goal
    │   │     │           ├── AlignmentCost:    jarak hidung → path
    │   │     │           ├── PathCost:         jarak robot → path
    │   │     │           ├── GoalCost:         jarak robot → goal
    │   │     │           └── TwirlingCost:     |ω| * twirling_scale
    │   │     │
    │   │     └── hasil: trajectory dengan total cost terendah
    │   │
    │   ├── oscillation_costs_.updateOscillationFlags()
    │   └── return best_trajectory (atau zero velocity)
    │
    └── 6. Extract velocity command dari best trajectory
    │
    ▼
    cmd_vel dikirim ke /cmd_vel topic
        │
        ▼
    Robot bergerak → odometry update → costmap update → repeat
```

---

## 9. Konfigurasi

### 9.1 Parameter DWA (`config/dwa_planner.yaml`)

```yaml
DWAPlannerROS:
  max_vel_x: 0.8
  min_vel_x: -0.8
  max_vel_y: 0.8
  min_vel_y: -0.8
  max_vel_trans: 1
  min_vel_trans: 0.5
  max_vel_theta: 1.2
  min_vel_theta: -1.2
  acc_lim_x: 0.8
  acc_lim_y: 0.5
  acc_lim_theta: 1.6
  acc_lim_trans: 0.7

  yaw_goal_tolerance: 0.1
  xy_goal_tolerance: 0.15
  latch_xy_goal_tolerance: true

  sim_time: 1.3
  sim_granularity: 0.01
  angular_sim_granularity: 0.034

  vx_samples: 6
  vy_samples: 6
  vtheta_samples: 30

  path_distance_bias: 32.0
  goal_distance_bias: 1.0
  occdist_scale: 0.01
  forward_point_distance: 0.0
  stop_time_buffer: 0.2

  scaling_speed: 0.25
  max_scaling_factor: 0.1

  oscillation_reset_dist: 0.05
  publish_traj_pc: true
  publish_cost_grid_pc: true
  holonomic_robot: true
  global_frame_id: odom
```

### 9.2 Local Costmap (`config/local_costmap.yaml`)

```yaml
local_costmap:
  global_frame: odom
  robot_base_frame: base_link
  update_frequency: 5.0
  publish_frequency: 2.0
  static_map: false
  rolling_window: true
  width: 8.0
  height: 8.0
  resolution: 0.01
  plugins:
    - {name: obstacle_layer, type: costmap_2d::ObstacleLayer}
    - {name: inflation_layer, type: costmap_2d::InflationLayer}
```

### 9.3 Interpretasi Parameter

| Parameter | Nilai | Efek |
|---|---|---|
| `path_distance_bias: 32.0` | Sangat tinggi | Robot sangat patuh mengikuti global plan |
| `goal_distance_bias: 1.0` | Rendah | Goal bukan prioritas utama (path lebih penting) |
| `occdist_scale: 0.01` | Sangat rendah | Obstacle avoidance tidak dominan (costmap inflation yang handle) |
| `forward_point_distance: 0.0` | Disabled | Tidak ada forward point shift |
| `vx/vy/vtheta_samples` | 6/6/30 | 1080 trajectories per evaluasi |
| `holonomic_robot: true` | Enabled | Robot bisa strafe (bergerak ke samping) |

---

## 10. Kompleksitas

| Operasi | Kompleksitas | Keterangan |
|---|---|---|
| Velocity window | $O(1)$ | Perhitungan batas kecepatan |
| Trajectory sampling | $O(N_{v_x} \cdot N_{v_y} \cdot N_{\omega})$ | 1080 trajectories |
| Forward simulation | $O(N_{\text{traj}} \cdot N_{\text{steps}})$ | ~1080 × 100 steps |
| Footprint collision | $O(N_{\text{traj}} \cdot N_{\text{steps}} \cdot N_{\text{edges}})$ | Setiap edge di-rasterize |
| Wavefront BFS | $O(W \cdot H)$ | Seluruh local costmap (800×800 cells) |
| **Total per evaluasi** | $O(N_{\text{traj}} \cdot N_{\text{steps}} + W \cdot H)$ | ~5 Hz update frequency |

---

## 11. Referensi File

| File | Isi |
|---|---|
| `dwa_local_planner/src/dwa_planner_ros.cpp` | ROS wrapper: computeVelocityCommands, dynamic reconfigure |
| `dwa_local_planner/src/dwa_planner.cpp` | Core DWA: setup critics, findBestPath |
| `dwa_local_planner/include/dwa_local_planner/dwa_planner.h` | Header DWAPlanner class |
| `dwa_local_planner/cfg/DWAPlanner.cfg` | Dynamic reconfigure parameter definitions |
| `base_local_planner/src/simple_trajectory_generator.cpp` | Velocity sampling + forward simulation |
| `base_local_planner/src/simple_scored_sampling_planner.cpp` | Trajectory scoring + best selection |
| `base_local_planner/src/obstacle_cost_function.cpp` | Footprint collision checking |
| `base_local_planner/src/oscillation_cost_function.cpp` | Oscillation prevention |
| `base_local_planner/src/map_grid_cost_function.cpp` | Path/goal distance scoring |
| `base_local_planner/src/twirling_cost_function.cpp` | Rotational penalty |
| `base_local_planner/src/map_grid.cpp` | Wavefront distance propagation (BFS) |
| `base_local_planner/src/costmap_model.cpp` | Costmap footprintCost, lineCost, pointCost |
| `base_local_planner/src/latched_stop_rotate_controller.cpp` | Final stop + rotate to goal |
