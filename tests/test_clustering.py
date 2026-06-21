import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from processor import cluster_images_dbscan


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
