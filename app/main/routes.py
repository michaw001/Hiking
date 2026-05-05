from collections import defaultdict
from pathlib import Path

from flask import render_template, redirect, url_for, flash, send_file, request, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from .. import db
from ..models import Tour, MapCache
from ..gpx.parser import parse_gpx
from ..gpx.map_year import build_year_map
from ..gpx.map_all import build_all_map, YEAR_COLORS
from ..gpx.excel_export import generate_xlsx_for_user
from . import main_bp
from .forms import UploadForm


def invalidate_maps(user_id, years=None):
    maps_dir = Path(current_user.get_maps_dir())
    if years:
        for year in years:
            cache = MapCache.query.filter_by(user_id=user_id, map_type="year", year=year).first()
            if cache:
                p = Path(cache.html_path)
                if p.exists():
                    p.unlink()
                db.session.delete(cache)
    all_cache = MapCache.query.filter_by(user_id=user_id, map_type="all").first()
    if all_cache:
        p = Path(all_cache.html_path)
        if p.exists():
            p.unlink()
        db.session.delete(all_cache)
    db.session.commit()


@main_bp.route("/")
@login_required
def dashboard():
    tours = Tour.query.filter_by(user_id=current_user.id).order_by(Tour.tour_date).all()

    yearly = defaultdict(lambda: {"count": 0, "km": 0.0, "ascent": 0.0, "duration_h": 0.0})
    for t in tours:
        if t.tour_date is None:
            continue
        y = t.tour_date.year
        yearly[y]["count"] += 1
        yearly[y]["km"] += t.distance_km or 0
        yearly[y]["ascent"] += t.ascent_m or 0
        yearly[y]["duration_h"] += (t.duration_min or 0) / 60.0

    years_sorted = sorted(yearly.keys())
    totals = {
        "tours": sum(v["count"] for v in yearly.values()),
        "km": sum(v["km"] for v in yearly.values()),
        "ascent": sum(v["ascent"] for v in yearly.values()),
        "hours": sum(v["duration_h"] for v in yearly.values()),
    }
    year_min = years_sorted[0] if years_sorted else ""
    year_max = years_sorted[-1] if years_sorted else ""

    return render_template(
        "main/dashboard.html",
        yearly=yearly,
        years=years_sorted,
        totals=totals,
        year_colors=YEAR_COLORS,
        year_min=year_min,
        year_max=year_max,
    )


@main_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        files = request.files.getlist("gpx_files")
        gpx_dir = current_user.get_gpx_dir()
        gpx_dir.mkdir(parents=True, exist_ok=True)

        imported = skipped = duplicate = 0
        invalidated_years = set()

        for file in files:
            if not file.filename:
                continue
            if not file.filename.lower().endswith(".gpx"):
                skipped += 1
                continue

            filename = secure_filename(file.filename)
            dest_path = gpx_dir / filename

            existing = Tour.query.filter_by(user_id=current_user.id, filename=filename).first()
            if existing:
                duplicate += 1
                continue

            file.save(str(dest_path))
            result = parse_gpx(str(dest_path))

            if result is None:
                dest_path.unlink(missing_ok=True)
                skipped += 1
                continue

            tour = Tour(
                user_id=current_user.id,
                filename=result["filename"],
                gpx_path=str(dest_path),
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

            if result["date"]:
                invalidated_years.add(result["date"].year)
            imported += 1

        db.session.commit()
        if invalidated_years:
            invalidate_maps(current_user.id, invalidated_years)

        parts = []
        if imported:
            parts.append(f"{imported} Tour(en) importiert")
        if duplicate:
            parts.append(f"{duplicate} bereits vorhanden")
        if skipped:
            parts.append(f"{skipped} übersprungen")
        flash(", ".join(parts) + ".", "success" if imported else "warning")
        return redirect(url_for("main.dashboard"))

    return render_template("main/upload.html", form=form)


@main_bp.route("/map/year/<int:year>")
@login_required
def map_year(year):
    cache = MapCache.query.filter_by(user_id=current_user.id, map_type="year", year=year).first()
    if cache and Path(cache.html_path).exists():
        return send_file(cache.html_path, mimetype="text/html")

    maps_dir = current_user.get_maps_dir()
    maps_dir.mkdir(parents=True, exist_ok=True)
    output_path = maps_dir / f"map_year_{year}.html"
    gpx_dir = str(current_user.get_gpx_dir())

    result = build_year_map(year, gpx_dir, output_path)
    if result is None:
        flash(f"Keine Touren für {year} gefunden.", "warning")
        return redirect(url_for("main.dashboard"))

    if cache:
        cache.html_path = str(output_path)
        from datetime import datetime
        cache.generated_at = datetime.utcnow()
    else:
        cache = MapCache(user_id=current_user.id, map_type="year", year=year, html_path=str(output_path))
        db.session.add(cache)
    db.session.commit()
    return send_file(str(output_path), mimetype="text/html")


@main_bp.route("/map/all")
@login_required
def map_all():
    cache = MapCache.query.filter_by(user_id=current_user.id, map_type="all").first()
    if cache and Path(cache.html_path).exists():
        return send_file(cache.html_path, mimetype="text/html")

    maps_dir = current_user.get_maps_dir()
    maps_dir.mkdir(parents=True, exist_ok=True)
    output_path = maps_dir / "map_all.html"
    gpx_dir = str(current_user.get_gpx_dir())

    result = build_all_map(gpx_dir, output_path)
    if result is None:
        flash("Noch keine Touren vorhanden.", "warning")
        return redirect(url_for("main.dashboard"))

    if cache:
        cache.html_path = str(output_path)
        from datetime import datetime
        cache.generated_at = datetime.utcnow()
    else:
        cache = MapCache(user_id=current_user.id, map_type="all", year=None, html_path=str(output_path))
        db.session.add(cache)
    db.session.commit()
    return send_file(str(output_path), mimetype="text/html")


@main_bp.route("/export/xlsx")
@login_required
def export_xlsx():
    tours = Tour.query.filter_by(user_id=current_user.id).order_by(Tour.tour_date).all()
    buf = generate_xlsx_for_user(tours)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"wanderstatistik_{current_user.username}.xlsx",
    )


@main_bp.route("/tour/<int:tour_id>/delete", methods=["POST"])
@login_required
def delete_tour(tour_id):
    tour = Tour.query.filter_by(id=tour_id, user_id=current_user.id).first_or_404()
    year = tour.tour_date.year if tour.tour_date else None
    gpx_path = Path(tour.gpx_path)
    db.session.delete(tour)
    db.session.commit()
    if gpx_path.exists():
        gpx_path.unlink()
    if year:
        invalidate_maps(current_user.id, {year})
    flash("Tour gelöscht.", "success")
    return redirect(url_for("main.dashboard"))
