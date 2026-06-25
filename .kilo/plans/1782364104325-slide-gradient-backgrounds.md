# Plan: Inject Result Images into PPTX + Split Results Slides

## Summary
Add actual thesis result images to 4 existing slides and create 2 new dedicated result slides (ICP + Path Planning). All images already have PNG versions in `gambar/`.

---

## Task 1: Add images to existing slides

### 1a. Slide 9 — Map Processing (replace text columns with images)
- **File**: `slide_map_processing` function
- **Remove**: 3-column text cards (lines showing "Lingkungan 3D", "Pembagian Region", "Combined & Transition Map")
- **Add images**:
  - Top area (full width): `combined_map.png` — shows all three regions combined
  - Below (split left 55% / right 45%):
    - Left: `transition_map.png`
    - Right: `transition_map_overlay.png`  
- Scale images to fit ~5.2" of vertical space total
- Keep title "PENGOLAHAN DATA MAP" and divider

### 1b. Slide 11 — ICP & Region Switcher (add arena context)
- **File**: `slide_icp` function
- **Add**: `sim_RA.png` below the Region Switcher section (right side, below region A/B/C cards)
- Show what the actual arena looks like that ICP runs on
- Scale to fit ~1.5–2.0" height in remaining space
- Keep all existing ICP pipeline cards and region switcher cards

### 1c. Slide 12 — Path Planning (add CSF visual)
- **File**: `slide_path_planning` function
- **Add**: `path_all_RA.png` below the CSF cards on the right side
- Shows all 4 CSF paths (10, 20, 50, 100) overlaid — visual proof of CSF impact
- Scale to fit ~2.0–2.5" height below existing CSF cards, or replace the key_finding callout box
- Consider removing the key_finding box (text is redundant when image shows it visually)

### 1d. Slide 14 — Arena Pengujian (replace text cards with 2×2 screenshot gallery)
- **File**: `slide_arena` function
- **Remove**: 4 arena description cards (lines showing "Region A", "Region B", "Region C", "Rough Floor")
- **Add**: 2×2 image grid:
  - Top-left: `sim_RA.png` with label "Region A"
  - Top-right: `sim_RA_rough.png` with label "Region A — Rough Floor"
  - Bottom-left: `sim_RB.png` with label "Region B"
  - Bottom-right: `sim_RC2.png` with label "Region C"
- Place small `PRIMARY`-colored labels above/below each image
- Keep title, divider, and platform info text (already fixed contrast in A4)
- Keep slide number

---

## Task 2: Create two new result slides (split current slide 15)

### 2a. NEW Slide 15 — Hasil Pengujian: ICP
- **File**: New function `slide_results_icp(slide)`
- **Layout**: Two images side by side or stacked:
  - Left/top: `icp_errors_RA.png` — ICP error plot for Region A (normal floor)
  - Right/bottom: `icp_errors_RA_rough.png` — ICP error plot for Region A (rough floor)
- **Text annotations**: Small labels below each image explaining what they show
- **Title**: "HASIL PENGUJIAN: ICP LOCALIZATION"
- **Gradient**: `GRAD_RESULTS_S → GRAD_RESULTS_E` (warm)
- **Slide number**: 15

### 2b. NEW Slide 16 — Hasil Pengujian: Path Planning
- **File**: New function `slide_results_path(slide)`
- **Layout**: 
  - Main image (center/top): `path_all_RA.png` — all CSF paths overlaid
  - Key finding text below (from current slide 15 CSF key finding):
    "CSF 100 menghasilkan path terpendek dan paling lurus. CSF 10 mengambil jalur tengah yang lebih konservatif namun lebih panjang."
- **Title**: "HASIL PENGUJIAN: PATH PLANNING"
- **Gradient**: `GRAD_RESULTS_S → GRAD_RESULTS_E` (warm)
- **Slide number**: 16

---

## Task 3: Renumber slides and update main()

### 3a. Rename + renumber old slides 15–19 → 17–20
- Old `slide_results_navigation` (was slide 15→16) → now slide 17
- Old `slide_conclusion` (was slide 16→17) → now slide 18
- Old `slide_future_work` (was slide 17→18) → now slide 19
- `slide_thanks` (was slide 18→19) → now slide 20

### 3b. Update `add_slide_number` calls
- `slide_results_navigation`: `16` → `17`
- `slide_conclusion`: `17` → `18`
- `slide_future_work`: `18` → `19`

### 3c. Update docstrings
- `slide_results_navigation`: "Slide 16" → "Slide 17"
- `slide_conclusion`: "Slide 17" → "Slide 18"
- `slide_future_work`: "Slide 18" → "Slide 19"

### 3d. Update `main()` function
- Insert `slide_results_icp(prs)` and `slide_results_path(prs)` after `slide_arena(prs)`
- Reorder: `slide_arena` → `slide_results_icp` → `slide_results_path` → `slide_results_navigation` → ...

---

## Task 4: Validation
1. Run `python generate_presentation.py`
2. Confirm 20 total slides
3. Open PPTX and verify:
   - Slide 9 shows map images (combined_map + transition)
   - Slide 11 shows sim_RA arena image below region cards
   - Slide 12 shows path_all_RA below CSF cards
   - Slide 14 shows 2×2 arena screenshot gallery
   - Slide 15 (new) shows 2 ICP error graphs
   - Slide 16 (new) shows path_all_RA + key finding
   - Slides 17–20 have correct numbers and content unchanged

---

## Image Reference Table (all PNG — no conversion needed)
| Image | Slides used |
|-------|------------|
| `combined_map.png` | 9 |
| `transition_map.png` | 9 |
| `transition_map_overlay.png` | 9 |
| `sim_RA.png` | 11, 14 |
| `sim_RA_rough.png` | 14 |
| `sim_RB.png` | 14 |
| `sim_RC2.png` | 14 |
| `path_all_RA.png` | 12, 16 |
| `icp_errors_RA.png` | 15 |
| `icp_errors_RA_rough.png` | 15 |
