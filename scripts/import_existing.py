#!/usr/bin/env python3
"""
One-time import script: imports all GPX files from the original Maps_3D/ directory
for a specified user.

Usage:
    cd /Volumes/Macintosh-HD-Data/Programmieren/Claude/Hiking
    python scripts/import_existing.py --username michael \
        --gpx-source /Volumes/Macintosh-HD-Data/Programmieren/Claude/Wandern/Maps_3D
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db
from app.models import User, Tour
from app.gpx.parser import parse_gpx


def import_tours(username: str, source_dir: Path):
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"User '{username}' nicht gefunden. Bitte zuerst im Web registrieren.")
            sys.exit(1)

        gpx_dir = user.get_gpx_dir()
        gpx_dir.mkdir(parents=True, exist_ok=True)

        gpx_files = sorted(source_dir.glob("*.gpx"))
        print(f"Gefunden: {len(gpx_files)} GPX-Dateien in {source_dir}")

        imported = skipped = errors = 0

        for gpx_file in gpx_files:
            if Tour.query.filter_by(user_id=user.id, filename=gpx_file.name).first():
                skipped += 1
                continue

            dest = gpx_dir / gpx_file.name
            shutil.copy2(gpx_file, dest)

            result = parse_gpx(str(dest))
            if result is None:
                dest.unlink()
                errors += 1
                print(f"  SKIP (Parsefehler): {gpx_file.name}")
                continue

            tour = Tour(
                user_id=user.id,
                filename=result["filename"],
                gpx_path=str(dest),
                tour_date=result["date"].date() if result["date"] else None,
                distance_km=result["distance_km"],
                duration_min=result["duration_min"],
                avg_speed_kmh=result["avg_speed_kmh"],
                ascent_m=result["ascent_m"],
                descent_m=result["descent_m"],
                min_ele_m=result["min_ele_m"],
                max_ele_m=result["max_ele_m"],
                num_points=result["num_points"],
            )
            db.session.add(tour)
            imported += 1

            if imported % 50 == 0:
                db.session.commit()
                print(f"  {imported} importiert...")

        db.session.commit()
        print(f"\nFertig: {imported} importiert, {skipped} bereits vorhanden, {errors} Parsefehler")
        print(f"Karten werden beim ersten Aufruf von /map/year/<jahr> und /map/all generiert.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import existing GPX tours into Hiking app")
    parser.add_argument("--username", required=True, help="Username to import for")
    parser.add_argument("--gpx-source", required=True, type=Path, help="Source directory with GPX files")
    args = parser.parse_args()

    if not args.gpx_source.is_dir():
        print(f"Fehler: Verzeichnis nicht gefunden: {args.gpx_source}")
        sys.exit(1)

    import_tours(args.username, args.gpx_source)
