# Rooftop Annotator — Markup & UI Improvements

**Date:** 2026-06-19
**Files:** `reporter.py`, `dashboard.py`

---

## 1. Smart Bubble Placement (Edge-Aware + Collision Avoidance)

**Problem:** Label bubbles are always placed upper-left of the marker dot with only minimal clamping (`max(x - 15, 5)`). When markers are near edges, bubbles clip off the image. When markers are clustered, bubbles overlap each other.

**Solution:** Replace the fixed offset with a 4-candidate position system:

1. Calculate the actual bubble dimensions using `font.getbbox(label_text)` instead of `len(text) * 11`.
2. Define 4 candidate label positions relative to the marker dot:
   - **1st priority:** Upper-left (current default direction)
   - **2nd priority:** Upper-right
   - **3rd priority:** Lower-right
   - **4th priority:** Lower-left
3. For each candidate, perform two checks:
   - **Edge check:** Does the bubble rectangle fit entirely within the photo area (x: 0–960px, y: 0–675px)?
   - **Collision check:** Does the bubble rectangle overlap any previously placed bubble? Use axis-aligned bounding box (AABB) intersection test against a running list of placed bubble rectangles.
4. Use the first candidate that passes both checks.
5. **Fallback:** If no candidate passes both checks, use the position with the least total overlap area (best-effort).

**Offset distances:** Use ~15% of image width horizontally and ~8% of image height vertically as the offset from the marker dot to the bubble center, matching the current offset scale.

**Collision tracking:** Maintain a list of placed bubble rectangles `[(rx1, ry1, rx2, ry2), ...]` that grows as each marker is rendered. Each new marker checks against this list.

---

## 2. Bubble Text — Larger, Centered, Properly Sized

**Problem:** Text uses Arial 22pt with width estimated as `len(text) * 11`, which is inaccurate. Text is drawn left-aligned at `rx1 + pad_x` instead of centered. Result is small, hard-to-read labels.

**Changes:**
- **Font:** Arial 22pt → **Arial 28pt bold**
- **Width measurement:** Replace `len(label_text) * 11` with `font.getbbox(label_text)` for exact pixel dimensions
- **Text centering:** Calculate centered x position: `rx1 + (box_width - text_width) // 2`
- **Vertical centering:** Calculate centered y position: `ry1 + (box_height - text_height) // 2`
- **Padding:** Increase from 12px to 14px to accommodate larger text

---

## 3. Individual Marker Deletion (dashboard.py)

**Problem:** Only a "Clear All Placements" button exists. Users cannot remove a single misplaced marker without clearing everything.

**Solution:** Add a marker list UI below the placement controls:

- Display all markers for the current active image as a list
- Each row shows: **colored emoji/indicator matching node type** + **type name** + **label text** + **"✕ Remove" button**
- Clicking "Remove" on a row:
  1. Removes the marker at that index from `markers_by_image[active_image]`
  2. Re-renders the drawing via `reporter.create_engineering_drawing()`
  3. Saves session metadata via `_save_session_metadata()`
  4. Calls `st.rerun()`
- The existing "Clear All" button remains for bulk clearing
- Use `st.columns([3, 1])` per row for layout: label in left column, button in right column
- Show a message like "No markers placed yet" when the list is empty

---

## 4. Right-Side Legend Improvements (reporter.py)

**Problem:** Legend has small 15×15px square swatches, large 65px spacing, no header, and the text is hard to read at the rendered canvas size.

**Changes:**
- **Add header:** Draw "LEGEND" text at top of sidebar in white, with a horizontal separator line below
- **Swatch shape:** Squares (15×15) → **Circles** (radius 10px) using `draw.ellipse()`
- **Swatch size:** 15×15px → 20×20px diameter
- **Font:** Arial 22pt → **Arial 26pt bold**
- **Spacing:** 65px between items → **45px** (tighter, less wasted space)
- **Vertical position:** Center the legend block vertically in the sidebar (calculate total legend height, offset from center)
- **Swatch-to-text gap:** Increase from 30px to 35px for better alignment
- **"brinc" text at bottom:** Keep as-is, already reads well

---

## 5. Engineer's Note — Shift Right onto Black Sidebar

**Problem:** Note box positioned at `canvas_w - note_w - 15` = x:945, which starts 15px *left* of the sidebar edge (960px), causing the box to straddle the photo and sidebar areas.

**Changes:**
- **Note width:** 240px → **220px** (adds breathing room within the 240px sidebar)
- **Before:** `nx1 = canvas_w - note_w - 15` (x = 945, straddles photo/sidebar)
- **After:** `nx1 = bg_w + (sidebar_w - note_w) // 2` → x = 960 + (240 - 220) // 2 = **970** (10px inset from sidebar edge)
- This places the note entirely within the black sidebar area with 10px margin on each side
- Keep the note's vertical position (bottom of sidebar) and all other properties unchanged

---

## 6. Title Bar — Moderate Size Increase

**Problem:** Address text at top uses Arial 16pt with 8px padding — too small and hard to read on the 1200×675 canvas.

**Changes:**
- **Font:** Arial 16pt → **Arial 22pt bold**
- **Padding:** 8px → **12px**
- **Border width:** 2px → **2px** (unchanged — already visible enough)
- All other properties (centered positioning, black fill, blue border, white text) remain the same

---

## Implementation Note: Font Variables

The current code uses a single `font_large` (Arial 22pt) for both bubble text and legend text. Since sections 2 and 4 specify different sizes, create separate font variables:
- `font_bubble` — Arial 28pt bold (for callout label text)
- `font_legend` — Arial 26pt bold (for sidebar legend labels)
- `font_title` — Arial 22pt bold (for address title bar)
- Keep existing `font_small` (14pt) and `font_note` (16pt) as-is

---

## Scope & Non-Goals

- Only `reporter.py` and `dashboard.py` are modified
- No changes to data structures (`markers_by_image` dict format stays the same)
- No changes to image processing, GPS extraction, or report generation
- No changes to the "Clear All" button behavior
- No drag-to-reposition for bubbles (out of scope)
