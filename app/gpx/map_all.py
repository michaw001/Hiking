import os
import math
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import folium
from folium.plugins import MiniMap
from .parser import haversine

MAX_SPEED_KMH = 25.0
MAX_GAP_SEC = 900

YEAR_COLORS = {
    2016: "#E53935",
    2017: "#E91E63",
    2018: "#9C27B0",
    2019: "#3F51B5",
    2020: "#0288D1",
    2021: "#00897B",
    2022: "#43A047",
    2023: "#F9A825",
    2024: "#EF6C00",
    2025: "#6D4C41",
    2026: "#546E7A",
    2027: "#00ACC1",
    2028: "#558B2F",
    2029: "#F57F17",
    2030: "#4527A0",
}


def simplify(points, tolerance=0.0001):
    if len(points) < 3:
        return points

    def point_line_dist(p, a, b):
        if a == b:
            return haversine(p[0], p[1], a[0], a[1])
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
        return math.sqrt((p[0] - a[0] - t * dx) ** 2 + (p[1] - a[1] - t * dy) ** 2)

    dmax, idx = 0, 0
    for i in range(1, len(points) - 1):
        d = point_line_dist(points[i], points[0], points[-1])
        if d > dmax:
            dmax, idx = d, i

    if dmax > tolerance:
        left = simplify(points[:idx + 1], tolerance)
        right = simplify(points[idx:], tolerance)
        return left[:-1] + right
    return [points[0], points[-1]]


def parse_gpx_for_all_map(filepath):
    try:
        tree = ET.parse(filepath)
    except ET.ParseError:
        return None
    root = tree.getroot()
    trkpts = root.findall(".//{http://www.topografix.com/GPX/1/1}trkpt")
    if not trkpts:
        return None

    raw = []
    for pt in trkpts:
        try:
            lat, lon = float(pt.get("lat")), float(pt.get("lon"))
        except (TypeError, ValueError):
            continue
        time_el = pt.find("{http://www.topografix.com/GPX/1/1}time")
        ts = None
        if time_el is not None and time_el.text:
            try:
                ts = datetime.strptime(time_el.text.strip(), "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass
        raw.append((lat, lon, ts))

    if not raw:
        return None

    first_ts = next((p[2] for p in raw if p[2] is not None), None)
    if first_ts is None:
        try:
            first_ts = datetime.strptime(
                os.path.basename(filepath).replace("Maps3D ", "")[:10], "%Y-%m-%d"
            )
        except ValueError:
            return None

    segments, current, distance_km = [], [], 0.0
    current.append((raw[0][0], raw[0][1]))
    for i in range(1, len(raw)):
        lat1, lon1, t1 = raw[i - 1]
        lat2, lon2, t2 = raw[i]
        d = haversine(lat1, lon1, lat2, lon2)
        if t1 and t2:
            dt = (t2 - t1).total_seconds()
            if dt <= 0 or dt > MAX_GAP_SEC:
                if len(current) > 1:
                    segments.append(current)
                current = [(lat2, lon2)]
                continue
            if (d / (dt / 3600)) <= MAX_SPEED_KMH:
                distance_km += d
                current.append((lat2, lon2))
            else:
                if len(current) > 1:
                    segments.append(current)
                current = [(lat2, lon2)]
        else:
            if d <= 0.5:
                distance_km += d
                current.append((lat2, lon2))
    if len(current) > 1:
        segments.append(current)

    duration_min = avg_speed = None
    for child in root.iter():
        tag = child.tag.split("}")[-1].lower()
        if "realsecondsSpent".lower() in tag:
            try:
                duration_min = float(child.text) / 60.0
            except (TypeError, ValueError):
                pass
        if "realspeed" in tag:
            try:
                avg_speed = float(child.text) * 3.6
            except (TypeError, ValueError):
                pass

    return {
        "date": first_ts,
        "year": first_ts.year,
        "segments": [simplify(seg) for seg in segments if len(seg) >= 2],
        "distance_km": round(distance_km, 2),
        "duration_min": round(duration_min, 0) if duration_min else None,
        "avg_speed_kmh": round(avg_speed, 1) if avg_speed else None,
    }


def make_popup_html(tour):
    date_str = tour["date"].strftime("%d.%m.%Y")
    dist = f"{tour['distance_km']:.1f} km"
    dur = (f"{int(tour['duration_min'] // 60)}h {int(tour['duration_min'] % 60)}min"
           if tour["duration_min"] else "–")
    spd = f"{tour['avg_speed_kmh']} km/h" if tour["avg_speed_kmh"] else "–"
    color = YEAR_COLORS.get(tour["year"], "#555")
    return f"""
    <div style="font-family:Arial,sans-serif;min-width:170px">
      <b style="font-size:14px;color:{color}">{date_str}</b>
      <hr style="margin:5px 0;border-color:#ddd">
      <table style="font-size:12px;border-collapse:collapse">
        <tr><td style="color:#777;padding:2px 8px 2px 0">Distanz</td>
            <td style="font-weight:bold">{dist}</td></tr>
        <tr><td style="color:#777;padding:2px 8px 2px 0">Dauer</td>
            <td>{dur}</td></tr>
        <tr><td style="color:#777;padding:2px 8px 2px 0">Ø Tempo</td>
            <td>{spd}</td></tr>
      </table>
    </div>"""


def build_all_map(gpx_dir, output_path):
    tours = []
    for fname in sorted(os.listdir(gpx_dir)):
        if not fname.lower().endswith(".gpx"):
            continue
        result = parse_gpx_for_all_map(os.path.join(gpx_dir, fname))
        if result and result["segments"]:
            tours.append(result)

    if not tours:
        return None

    all_pts = [pt for t in tours for seg in t["segments"] for pt in seg]
    min_lat = min(p[0] for p in all_pts)
    max_lat = max(p[0] for p in all_pts)
    min_lon = min(p[1] for p in all_pts)
    max_lon = max(p[1] for p in all_pts)

    m = folium.Map(tiles="OpenStreetMap", control_scale=True)
    m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]], padding=[30, 30])

    present_years = sorted({t["year"] for t in tours})
    year_layers = {}
    for year in present_years:
        n = sum(1 for t in tours if t["year"] == year)
        color = YEAR_COLORS.get(year, "#555")
        layer = folium.FeatureGroup(name=f"{year}  ({n} Touren)", show=True)
        year_layers[year] = layer
        m.add_child(layer)

    tour_poly_map = {}

    for idx, tour in enumerate(sorted(tours, key=lambda x: x["date"])):
        year = tour["year"]
        color = YEAR_COLORS.get(year, "#555")
        layer = year_layers.get(year)
        if not layer:
            continue

        popup_html = make_popup_html(tour)
        date_label = tour["date"].strftime("%d.%m.%Y")
        hover_text = f"{date_label}  –  {tour['distance_km']:.1f} km"
        tour_key = f"t{idx}_{tour['date'].strftime('%Y%m%d%H%M%S')}"
        tour_polys = []

        for seg in tour["segments"]:
            if len(seg) < 2:
                continue
            poly = folium.PolyLine(
                locations=seg,
                color=color,
                weight=3,
                opacity=0.75,
                tooltip=folium.Tooltip(hover_text, sticky=False),
                popup=folium.Popup(popup_html, max_width=230),
            )
            poly.add_to(layer)
            tour_polys.append(poly.get_name())

        tour_poly_map[tour_key] = {"layers": tour_polys, "color": color, "weight": 3, "opacity": 0.75}

        if tour["segments"]:
            longest_seg = max(tour["segments"], key=len)
            mid = longest_seg[len(longest_seg) // 2]
            folium.Marker(
                location=mid,
                icon=folium.DivIcon(
                    html=f'<div style="background:{color};color:white;font-size:9px;'
                         f'font-family:Arial,sans-serif;font-weight:bold;padding:1px 4px;'
                         f'border-radius:3px;white-space:nowrap;'
                         f'box-shadow:0 1px 3px rgba(0,0,0,.4);opacity:0.9">'
                         f'{date_label}</div>',
                    icon_size=(80, 18),
                    icon_anchor=(40, 9),
                ),
                popup=folium.Popup(popup_html, max_width=230),
                tooltip=hover_text,
            ).add_to(layer)

        start = tour["segments"][0][0]
        folium.CircleMarker(
            location=start,
            radius=4,
            color="white",
            weight=1.5,
            fill=True,
            fill_color=color,
            fill_opacity=1.0,
            popup=folium.Popup(popup_html, max_width=230),
            tooltip=hover_text,
        ).add_to(layer)

    legend_rows = "".join(
        f'<tr><td><span style="display:inline-block;width:16px;height:10px;'
        f'background:{YEAR_COLORS.get(y, "#555")};border-radius:2px;margin-right:6px"></span></td>'
        f'<td style="font-size:12px;padding:1px 0">{y}</td>'
        f'<td style="font-size:11px;color:#888;padding:1px 0 1px 8px">'
        f'{sum(1 for t in tours if t["year"] == y)} Touren</td></tr>'
        for y in present_years
    )
    legend_html = f"""
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
                padding:10px 14px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.3);
                font-family:Arial,sans-serif">
      <b style="font-size:13px">Alle Wanderungen</b>
      <table style="margin-top:6px;border-collapse:collapse">{legend_rows}</table>
      <div style="margin-top:6px;font-size:11px;color:#888">{len(tours)} Touren gesamt · Klick = Details</div>
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)
    MiniMap(toggle_display=True, position="bottomright").add_to(m)

    highlight_script = f"""
<script>
(function() {{
  var tourData = {json.dumps(tour_poly_map)};
  var activeTour = null;
  var mapObj = window["{m.get_name()}"];

  function applyStyle(name, color, weight, opacity) {{
    var l = window[name];
    if (!l) return;
    l.setStyle({{color: color, weight: weight, opacity: opacity}});
    if (color === '#FFE033') l.bringToFront();
  }}

  function highlight(key) {{
    if (activeTour && activeTour !== key) reset(activeTour);
    activeTour = key;
    tourData[key].layers.forEach(function(n) {{ applyStyle(n, '#FFE033', 7, 1); }});
  }}

  function reset(key) {{
    var td = tourData[key];
    td.layers.forEach(function(n) {{ applyStyle(n, td.color, td.weight, td.opacity); }});
  }}

  setTimeout(function() {{
    Object.keys(tourData).forEach(function(key) {{
      tourData[key].layers.forEach(function(name) {{
        var l = window[name];
        if (!l) return;
        l.on('click', function(e) {{
          highlight(key);
          L.DomEvent.stopPropagation(e);
        }});
      }});
    }});
    mapObj.on('click', function() {{
      if (activeTour) {{ reset(activeTour); activeTour = null; }}
    }});
  }}, 200);
}})();
</script>"""
    m.get_root().html.add_child(folium.Element(highlight_script))

    m.save(str(output_path))
    return str(output_path)
