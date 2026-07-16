-make flowchart and fix icp (done)
-make flowchart and fix costmap
-make flowchart and fix dwa
-make flowchart and import global planner
-make costmap jumper 
-make path interceptor 
-make main sistem
-fix BAB2
-do data local plan
-compare icp and transition layer

1. Gambar yang seluruhnya tidak direferensi — perlu diperbaiki (17 environment, 25 label)
bab/Metodologi/bahan_peralatan.tex (figure sensor, line 20 — tidak punya label induk sama sekali):

fig:ydlidar (line 26)
fig:cmps14 (line 33)
bab/Metodologi/metode_pengujian.tex (line 27):

fig:sim_all (line 52, induk), fig:sim_ra (33), fig:sim_ra_rough (40), fig:sim_rc2 (49)
bab/Metodologi/pengolahan_map.tex:

fig:combined_map (line 71)
fig:transition_map_all (line 104, induk), fig:transition_map (94), fig:transition_map_overlay (101)
bab/Metodologi/sistem_navigasi.tex (9 figure alur):

fig:arsitektur_navigasi (line 6)
fig:main_navigation_flow (line 49)
fig:icp_flow (line 60)
fig:costmap_layers (line 280)
fig:costmap_rviz (line 443, induk), fig:static_layer_rviz (432), fig:inflation_layer_rviz (440)
fig:region_switcher_flow (line 555)
fig:global_planner_flow (line 673)
fig:path_router_flow (line 838)
fig:dwa_flow (line 906)
bab/Hasil_dan_pembahasan/pengujian_hasil.tex (4 figure):

fig:icp_errors_ra_posy (line 62)
fig:radius_transition (line 69)
fig:path_all_ra (line 127)
fig:path_all_rc (line 260)
2. Label sub-figure yang wajar tidak dicantum (induknya sudah direferensi)
fig:gambar1, fig:gambar2, fig:gambar3 di pengolahan_map.tex (line 45/52/59) — induk fig:tiga_gambar sudah direferensi (line 37). Ini normal; tidak perlu diubah.
3. Label mati / terkomentari (bukan masalah)
fig:arena_with_dimension di bahan_peralatan.tex (line 82) — seluruh blok figure dinonaktifkan dengan %, jadi tidak menghasilkan output.
Yang perlu Anda tindak lanjuti adalah kategori #1 (17 figure environment, 25 label), terutama 9 diagram alur di sistem_navigasi.tex dan grup gambar sim_all/transition_map_all/combined_map yang sama sekali belum disebut di teks (mis. tambahkan "Gambar~\ref{...}" di paragraf penjelasnya).

Catatan: analisis ini berdasarkan pencocokan label eksak di seluruh .tex proyek utama. Jika Anda ingin, saya bisa menyarankan di mana menambahkan \ref{...} untuk masing-masing gambar tersebut (perlu beralih ke mode edit).