# Graph Report - .  (2026-06-20)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 240 nodes · 312 edges · 23 communities (14 shown, 9 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e045cb03`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]

## God Nodes (most connected - your core abstractions)
1. `GoogleDriveManager` - 17 edges
2. `extract_city_from_address()` - 16 edges
3. `search_gmail_for_contacts()` - 11 edges
4. `TestExtractCityFromAddress` - 11 edges
5. `get_credentials()` - 10 edges
6. `_validate_domain()` - 9 edges
7. `TestValidateDomain` - 8 edges
8. `process_and_organize_images()` - 7 edges
9. `TestGetCredentials` - 7 edges
10. `_get_gmail_service()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Station Overlay UI Component` --conceptually_related_to--> `streamlit-image-coordinates`  [INFERRED]
  images/station_overlay.png → requirements.txt
- `TestGetCredentials` --uses--> `GoogleDriveManager`  [INFERRED]
  tests/test_google_oauth.py → google_drive.py
- `TestValidateDomain` --uses--> `GoogleDriveManager`  [INFERRED]
  tests/test_google_oauth.py → google_drive.py
- `_lookup_contacts_from_gmail()` --calls--> `search_gmail_for_contacts()`  [EXTRACTED]
  dashboard.py → gmail_lookup.py
- `TestDriveManagerOAuth` --uses--> `GoogleDriveManager`  [INFERRED]
  tests/test_google_oauth.py → google_drive.py

## Import Cycles
- None detected.

## Communities (23 total, 9 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (36): cluster_images(), _derive_department_folder_name(), _exifread_ratio_to_float(), extract_city_from_address(), extract_exif_gps(), _extract_gps_with_exifread(), get_decimal_from_dms(), _parse_exifread_dms() (+28 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (18): _get_gmail_service(), Build a Gmail API service using the current user's OAuth credentials., GoogleDriveManager, Upload bytes to Google Drive.          Args:             file_bytes: Bytes to, Manages Google Drive operations: auth, file upload/download, folder creation., Download file from Google Drive to local path.          Args:             fil, Initialize with either OAuth Credentials or a service account JSON string., List files in folder.          Args:             folder_id: Google Drive fold (+10 more)

### Community 2 - "Community 2"
Cohesion: 0.10
Nodes (23): _delete_token_file(), get_auth_url(), _get_client_config(), get_credentials(), _get_redirect_uri(), handle_callback(), is_authenticated(), _load_token_from_disk() (+15 more)

### Community 3 - "Community 3"
Cohesion: 0.10
Nodes (17): _detect_agency_from_gps(), _extract_town_state_from_address(), _get_displayable_image_path(), _lookup_contacts_from_gmail(), _on_files_changed(), Resolve relative paths against the dashboard file location., Infer town and state from a reverse-geocoded address string., Save metadata to a JSON file inside each site's folder. (+9 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (20): add_styled_table(), _coords_close(), create_engineering_drawing(), draw_styled_map(), _format_short_address(), generate_word_report(), _merge_way_segments(), query_airspace_class() (+12 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (17): _extract_body_contacts(), _extract_external_contacts(), _get_calendar_service(), _get_plain_text_body(), _is_blocked_email(), _is_non_person_name(), _name_from_email(), Gmail API wrapper for searching threads and extracting contact info.  Uses OAu (+9 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (7): PipelineTests, Tests for smart bubble placement in engineering drawings., A marker near the top-left corner should place its bubble below/right, not off-s, A marker near the right edge should not place its bubble off the photo area., Multiple markers clustered together should render without errors., Markers at all four corners should all render without clipping., TestBubblePlacement

### Community 7 - "Community 7"
Cohesion: 0.24
Nodes (9): analyze_image_heuristics(), analyze_image_via_api(), analyze_site(), Iterates through all images in a site and aggregates infrastructure findings., Placeholder for cloud/Vision LLM API integration.     If api_key and api_url are, Simulate computer vision analysis of site images.     Parses filenames and uses, main(), Run the end-to-end processing pipeline from the command line. (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.33
Nodes (4): Check that the email belongs to the allowed domain.      Args:         email:, _validate_domain(), Test that only @brincdrones.com emails are accepted., TestValidateDomain

### Community 9 - "Community 9"
Cohesion: 0.33
Nodes (6): BRINC Logo White, folium, streamlit, streamlit-folium, streamlit-image-coordinates, Station Overlay UI Component

### Community 10 - "Community 10"
Cohesion: 0.33
Nodes (4): Verify site_data has None values when city cannot be extracted., Integration tests for process_and_organize_images() with agency_name., Verify site_data contains city and agency_name fields., TestProcessAndOrganizeImages

### Community 11 - "Community 11"
Cohesion: 0.33
Nodes (4): Test that reporter can access agency_name field., Verify site_data has fields reporter expects., Verify reporter doesn't break if agency_name is None., TestReporterIntegration

### Community 12 - "Community 12"
Cohesion: 0.33
Nodes (4): Test that agency_name is correctly generated from city., Generate proper agency_name format from extracted city., agency_name should be None when city is None., TestAgencyNameGeneration

## Knowledge Gaps
- **11 isolated node(s):** `Critical Rules for Agents`, `Pillow`, `pillow-heif`, `geopy`, `python-docx` (+6 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GoogleDriveManager` connect `Community 1` to `Community 8`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.166) - this node is a cross-community bridge._
- **Why does `get_drive_manager()` connect `Community 3` to `Community 1`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `GoogleDriveManager` (e.g. with `TestDriveManagerOAuth` and `TestGetCredentials`) actually correct?**
  _`GoogleDriveManager` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Simulate computer vision analysis of site images.     Parses filenames and uses`, `Placeholder for cloud/Vision LLM API integration.     If api_key and api_url are`, `Iterates through all images in a site and aggregates infrastructure findings.` to the rest of the system?**
  _106 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.05877551020408163 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.08387096774193549 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.10317460317460317 - nodes in this community are weakly interconnected._