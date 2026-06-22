# Graph Report - ant  (2026-06-22)

## Corpus Check
- 21 files · ~24,715 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 397 nodes · 706 edges · 26 communities (17 shown, 9 thin omitted)
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 122 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `78f07323`
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
- [[_COMMUNITY_Community 23|Community 23]]

## God Nodes (most connected - your core abstractions)
1. `CandidateSite` - 33 edges
2. `SiteIdentity` - 28 edges
3. `SurveyPhoto` - 24 edges
4. `TestCandidateSite` - 22 edges
5. `ElectricalInfo` - 18 edges
6. `GoogleDriveManager` - 17 edges
7. `extract_city_from_address()` - 17 edges
8. `NetworkInfo` - 17 edges
9. `AccessInfo` - 16 edges
10. `StructuralInfo` - 16 edges

## Surprising Connections (you probably didn't know these)
- `Station Overlay UI Component` --conceptually_related_to--> `streamlit-image-coordinates`  [INFERRED]
  images/station_overlay.png → requirements.txt
- `TestGetCredentials` --uses--> `GoogleDriveManager`  [INFERRED]
  tests/test_google_oauth.py → google_drive.py
- `GeoResult` --uses--> `CandidateSite`  [INFERRED]
  processor.py → site_model.py
- `GeoResult` --uses--> `SiteIdentity`  [INFERRED]
  processor.py → site_model.py
- `GeoResult` --uses--> `SurveyPhoto`  [INFERRED]
  processor.py → site_model.py

## Import Cycles
- None detected.

## Communities (26 total, 9 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (39): cluster_images(), _derive_department_folder_name(), _exifread_ratio_to_float(), extract_city_from_address(), extract_exif_gps(), _extract_gps_with_exifread(), GeoResult, get_decimal_from_dms() (+31 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (22): _get_gmail_service(), Build a Gmail API service using the current user's OAuth credentials., GoogleDriveManager, Upload bytes to Google Drive.          Args:             file_bytes: Bytes to, Manages Google Drive operations: auth, file upload/download, folder creation., Download file from Google Drive to local path.          Args:             fil, Initialize with either OAuth Credentials or a service account JSON string., List files in folder.          Args:             folder_id: Google Drive fold (+14 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (23): _delete_token_file(), get_auth_url(), _get_client_config(), get_credentials(), _get_redirect_uri(), handle_callback(), is_authenticated(), _load_token_from_disk() (+15 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (35): AccessInfo, DockLocation, ElectricalInfo, export_sites_csv(), export_sites_json(), FlightOps, InstallInfo, NetworkInfo (+27 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (32): add_styled_table(), _coords_close(), create_engineering_drawing(), draw_styled_map(), _format_short_address(), generate_candidate_site_report(), generate_word_report(), _load_font() (+24 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (38): _detect_agency_from_gps(), _extract_town_state_from_address(), _get_displayable_image_path(), _get_last_push_timestamp(), _lookup_contacts_from_gmail(), _on_files_changed(), Resolve relative paths against the dashboard file location., Infer town and state from a reverse-geocoded address string. (+30 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (7): PipelineTests, Tests for smart bubble placement in engineering drawings., A marker near the top-left corner should place its bubble below/right, not off-s, A marker near the right edge should not place its bubble off the photo area., Multiple markers clustered together should render without errors., Markers at all four corners should all render without clipping., TestBubblePlacement

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (17): analyze_image_heuristics(), analyze_image_via_api(), analyze_site(), enrich_gis(), estimate_building_height_gemini(), Iterates through all images in a site and aggregates infrastructure findings., Simulate computer vision analysis of site images.     Parses filenames and uses, Use Gemini Flash free tier to estimate building height from a photo.     Returns (+9 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (17): cluster_images_dbscan(), cluster_to_candidate_sites(), Cluster images by GPS proximity using DBSCAN.      Args:         images_meta: li, Convert cluster output into a list of CandidateSite objects.      Args:, CandidateSite, categorize_photo_by_filename(), Top-level model representing one candidate DFR deployment site., Convert a legacy processor.py site dict to a CandidateSite. (+9 more)

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

### Community 23 - "Community 23"
Cohesion: 0.29
Nodes (5): Architecture, Commands, Graphify, Project Overview, Secrets & Configuration

## Knowledge Gaps
- **16 isolated node(s):** `CRITICAL RULES`, `Project Overview`, `Commands`, `Architecture`, `Secrets & Configuration` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CandidateSite` connect `Community 8` to `Community 0`, `Community 3`, `Community 4`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Why does `extract_city_from_address()` connect `Community 0` to `Community 8`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `GoogleDriveManager` connect `Community 1` to `Community 2`, `Community 5`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `CandidateSite` (e.g. with `GeoResult` and `TestDBSCANClustering`) actually correct?**
  _`CandidateSite` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `SiteIdentity` (e.g. with `GeoResult` and `TestEnrichGISElevation`) actually correct?**
  _`SiteIdentity` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `SurveyPhoto` (e.g. with `GeoResult` and `TestDynamicReport`) actually correct?**
  _`SurveyPhoto` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `TestCandidateSite` (e.g. with `AccessInfo` and `CandidateSite`) actually correct?**
  _`TestCandidateSite` has 12 INFERRED edges - model-reasoned connections that need verification._