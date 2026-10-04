from pathlib import Path

from espana_outdoors_pipeline.scanner import detect_format, scan


def test_detect_format():
    assert detect_format(Path("route.GPX")) == (".gpx", "gpx")
    assert detect_format(Path("map.osm.pbf")) == (".osm.pbf", "osm.pbf")
    assert detect_format(Path("notes.txt")) is None


def test_scan_collects_metadata_and_hashes(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    source = root / "route.gpx"
    source.write_text("<gpx></gpx>", encoding="utf-8")
    (root / "ignore.txt").write_text("ignore", encoding="utf-8")

    catalog = tmp_path / "catalog.sqlite"
    result = scan(root, catalog, hash_mode="always", progress_every=1)

    assert result["files"] == 1
    assert result["hashed"] == 1
    assert result["errors"] == 0
    assert catalog.exists()


def test_scan_reuses_unchanged_hash(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    source = root / "route.kml"
    source.write_text("<kml></kml>", encoding="utf-8")
    catalog = tmp_path / "catalog.sqlite"

    first = scan(root, catalog, hash_mode="always")
    second = scan(root, catalog, hash_mode="auto")

    assert first["hashed"] == 1
    assert second["hashed"] == 0
    assert second["reused"] == 1
