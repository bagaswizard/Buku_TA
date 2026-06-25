# i_see_pee — ICP-Based 2D Localization untuk ROS

Package ini melakukan **2D robot localization** menggunakan algoritma **Iterative Closest Point (ICP)**. Scan-to-map matching memperkirakan koreksi pose robot terhadap static occupancy grid map. Semua kode ada di `src/icp_loc/`, dengan logika inti di `include/i_see_pee/` dan `src/i_see_pee.cpp`.

---

## Arsitektur

```
i_see_pee_node                              (src/i_see_pee_node.cpp)
  └── controller                            (src/i_see_pee.cpp:786)
        ├── icp::scan_matcher               (src/i_see_pee.cpp:369)
        │     ├── map::interface            (src/i_see_pee.cpp:297)
        │     ├── sampler                   (src/i_see_pee.cpp:348)
        │     └── conversion_checker        (src/i_see_pee.cpp:333)
        ├── scan::interface                 (src/i_see_pee.cpp:247)
        └── odom::frame_handler             (src/i_see_pee.cpp:288)
```

`controller::update()` adalah fungsi utama yang dipanggil setiap kali laser scan masuk. Alurnya:

1. Ambil pose robot dari odometry
2. Transform laser scan ke frame `map`
3. Jalankan ICP untuk menghitung koreksi pose
4. Terapkan koreksi, broadcast TF yang sudah diperbaiki

---

## Namespace

| Namespace | File | Fungsi |
|---|---|---|
| `internal` | `i_see_pee.cpp:9-79` | Konversi tipe ROS ↔ Eigen (`Time`, `Transform`, `Quaternion`) |
| `map` | `i_see_pee.cpp:81-331` | Precompute KNN dari occupancy grid, simpan di hash table |
| `scan` | `i_see_pee.cpp:333-425` | Konversi LaserScan → Cartesian point cloud, caching |
| `odom` | `i_see_pee.cpp:427-567` | Manajemen TF frame (`map`, `odom`, `base_link`) |
| `icp` | `i_see_pee.cpp:569-783` | Algoritma ICP: matching, SVD solver, convergence check |
| `controller` | `i_see_pee.cpp:786-862` | Glue logic: hubungkan scan → ICP → odom |

---

## 1. Preprocessing Map — Prekomputasi KNN

### Masalah

ICP membutuhkan pencarian titik terdekat (nearest neighbor) antara laser scan dan map. Umumnya ini menggunakan K-D tree dengan kompleksitas $O(D \log M)$ per lookup.

### Solusi: Precompute Semua Kemungkinan

Karena occupancy grid bersifat **diskrit** dan ukurannya **terbatas**, kita bisa menghitung semua kemungkinan nearest neighbors **sebelum runtime** dan menyimpannya di hash table. Ini membuat lookup saat runtime menjadi $O(1)$.

Setiap cell dalam grid menyimpan daftar hingga $K$ occupied cells terdekat (diurutkan berdasarkan jarak Euclidean).

### Algoritma (`map::interpret`, `i_see_pee.cpp:235`)

Untuk **setiap occupied cell** dalam grid:

1. **Cek reachability**: Apakah setidaknya satu dari 8 tetangganya (Moore neighborhood 3×3) adalah free cell? Jika tidak (misalnya cell di tengah tembok tebal), skip — laser tidak akan pernah sampai ke sana.

2. **Iterasi cell tetangga**: Gunakan `circle_iterator` (`iterator.hpp:83`) untuk mengunjungi semua cell dalam radius $r$ (dalam satuan cell) dari occupied cell tersebut.

3. **Insert ke daftar KNN**: Untuk setiap cell tetangga $i_{\text{nb}}$, masukkan posisi occupied cell ke dalam daftar KNN milik $i_{\text{nb}}$. Daftar dijaga tetap terurut dengan `maybe_insert` (`utils.hpp:20`), dan dibatasi maksimal $K$ entry.

### Storage

```cpp
std::unordered_map<index_t, std::vector<position_t>> knn_;
```

Key `index_t` adalah flat 1D index:

$$i = x + y \cdot W$$

dimana $W$ adalah lebar grid.

### Contoh Visual

```
Grid 6×6:
  . . . # . .
  . . # # . .
  . . . . . .
  . . . # . .
  . . . . . .
  . . . . . .
  (. = free, # = occupied, K=3, r=2)

Occupied cell (3,0):
  → circle radius 2: (1,0) (2,0) (3,0) (4,0) (5,0) (2,1) (3,1) (4,1) (3,2)
  → Masing-masing cell ini mendapat (3,0) di daftar KNN-nya
  → Contoh: knn_[(2,0)] = [(3,0) dist=1, (2,1) dist=√2, (3,1) dist=√2]

Setelah semua occupied cell diproses, hash table siap digunakan runtime.
```

---

## 2. Scan Processing (`scan` namespace)

### Cache Trigonometri (`scan::cache`, `i_see_pee.cpp:365`)

Untuk setiap konfigurasi scan, precompute matriks $2 \times N$:

$$C = \begin{bmatrix} \cos\theta_0 & \cos\theta_1 & \dots & \cos\theta_{N-1} \\ \sin\theta_0 & \sin\theta_1 & \dots & \sin\theta_{N-1} \end{bmatrix}$$

Cache hanya dihitung ulang jika parameter scan berubah.

### Konversi LaserScan ke Point Cloud (`scan::interface_::callback`, line 381)

Diberikan range readings $r_0, r_1, \dots, r_{N-1}$:

$$S = \begin{bmatrix} r_0\cos\theta_0 & r_1\cos\theta_1 & \dots \\ r_0\sin\theta_0 & r_1\sin\theta_1 & \dots \end{bmatrix}$$

Implementasi: perkalian element-wise antara cache dan range readings.

---

## 3. Algoritma ICP (`icp` namespace)

### 3.1 Outer Loop (`scan_matcher::operator()`, line 751)

```
T = Identity
for i = 1 to max_iter:
    scan_sample = sampler(scan)       // subsample dengan random stride
    scan_tf     = T * scan_sample     // transform ke map frame
    M           = matches(scan_tf, knn) // cari correspondences
    w           = get_weights(M)      // hitung weight
    T_update    = point_to_map(M, w)  // SVD solver
    T           = T_update * T        // akumulasi
    if converged(T_update): break
return T
```

### 3.2 Correspondence Matching (`matches`, line 574)

Untuk setiap sensor point $s_j$ setelah di-transform ke frame map:

1. Validasi: apakah $s_j$ berada dalam batas map?
2. Hitung flat index: $i = \text{converter.to\_index}(s_j)$
3. Lookup: `knn_[i]` mengembalikan hingga $K$ occupied map points terdekat
4. Duplikasi: $s_j$ dipasangkan dengan setiap nearest neighbor-nya

Hasil: dari $N$ sensor points menjadi $N \times K$ pasangan $(s_j, m_{j,k})$.

### 3.3 Weighting (`get_weights`, line 615)

Saat ini semua pasangan diberi weight seragam:

$$w_i = 1 \quad \forall i$$

Kode memiliki placeholder untuk weighting berdasarkan jarak tetapi belum diaktifkan.

### 3.4 Solusi SVD / Point-to-Map (`point_to_map`, line 632)

Diberikan $M$ pasangan $\{s_i\}$ (sensor) dan $\{m_i\}$ (map) dengan weights $\{w_i\}$, kita mencari rigid transform $T \in SE(2)$ yang meminimalkan:

$$T^* = \arg\min_{R,\,t} \sum_{i=1}^{M} w_i \, \big\| m_i - (R s_i + t) \big\|^2$$

#### Langkah 1: Weighted Centroids

$$\bar{s} = \frac{\sum_{i=1}^{M} w_i s_i}{\sum_{i=1}^{M} w_i}, \qquad \bar{m} = \frac{\sum_{i=1}^{M} w_i m_i}{\sum_{i=1}^{M} w_i}$$

#### Langkah 2: Centering (pindahkan titik ke pusat koordinat)

$$s_i' = s_i - \bar{s}, \qquad m_i' = m_i - \bar{m}$$

#### Langkah 3: Cross-Covariance Matrix

$$H = \sum_{i=1}^{M} w_i \, m_i' (s_i')^\top = M \, W \, S^\top$$

dimana $S, M \in \mathbb{R}^{2 \times M}$ adalah matriks yang kolomnya berisi titik-titik yang sudah di-center, dan $W = \operatorname{diag}(w_1, \dots, w_M)$.

#### Langkah 4: Singular Value Decomposition

$$H = U \Sigma V^\top$$

dengan $U, V \in \mathbb{R}^{2 \times 2}$ orthonormal dan $\Sigma = \operatorname{diag}(\sigma_1, \sigma_2)$.

#### Langkah 5: Rotasi Optimal

$$R = U V^\top$$

Jika $\det(R) < 0$ (menghasilkan refleksi, bukan rotasi murni), koreksi dengan membalik tanda baris pertama $V^\top$:

$$\text{if } \det(R) < 0: \quad V^\top_{0,:} \gets -V^\top_{0,:}, \quad R = U V^\top$$

#### Langkah 6: Translasi Optimal

$$t = \bar{m} - R \bar{s}$$

#### Langkah 7: Susun Rigid Transform 2D

$$T_{\text{update}} = \begin{bmatrix} R & t \\ 0 & 1 \end{bmatrix} = \begin{bmatrix} \cos\Delta\theta & -\sin\Delta\theta & t_x \\ \sin\Delta\theta & \cos\Delta\theta & t_y \\ 0 & 0 & 1 \end{bmatrix}$$

### 3.5 Convergence Check (`conversion_checker`, line 685)

Setelah iterasi, cek apakah transform update cukup kecil:

```cpp
t_curr  = norm(t)                                // magnitude translasi
angle   = |atan2(R(1,0), R(0,0))|                // magnitude rotasi
return t_norm > t_curr && r_norm > angle
```

$$\text{converged} \iff \|t\| < t_{\text{norm}} \land \big|\arctan2(R_{1,0}, R_{0,0})\big| < r_{\text{norm}}$$

Default: $t_{\text{norm}} = 0.01$ m, $r_{\text{norm}} = 0.01$ rad ($\approx 0.57^\circ$).

### 3.6 Random Stride Subsampling (`sampler`, line 717)

Untuk mempercepat, hanya $1/s$ dari scan points yang digunakan:

1. Pilih offset acak $o \in [0, s-1]$
2. Ambil setiap point ke-$s$ mulai dari $o$:

$$p_k' = p_{o + k \cdot s}, \quad k = 0, 1, \dots, \left\lfloor \frac{N}{s} \right\rfloor - 1$$

Default $s = 3$ (gunakan ~33% dari scan points).

---

## 4. Frame Management (`odom` namespace)

### Frame Tree

```
map ───T_map→odom───→ odom ───T_odom→base───→ base_link ───T_base→sensor───→ laser_frame
```

### Update Pose (`controller::update`, line 834)

Setiap kali laser scan masuk:

```
1. T_base→sensor   = lookup TF static base→laser_frame
2. T_map→base       = odometry integration (T_map→base * ΔT_odom)
3. T_map→sensor     = T_map→base · T_base→sensor
4. scan_map         = T_map→sensor · scan_points     (scan → frame map)
5. T_icp            = icp(scan_map)                   (koreksi ICP)
6. T_map→base       = T_icp · T_map→base             (terapkan koreksi)
7. T_map→odom       = T_map→base · (T_odom→base)⁻¹   (rebase odom)
8. broadcast TF map→base_link dan map→odom
```

### Koreksi Odometric Drift

Hubungan kunci:

$$T_{\text{map} \to \text{odom}} = T_{\text{map} \to \text{base}} \cdot T_{\text{odom} \to \text{base}}^{-1}$$

ICP memperbaiki $T_{\text{map} \to \text{base}}$, yang secara otomatis menggeser frame `odom` relatif terhadap `map`. Ini mengoreksi drift odometry tanpa mengubah estimasi robot di frame odom.

---

## 5. Kompleksitas

| Operasi | Kompleksitas | Keterangan |
|---|---|---|
| Precompute KNN | $O(|G| \cdot r^2 \cdot \log K)$ | Sekali, saat map diterima |
| KNN lookup runtime | $O(1)$ | Hash table lookup per scan beam |
| SVD | $O(N)$ | Per iterasi ICP ($N$ = jumlah matched points) |
| Total per scan | $O(N \cdot K \cdot I)$ | $I \approx 50$ iterasi (konvergen lebih cepat) |

Notasi: $|G|$ = occupied cells, $r$ = search radius, $K$ = K nearest neighbors, $N$ = scan beams (setelah stride), $I$ = iterasi ICP.

---

## 6. Alur Data End-to-End

```
/map (OccupancyGrid)              /scan (LaserScan)
        │                              │
        ▼                              ▼
  map::interpret()              scan::interface_::callback()
        │                              │
        ▼                              ▼
  hash table knn_               point cloud (2×N)
  (precomputed KNN)                   │
                                      │
                                      ▼
                              Transform ke frame map
                              (via odometry + TF)
                                      │
                                      ▼
                              icp::scan_matcher()
                                │
                                ├── sampler (subsample)
                                ├── matches (KNN lookup)
                                ├── point_to_map (SVD)
                                └── convergence check
                                      │
                                      ▼
                              Koreksi pose T_icp
                                      │
                                      ▼
                              Update T_map→base
                              Broadcast TF
```

---

## 7. Konfigurasi (`config/icp_config.yaml`)

```yaml
map:
  topic: "/map"       # topic occupancy grid
  k: 8                # K nearest neighbors (1–10)
  radius: 10          # search radius dalam cell (0–10)

scan:
  topic: "/scan"      # topic laser scan

odom:
  map_frame: "map"
  odom_frame: "odom"
  base_frame: "base_link"

icp:
  enable_icp: true
  t_norm: 0.01        # threshold translasi (m)
  r_norm: 0.01        # threshold rotasi (rad)
  max_iter: 50        # maksimum iterasi (1–100)
  stride: 3           # random subsample stride (1–100)
```

---

## 8. Referensi File

| File | Isi |
|---|---|
| `include/i_see_pee/i_see_pee.hpp` | Semua type definitions, deklarasi struct/class |
| `src/i_see_pee.cpp` | Semua implementasi fungsi |
| `include/i_see_pee/utils.hpp` | Helper `cast_to_range`, `maybe_insert` |
| `include/i_see_pee/iterator.hpp` | Iterator untuk traversal grid: `submap_iterator`, `circle_iterator` |
| `include/i_see_pee/debug.hpp` | Publisher opsional untuk visualisasi point cloud |
| `include/i_see_pee/macros.hpp` | Macro logging `I_SEE_PEE_INFO/WARN/DEBUG` |
| `src/i_see_pee_node.cpp` | Entry point: `main()`, instansiasi `controller`, `ros::spin()` |
