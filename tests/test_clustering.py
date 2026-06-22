import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from processor import cluster_images_dbscan, split_clusters_by_time_gap
from site_model import CandidateSite


class TestDBSCANClustering:
    def test_two_distinct_clusters(self):
        """Photos at two locations ~500m apart should form 2 clusters."""
        images = [
            {"path": "a1.jpg", "lat": 41.862644, "lon": -87.661244, "time": None},
            {"path": "a2.jpg", "lat": 41.862700, "lon": -87.661300, "time": None},
            {"path": "b1.jpg", "lat": 41.867000, "lon": -87.665000, "time": None},
            {"path": "b2.jpg", "lat": 41.867050, "lon": -87.665050, "time": None},
        ]
        clusters = cluster_images_dbscan(images)
        assert len(clusters) == 2
        cluster_sizes = sorted([len(c) for c in clusters])
        assert cluster_sizes == [2, 2]

    def test_single_cluster(self):
        """All photos within 50m should form 1 cluster."""
        images = [
            {"path": "a1.jpg", "lat": 41.862644, "lon": -87.661244, "time": None},
            {"path": "a2.jpg", "lat": 41.862650, "lon": -87.661250, "time": None},
            {"path": "a3.jpg", "lat": 41.862660, "lon": -87.661260, "time": None},
        ]
        clusters = cluster_images_dbscan(images)
        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_single_image(self):
        """One image should still produce one cluster."""
        images = [{"path": "solo.jpg", "lat": 41.862644, "lon": -87.661244, "time": None}]
        clusters = cluster_images_dbscan(images)
        assert len(clusters) == 1

    def test_empty_input(self):
        clusters = cluster_images_dbscan([])
        assert clusters == []

    def test_no_gps_images_excluded(self):
        """Images without GPS should be excluded from clusters."""
        images = [
            {"path": "a.jpg", "lat": 41.862644, "lon": -87.661244, "time": None},
            {"path": "nogps.jpg", "lat": None, "lon": None, "time": None},
        ]
        clusters = cluster_images_dbscan(images)
        total_images = sum(len(c) for c in clusters)
        assert total_images == 1


class TestTimeGapSplitting:
    def test_no_split_when_times_close(self):
        """Photos taken within 10 minutes stay in one cluster."""
        from datetime import datetime
        cluster = [
            [
                {"path": "a.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 0)},
                {"path": "b.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 5)},
                {"path": "c.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 8)},
            ]
        ]
        result = split_clusters_by_time_gap(cluster)
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_split_on_large_gap(self):
        """A 15-minute gap between photos should split the cluster."""
        from datetime import datetime
        cluster = [
            [
                {"path": "a.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 0)},
                {"path": "b.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 3)},
                {"path": "c.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 20)},
                {"path": "d.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 22)},
            ]
        ]
        result = split_clusters_by_time_gap(cluster)
        assert len(result) == 2
        assert [img["path"] for img in result[0]] == ["a.jpg", "b.jpg"]
        assert [img["path"] for img in result[1]] == ["c.jpg", "d.jpg"]

    def test_untimed_images_attached_to_last_group(self):
        """Images without timestamps go with the last temporal group."""
        from datetime import datetime
        cluster = [
            [
                {"path": "a.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 0)},
                {"path": "b.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 20)},
                {"path": "no_time.jpg", "lat": 41.86, "lon": -87.66, "time": None},
            ]
        ]
        result = split_clusters_by_time_gap(cluster)
        assert len(result) == 2
        assert result[0] == [cluster[0][0]]
        # Last group gets the timed image + untimed image
        paths = [img["path"] for img in result[1]]
        assert "b.jpg" in paths
        assert "no_time.jpg" in paths

    def test_all_untimed_no_split(self):
        """A cluster with no timestamps should not be split."""
        cluster = [
            [
                {"path": "a.jpg", "lat": 41.86, "lon": -87.66, "time": None},
                {"path": "b.jpg", "lat": 41.86, "lon": -87.66, "time": None},
            ]
        ]
        result = split_clusters_by_time_gap(cluster)
        assert len(result) == 1
        assert len(result[0]) == 2

    def test_single_image_no_split(self):
        """A single-image cluster should pass through unchanged."""
        from datetime import datetime
        cluster = [
            [{"path": "solo.jpg", "lat": 41.86, "lon": -87.66, "time": datetime(2026, 6, 22, 14, 0)}]
        ]
        result = split_clusters_by_time_gap(cluster)
        assert len(result) == 1


class TestProcessorCandidateSiteOutput:
    def test_cluster_to_candidate_sites(self):
        from processor import cluster_to_candidate_sites
        clusters = [
            [
                {"path": "/img/a1.jpg", "filename": "building_front.jpg",
                 "lat": 41.862644, "lon": -87.661244, "time": "2026-06-21 14:30:00",
                 "dest_path": "/out/a1.jpg"},
                {"path": "/img/a2.jpg", "filename": "roof_overview.jpg",
                 "lat": 41.862650, "lon": -87.661250, "time": "2026-06-21 14:31:00",
                 "dest_path": "/out/a2.jpg"},
            ],
            [
                {"path": "/img/b1.jpg", "filename": "antenna_north.jpg",
                 "lat": 41.867000, "lon": -87.665000, "time": "2026-06-21 15:00:00",
                 "dest_path": "/out/b1.jpg"},
            ],
        ]
        sites = cluster_to_candidate_sites(clusters, agency_name="Chicago PD")
        assert len(sites) == 2
        assert isinstance(sites[0], CandidateSite)
        assert sites[0].identity.agency_name == "Chicago PD"
        assert len(sites[0].photos) == 2
        assert sites[0].photos[0].category == "Site"   # "building_front" -> Site
        assert sites[1].photos[0].category == "RF"     # "antenna_north" -> RF
