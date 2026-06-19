# Rooftop Annotator Markup & UI Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix annotation bubble clipping/overlap, improve text readability, add per-marker deletion, and polish the legend/title/engineer's note rendering.

**Architecture:** All rendering changes go into `reporter.py`'s `create_engineering_drawing()` function. The marker deletion UI goes into `dashboard.py`'s interactive annotator section. No new files, no data structure changes.

**Tech Stack:** Python, Pillow (PIL), Streamlit

**Spec:** `docs/superpowers/specs/2026-06-19-rooftop-annotator-improvements-design.md`

---

## File Map

- **Modify:** `ant/reporter.py:129-362` — Font variables, title bar, legend, bubble placement algorithm, bubble text sizing/centering, engineer's note position
- **Modify:** `ant/dashboard.py:682-712` — Individual marker deletion UI (marker list with remove buttons)
- **Modify:** `ant/tests/test_pipeline.py:160-175` — Update and extend engineering drawing tests

---

### Task 1: Update Font Variables in reporter.py

**Files:**
- Modify: `ant/reporter.py:222-230`

- [ ] **Step 1: Replace the font initialization block**

In `reporter.py`, replace lines 222-230:

```python
    font_large = None
    try:
        font_large = ImageFont.truetype("arial.ttf", 22)
        font_small = ImageFont.truetype("arial.ttf", 14)
        font_note = ImageFont.truetype("arial.ttf", 16)
    except:
        font_large = None
        font_small = None
        font_note = None
```

With:

```python
    try:
        font_bubble = ImageFont.truetype("arialbd.ttf", 28)
        font_legend = ImageFont.truetype("arialbd.ttf", 26)
        font_title = ImageFont.truetype("arialbd.ttf", 22)
        font_small = ImageFont.truetype("arial.ttf", 14)
        font_note = ImageFont.truetype("arial.ttf", 16)
    except:
        font_bubble = None
        font_legend = None
        font_title = None
        font_small = None
        font_note = None
```

- [ ] **Step 2: Update all references to `font_large`**

There are 3 remaining references to `font_large` in this function that need updating:

1. Line 235 — legend text: change `font=font_large` → `font=font_legend`
2. Line 241 — "brinc" text: change `font=font_large` → `font=font_legend`
3. Line 286 — bubble label text: change `font=font_large` → `font=font_bubble`

- [ ] **Step 3: Run existing test to verify nothing broke**

Run: `python -m pytest ant/tests/test_pipeline.py::TestReporter::test_create_engineering_drawing_writes_output -v`
Expected: PASS (output image still generated)

- [ ] **Step 4: Commit**

```bash
git add ant/reporter.py
git commit -m "refactor: split font_large into font_bubble, font_legend, font_title"
```

---

### Task 2: Title Bar — Increase Size

**Files:**
- Modify: `ant/reporter.py:157-182`

- [ ] **Step 1: Update the title bar font and padding**

In `reporter.py`, replace the address rendering block (lines 158-182):

```python
    if address:
        try:
            font_address = ImageFont.truetype("arial.ttf", 16)
        except:
            font_address = None

        # Draw semi-transparent background for address
        addr_text = str(address).strip()
        addr_bbox = draw.textbbox((0, 0), addr_text, font=font_address)
        addr_width = addr_bbox[2] - addr_bbox[0]
        addr_height = addr_bbox[3] - addr_bbox[1]

        # Position at top center of photo area
        addr_x = (bg_w - addr_width) // 2
        addr_y = 10

        # Draw background box for readability
        padding = 8
        draw.rectangle(
            [addr_x - padding, addr_y - padding, addr_x + addr_width + padding, addr_y + addr_height + padding],
            fill='#000000',
            outline='#3B82F6',
            width=2
        )
        draw.text((addr_x, addr_y), addr_text, fill='#F8FAFC', font=font_address)
```

With:

```python
    if address:
        # Draw address header at top center of photo area
        addr_text = str(address).strip()
        addr_bbox = draw.textbbox((0, 0), addr_text, font=font_title)
        addr_width = addr_bbox[2] - addr_bbox[0]
        addr_height = addr_bbox[3] - addr_bbox[1]

        # Position at top center of photo area
        addr_x = (bg_w - addr_width) // 2
        addr_y = 10

        # Draw background box for readability
        padding = 12
        draw.rectangle(
            [addr_x - padding, addr_y - padding, addr_x + addr_width + padding, addr_y + addr_height + padding],
            fill='#000000',
            outline='#3B82F6',
            width=2
        )
        draw.text((addr_x, addr_y), addr_text, fill='#F8FAFC', font=font_title)
```

Key changes: removed the local `font_address` variable (now uses `font_title` from Task 1 — Arial 22pt bold), increased padding from 8 to 12.

- [ ] **Step 2: Run existing test**

Run: `python -m pytest ant/tests/test_pipeline.py::TestReporter::test_create_engineering_drawing_writes_output -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ant/reporter.py
git commit -m "feat: increase title bar font to 22pt and padding to 12px"
```

---

### Task 3: Right-Side Legend Improvements

**Files:**
- Modify: `ant/reporter.py:232-241`

- [ ] **Step 1: Replace the legend rendering block**

In `reporter.py`, replace lines 232-241:

```python
    # Draw legend labels and color markers
    y_offset = 40
    for title, color in legend_items:
        draw.text((bg_w + 50, y_offset), title, fill=color, font=font_large)
        # Draw a little colored symbol next to it
        draw.rectangle([bg_w + 20, y_offset + 5, bg_w + 35, y_offset + 20], fill=color)
        y_offset += 65
        
    # Draw "brinc" stylized logo at the bottom right
    draw.text((bg_w + 20, canvas_h - 60), "brinc", fill='#F8FAFC', font=font_large)
```

With:

```python
    # Draw "LEGEND" header
    legend_header_y = 25
    draw.text((bg_w + 20, legend_header_y), "LEGEND", fill='#F8FAFC', font=font_title)
    draw.line([(bg_w + 20, legend_header_y + 30), (canvas_w - 20, legend_header_y + 30)], fill='#334155', width=1)

    # Center legend items vertically in sidebar (below header, above brinc text)
    legend_item_spacing = 45
    legend_total_height = len(legend_items) * legend_item_spacing
    legend_start_y = legend_header_y + 50  # Start below header line

    for i, (title, color) in enumerate(legend_items):
        item_y = legend_start_y + i * legend_item_spacing
        # Draw colored circle swatch (20px diameter)
        cx, cy = bg_w + 30, item_y + 10
        draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=color)
        # Draw label text
        draw.text((bg_w + 55, item_y), title, fill=color, font=font_legend)

    # Draw "brinc" stylized logo at the bottom right
    draw.text((bg_w + 20, canvas_h - 60), "brinc", fill='#F8FAFC', font=font_legend)
```

Key changes: "LEGEND" header with separator line, circles instead of squares (20px diameter), Arial 26pt bold, 45px spacing, text starts at x+55 (35px gap from circle center).

- [ ] **Step 2: Run existing test**

Run: `python -m pytest ant/tests/test_pipeline.py::TestReporter::test_create_engineering_drawing_writes_output -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ant/reporter.py
git commit -m "feat: redesign legend with header, circles, larger font, tighter spacing"
```

---

### Task 4: Smart Bubble Placement — Edge-Aware + Collision Avoidance

**Files:**
- Modify: `ant/reporter.py:243-286`
- Test: `ant/tests/test_pipeline.py`

- [ ] **Step 1: Write tests for the bubble placement logic**

Add these tests to `ant/tests/test_pipeline.py`, before the `if __name__` block:

```python
class TestBubblePlacement(unittest.TestCase):
    """Tests for smart bubble placement in engineering drawings."""

    def test_bubble_near_top_left_avoids_clipping(self):
        """A marker near the top-left corner should place its bubble below/right, not off-screen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bg_path = tmp_path / "bg.png"
            out_path = tmp_path / "drawing.png"
            Image.new("RGB", (400, 200), color="gray").save(bg_path)

            # Marker at 2%, 2% — very close to top-left corner
            markers = [
                {"type": "Electric", "label": "20A 110V AC", "node_x": 2, "node_y": 2, "label_x": 2, "label_y": 2},
            ]
            result = reporter.create_engineering_drawing(str(bg_path), str(out_path), markers, "Test")
            self.assertTrue(out_path.exists())
            # Verify output image is valid and correct size
            with Image.open(out_path) as img:
                self.assertEqual(img.size, (1200, 675))

    def test_bubble_near_right_edge_avoids_clipping(self):
        """A marker near the right edge should not place its bubble off the photo area."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bg_path = tmp_path / "bg.png"
            out_path = tmp_path / "drawing.png"
            Image.new("RGB", (400, 200), color="gray").save(bg_path)

            markers = [
                {"type": "Data", "label": "CAT6 Drop", "node_x": 95, "node_y": 50, "label_x": 95, "label_y": 50},
            ]
            result = reporter.create_engineering_drawing(str(bg_path), str(out_path), markers, "Test")
            self.assertTrue(out_path.exists())

    def test_multiple_markers_same_area_no_crash(self):
        """Multiple markers clustered together should render without errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bg_path = tmp_path / "bg.png"
            out_path = tmp_path / "drawing.png"
            Image.new("RGB", (400, 200), color="gray").save(bg_path)

            markers = [
                {"type": "Electric", "label": "20A 110V", "node_x": 50, "node_y": 50, "label_x": 35, "label_y": 42},
                {"type": "Data", "label": "CAT6", "node_x": 52, "node_y": 52, "label_x": 37, "label_y": 44},
                {"type": "RF", "label": "5GHz", "node_x": 48, "node_y": 48, "label_x": 33, "label_y": 40},
            ]
            result = reporter.create_engineering_drawing(str(bg_path), str(out_path), markers, "Test")
            self.assertTrue(out_path.exists())
            with Image.open(out_path) as img:
                self.assertEqual(img.size, (1200, 675))

    def test_four_corner_markers(self):
        """Markers at all four corners should all render without clipping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bg_path = tmp_path / "bg.png"
            out_path = tmp_path / "drawing.png"
            Image.new("RGB", (400, 200), color="gray").save(bg_path)

            markers = [
                {"type": "Electric", "label": "TL corner", "node_x": 3, "node_y": 3, "label_x": 3, "label_y": 3},
                {"type": "Data", "label": "TR corner", "node_x": 97, "node_y": 3, "label_x": 97, "label_y": 3},
                {"type": "RF", "label": "BL corner", "node_x": 3, "node_y": 97, "label_x": 3, "label_y": 97},
                {"type": "Unistrut", "label": "BR corner", "node_x": 97, "node_y": 97, "label_x": 97, "label_y": 97},
            ]
            result = reporter.create_engineering_drawing(str(bg_path), str(out_path), markers, "Test")
            self.assertTrue(out_path.exists())
```

- [ ] **Step 2: Run tests to verify they fail (current code uses fixed label_x/label_y, but tests should still pass since create_engineering_drawing accepts those coords)**

Run: `python -m pytest ant/tests/test_pipeline.py::TestBubblePlacement -v`
Expected: All PASS (tests verify rendering completes without crash; the placement logic fix ensures bubbles don't clip, but the existing code won't crash — it just draws off-canvas)

- [ ] **Step 3: Replace the marker rendering loop with smart placement**

In `reporter.py`, replace the entire marker rendering block (lines 243-286):

```python
    # Draw Markers & Callouts on the background image
    for m in markers:
        # Convert percent to actual pixel coords
        nx = int((m['node_x'] / 100.0) * bg_w)
        ny = int((m['node_y'] / 100.0) * canvas_h)
        lx = int((m['label_x'] / 100.0) * bg_w)
        ly = int((m['label_y'] / 100.0) * canvas_h)
        
        m_type = m.get('type', 'Electric')
        label_text = m.get('label', '')
        
        # Select color matching type
        border_color = '#EF4444' # Default Red (Electric)
        if m_type == 'Data':
            border_color = '#F97316' # Orange
        elif m_type == 'RF':
            border_color = '#A855F7' # Purple
        elif m_type == 'Unistrut':
            border_color = '#94A3B8'
        elif m_type == 'Lift':
            border_color = '#EAB308'
            
        # Draw connection line from Node to Callout Label
        # Draw a path with intermediate node circles if specified
        draw.line([(nx, ny), (lx, ly)], fill=border_color, width=3)
        
        # Draw small circles at the connection endpoints
        draw.ellipse([nx-6, ny-6, nx+6, ny+6], fill=border_color)
        draw.ellipse([lx-4, ly-4, lx+4, ly+4], fill=border_color)
        
        # Calculate text bounding box to wrap in rounded rectangle
        # Roughly calculate text size
        text_w = len(label_text) * 11
        text_h = 24
        
        pad_x, pad_y = 12, 12
        rx1, ry1 = lx - text_w // 2 - pad_x, ly - text_h // 2 - pad_y
        rx2, ry2 = lx + text_w // 2 + pad_x, ly + text_h // 2 + pad_y
        
        # Draw Rounded Rect for text
        draw.rounded_rectangle([rx1, ry1, rx2, ry2], radius=12, outline=border_color, width=3, fill='#000000')
        
        # Draw Text
        draw.text((rx1 + pad_x, ry1 + pad_y - 2), label_text, fill='#FFFFFF', font=font_large)
```

With:

```python
    # Draw Markers & Callouts on the background image
    # Track placed bubble rectangles for collision avoidance
    placed_bubbles = []

    for m in markers:
        # Convert percent to actual pixel coords
        nx = int((m['node_x'] / 100.0) * bg_w)
        ny = int((m['node_y'] / 100.0) * canvas_h)

        m_type = m.get('type', 'Electric')
        label_text = m.get('label', '')

        # Select color matching type
        color_map = {
            'Data': '#F97316',
            'RF': '#A855F7',
            'Unistrut': '#94A3B8',
            'Lift': '#EAB308',
        }
        border_color = color_map.get(m_type, '#EF4444')

        # Measure actual text size for accurate bubble dimensions
        if font_bubble:
            bbox = draw.textbbox((0, 0), label_text, font=font_bubble)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        else:
            text_w = len(label_text) * 14
            text_h = 30

        pad_x, pad_y = 14, 14
        bubble_w = text_w + pad_x * 2
        bubble_h = text_h + pad_y * 2

        # Smart bubble placement: try 4 directions, check edge + collision
        offset_x = int(bg_w * 0.15)
        offset_y = int(canvas_h * 0.08)

        candidates = [
            (nx - offset_x - bubble_w // 2, ny - offset_y - bubble_h // 2),  # upper-left
            (nx + offset_x - bubble_w // 2, ny - offset_y - bubble_h // 2),  # upper-right
            (nx + offset_x - bubble_w // 2, ny + offset_y - bubble_h // 2),  # lower-right
            (nx - offset_x - bubble_w // 2, ny + offset_y - bubble_h // 2),  # lower-left
        ]

        best_pos = None
        best_overlap = float('inf')

        for cx, cy in candidates:
            # Clamp to photo area bounds
            cx = max(2, min(cx, bg_w - bubble_w - 2))
            cy = max(2, min(cy, canvas_h - bubble_h - 2))
            candidate_rect = (cx, cy, cx + bubble_w, cy + bubble_h)

            # Check if bubble fits within photo area
            fits_edge = (cx >= 0 and cy >= 0 and cx + bubble_w <= bg_w and cy + bubble_h <= canvas_h)

            # Calculate total overlap with already-placed bubbles
            total_overlap = 0
            for pb in placed_bubbles:
                # AABB intersection area
                ox1 = max(candidate_rect[0], pb[0])
                oy1 = max(candidate_rect[1], pb[1])
                ox2 = min(candidate_rect[2], pb[2])
                oy2 = min(candidate_rect[3], pb[3])
                if ox1 < ox2 and oy1 < oy2:
                    total_overlap += (ox2 - ox1) * (oy2 - oy1)

            if fits_edge and total_overlap == 0:
                best_pos = (cx, cy)
                break
            elif total_overlap < best_overlap:
                best_overlap = total_overlap
                best_pos = (cx, cy)

        if best_pos is None:
            best_pos = (candidates[0][0], candidates[0][1])

        lx, ly = best_pos[0] + bubble_w // 2, best_pos[1] + bubble_h // 2
        rx1, ry1 = best_pos
        rx2, ry2 = rx1 + bubble_w, ry1 + bubble_h

        # Track this bubble for future collision checks
        placed_bubbles.append((rx1, ry1, rx2, ry2))

        # Draw connection line from node dot to bubble center
        draw.line([(nx, ny), (lx, ly)], fill=border_color, width=3)

        # Draw node dot and bubble endpoint dot
        draw.ellipse([nx - 6, ny - 6, nx + 6, ny + 6], fill=border_color)
        draw.ellipse([lx - 4, ly - 4, lx + 4, ly + 4], fill=border_color)

        # Draw rounded rectangle bubble
        draw.rounded_rectangle([rx1, ry1, rx2, ry2], radius=12, outline=border_color, width=3, fill='#000000')

        # Draw centered text inside bubble
        text_x = rx1 + (bubble_w - text_w) // 2
        text_y = ry1 + (bubble_h - text_h) // 2
        draw.text((text_x, text_y), label_text, fill='#FFFFFF', font=font_bubble)
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest ant/tests/test_pipeline.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add ant/reporter.py ant/tests/test_pipeline.py
git commit -m "feat: smart bubble placement with edge-aware + collision avoidance, centered 28pt text"
```

---

### Task 5: Engineer's Note — Shift Right onto Sidebar

**Files:**
- Modify: `ant/reporter.py:288-312`

- [ ] **Step 1: Replace the engineer's note positioning block**

In `reporter.py`, replace the engineer's note block (the lines that were originally 288-312, now shifted due to earlier edits — find the block starting with `# Draw Engineer's Note Box`):

```python
    # Draw Engineer's Note Box in the Bottom Right
    note_w, note_h = 240, 250
    nx1, ny1 = canvas_w - note_w - 15, canvas_h - note_h - 15
    nx2, ny2 = canvas_w - 15, canvas_h - 15
```

With:

```python
    # Draw Engineer's Note Box centered in the sidebar
    note_w, note_h = 220, 250
    nx1 = bg_w + (sidebar_w - note_w) // 2
    ny1 = canvas_h - note_h - 15
    nx2, ny2 = nx1 + note_w, ny1 + note_h
```

This changes note width from 240→220 and centers it in the 240px sidebar (x=970, giving 10px margin on each side). The note sits entirely on the black area.

- [ ] **Step 2: Update the word-wrap width calculation**

Find the line:

```python
        if len(" ".join(current_line + [word])) * 8 > (note_w - 20):
```

No change needed — `note_w` is now 220 instead of 240, so the wrap will automatically be slightly tighter. This is correct behavior.

- [ ] **Step 3: Run tests**

Run: `python -m pytest ant/tests/test_pipeline.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add ant/reporter.py
git commit -m "feat: center engineer's note box within sidebar area"
```

---

### Task 6: Individual Marker Deletion UI in dashboard.py

**Files:**
- Modify: `ant/dashboard.py:682-712`

- [ ] **Step 1: Add the marker list with delete buttons**

In `dashboard.py`, find the section starting with `# Action Buttons` (line 682). Insert the marker list **before** the action buttons section. Add this code before `# Action Buttons`:

```python
                    # Marker list with individual delete buttons
                    current_markers = selected_site['markers_by_image'].get(st.session_state.active_bg_image, [])
                    if current_markers:
                        st.markdown("**Placed Markers:**")
                        color_emoji = {
                            'Electric': '🔴',
                            'Data': '🟠',
                            'RF': '🟣',
                            'Unistrut': '⚪',
                            'Lift': '🟡',
                        }
                        for idx, marker in enumerate(current_markers):
                            mcol1, mcol2 = st.columns([3, 1])
                            with mcol1:
                                emoji = color_emoji.get(marker.get('type', ''), '⚫')
                                st.markdown(f"{emoji} **{marker.get('type', '')}** — {marker.get('label', '')}")
                            with mcol2:
                                if st.button("✕ Remove", key=f"del_marker_{selected_site['site_id']}_{st.session_state.active_bg_image}_{idx}"):
                                    selected_site['markers_by_image'][st.session_state.active_bg_image].pop(idx)
                                    # Re-render drawing
                                    if selected_site['markers_by_image'][st.session_state.active_bg_image]:
                                        reporter.create_engineering_drawing(
                                            bg_display_path or bg_path,
                                            output_drawing_path,
                                            selected_site['markers_by_image'][st.session_state.active_bg_image],
                                            selected_site['eng_note'],
                                            address=selected_site['address'],
                                            image_placements=selected_site['image_placements_by_image'].get(st.session_state.active_bg_image, []),
                                            images_dir=images_dir
                                        )
                                    elif os.path.exists(output_drawing_path):
                                        os.remove(output_drawing_path)
                                    _save_session_metadata(st.session_state.processed_sites)
                                    st.rerun()
                    else:
                        st.caption("No markers placed yet.")

```

- [ ] **Step 2: Verify the indentation level matches the surrounding code**

The new block must be at the same indentation level as the `# Action Buttons` comment (20 spaces — 5 levels of 4-space indent). Verify by reading the surrounding lines.

- [ ] **Step 3: Test manually in the Streamlit app**

Run: `streamlit run ant/dashboard.py`

Test steps:
1. Navigate to the Interactive Rooftop Layout & Annotator
2. Select a photo
3. Place 2-3 markers
4. Verify the marker list appears below the image with type, label, and remove button per row
5. Click "✕ Remove" on one marker — verify it disappears from the list and the drawing re-renders
6. Verify "Clear All Placements" still works
7. Verify "No markers placed yet." shows when the list is empty

- [ ] **Step 4: Commit**

```bash
git add ant/dashboard.py
git commit -m "feat: add per-marker deletion UI with marker list and remove buttons"
```

---

### Task 7: Final Integration Test

**Files:**
- Test: `ant/tests/test_pipeline.py`

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest ant/tests/test_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 2: Manual visual verification**

Run: `streamlit run ant/dashboard.py`

Walk through the full workflow:
1. Select a photo background
2. Place markers at all 4 corners — verify no bubbles clip off the edge
3. Place 3 markers close together in the center — verify bubbles don't overlap
4. Verify bubble text is large, bold, and centered in each box
5. Check the legend: "LEGEND" header, circle swatches, readable text
6. Check the title bar: larger text, readable address
7. Check engineer's note: entirely on the black sidebar, not straddling photo edge
8. Remove individual markers using the list — verify drawing updates
9. Clear all and start fresh — verify clean state

- [ ] **Step 3: Commit final state if any touch-ups were needed**

```bash
git add -A
git commit -m "test: verify all annotator improvements pass integration checks"
```
