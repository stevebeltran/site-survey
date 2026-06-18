import os
import sys
import tempfile
import unittest
import datetime
from types import SimpleNamespace
from pathlib import Path

from PIL import Image
from docx import Document


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import processor
import reporter


class PipelineTests(unittest.TestCase):
    def test_cluster_images_uses_transitive_connectivity(self):
        images_meta = [
            {"path": "a.jpg", "lat": 0.0, "lon": 0.0, "time": None},
            {"path": "b.jpg", "lat": 0.0, "lon": 0.0005, "time": None},
            {"path": "c.jpg", "lat": 0.0, "lon": 0.0010, "time": None},
        ]

        clusters = processor.cluster_images(images_meta, radius_meters=90.0)

        self.assertEqual(len(clusters), 1)
        self.assertEqual([img["path"] for img in clusters[0]], ["a.jpg", "b.jpg", "c.jpg"])

    def test_generate_word_report_uses_generic_defaults_when_customer_info_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            site_image = tmp_path / "site.jpg"
            Image.new("RGB", (100, 100), color="white").save(site_image)

            site_folder = tmp_path / "site"
            site_folder.mkdir()
            drawing_path = site_folder / "engineering_layout.png"
            Image.new("RGB", (200, 100), color="black").save(drawing_path)

            report_path = tmp_path / "report.docx"
            site_data = [
                {
                    "address": "123 Example St, Test City, TS",
                    "latitude": 41.0,
                    "longitude": -87.0,
                    "folder_path": str(site_folder),
                    "analysis": {
                        "roof_access": "Unknown",
                        "roof_type": "Unknown",
                        "mounting_structures": [],
                        "hardware": [],
                    },
                    "airspace": "Class G",
                    "airfield_info": "Test Field (1.00 km)",
                    "images": [
                        {
                            "filename": "site.jpg",
                            "path": str(site_image),
                            "selected_for_report": True,
                        }
                    ],
                }
            ]

            reporter.generate_word_report(site_data, str(report_path))

            self.assertTrue(report_path.exists())
            doc = Document(str(report_path))
            text = "\n".join(p.text for p in doc.paragraphs)
            cell_text = "\n".join(cell.text for table in doc.tables for row in table.rows for cell in row.cells)
            combined = f"{text}\n{cell_text}"

            self.assertNotIn("Lansing Police Department", combined)

    def test_extract_exif_gps_uses_exifread_for_heic_metadata(self):
        class DummyRatio:
            def __init__(self, num, den):
                self.num = num
                self.den = den

        class DummyTag:
            def __init__(self, values, text):
                self.values = values
                self.text = text

            def __str__(self):
                return self.text

        fake_tags = {
            "GPS GPSLatitude": DummyTag([DummyRatio(38, 1), DummyRatio(42, 1), DummyRatio(1321, 50)], "GPS GPSLatitude"),
            "GPS GPSLatitudeRef": DummyTag("N", "N"),
            "GPS GPSLongitude": DummyTag([DummyRatio(90, 1), DummyRatio(24, 1), DummyRatio(2497, 50)], "GPS GPSLongitude"),
            "GPS GPSLongitudeRef": DummyTag("W", "W"),
            "EXIF DateTimeOriginal": DummyTag("2026:05:06 08:03:22", "2026:05:06 08:03:22"),
        }

        with tempfile.NamedTemporaryFile(suffix=".HEIC", delete=False) as tmp:
            tmp.write(b"test")
            tmp_path = tmp.name

        try:
            original_exifread = processor.exifread
            processor.exifread = SimpleNamespace(
                process_file=lambda fh, details=False: fake_tags
            )

            lat, lon, captured = processor._extract_gps_with_exifread(tmp_path)

            self.assertAlmostEqual(lat, 38.70733888888889)
            self.assertAlmostEqual(lon, -90.41387222222222)
            self.assertEqual(captured, datetime.datetime(2026, 5, 6, 8, 3, 22))
        finally:
            processor.exifread = original_exifread
            os.unlink(tmp_path)

    def test_process_and_organize_images_scopes_to_explicit_image_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_dir = tmp_path / "raw"
            output_dir = tmp_path / "processed"
            source_dir.mkdir()

            old_image = source_dir / "old_site.jpg"
            new_image = source_dir / "new_upload.jpg"
            Image.new("RGB", (100, 100), color="red").save(old_image)
            Image.new("RGB", (100, 100), color="blue").save(new_image)

            original_extract = processor.extract_exif_gps
            original_reverse_geocode = processor.reverse_geocode
            try:
                processor.extract_exif_gps = lambda path: (
                    41.0,
                    -87.0,
                    datetime.datetime(2026, 6, 15, 12, 0, 0),
                )
                processor.reverse_geocode = lambda lat, lon: "100 Test St, Test City, TS"

                site_data = processor.process_and_organize_images(
                    str(source_dir),
                    str(output_dir),
                    image_paths=[str(new_image)],
                )
            finally:
                processor.extract_exif_gps = original_extract
                processor.reverse_geocode = original_reverse_geocode

            processed_filenames = [
                img["filename"]
                for site in site_data
                for img in site.get("images", [])
            ]
            self.assertEqual(processed_filenames, ["new_upload.jpg"])
            self.assertFalse(any(output_dir.rglob("old_site.jpg")))

    def test_create_engineering_drawing_writes_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bg_path = tmp_path / "bg.png"
            out_path = tmp_path / "engineering_layout.png"
            Image.new("RGB", (400, 200), color="gray").save(bg_path)

            markers = [
                {"type": "Electric", "label": "120V", "node_x": 20, "node_y": 30, "label_x": 10, "label_y": 20},
                {"type": "RF", "label": "Antenna", "node_x": 60, "node_y": 50, "label_x": 45, "label_y": 40},
            ]

            reporter.create_engineering_drawing(str(bg_path), str(out_path), markers, "Test note")

            self.assertTrue(out_path.exists())


if __name__ == "__main__":
    unittest.main()
