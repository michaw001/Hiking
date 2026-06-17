import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import folium
from folium.plugins import MiniMap
from .parser import haversine

MAX_SPEED_KMH = 25.0
MAX_GAP_SEC = 900

MONTH_COLORS = {
    1:  "#1565C0", 2:  "#1976D2", 3:  "#2E7D32", 4:  "#43A047",
    5:  "#F9A825", 6:  "#EF6C00", 7:  "#D32F2F", 8:  "#C62828",
    9:  "#6A1B9A", 10: "#7B1FA2", 11: "#4E342E", 12: "#37474F",
}
MONTHS_DE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
             "Juli", "August", "September", "Oktober", "November", "Dezember"]


def parse_gpx_for_map(filepath, year):
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
    if first_ts.year != year:
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
        "segments": segments,
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
    return f"""
    <div style="font-family:Arial,sans-serif;min-width:170px">
      <b style="font-size:14px;color:#1565C0">{date_str}</b>
      <hr style="margin:5px 0;border-color:#ddd">
      <table style="font-size:12px;border-collapse:collapse">
        <tr><td style="color:#777;padding:2px 8px 2px 0">Distanz</td>
            <td style="font-weight:bold">{dist}</td></tr>
        <tr><td style="color:#777;padding:2px 8px 2px 0">Dauer</td>
            <td>{dur}</td></tr>
        <tr><td style="color:#777;padding:2px 8px 2px 0">Ø Tempo</td>
            <td>{spd}</td></tr>
      </table>
      <div style="text-align:right;margin-top:6px">
        <button onclick="deleteTour({tour['tour_id']})" title="Tour ausblenden"
                style="background:none;border:none;cursor:pointer;font-size:15px;
                       color:#c0392b;padding:2px 4px;line-height:1">🗑</button>
      </div>
    </div>"""


def midpoint(segment):
    return segment[len(segment) // 2]


def build_year_map(year, gpx_dir, output_path, tour_lookup):
    tours = []
    for fname in sorted(os.listdir(gpx_dir)):
        if not fname.lower().endswith(".gpx"):
            continue
        if fname not in tour_lookup:
            continue
        result = parse_gpx_for_map(os.path.join(gpx_dir, fname), year)
        if result and result["segments"]:
            result["tour_id"] = tour_lookup[fname]
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

    month_layers = {}
    for month in sorted({t["date"].month for t in tours}):
        n = sum(1 for t in tours if t["date"].month == month)
        layer = folium.FeatureGroup(name=f"{MONTHS_DE[month]}  ({n} Touren)", show=True)
        month_layers[month] = layer
        m.add_child(layer)

    tour_poly_map = {}

    for idx, tour in enumerate(sorted(tours, key=lambda x: x["date"])):
        month = tour["date"].month
        color = MONTH_COLORS[month]
        layer = month_layers[month]
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
                weight=4,
                opacity=0.85,
                tooltip=folium.Tooltip(hover_text, sticky=False),
                popup=folium.Popup(popup_html, max_width=230),
            )
            poly.add_to(layer)
            tour_polys.append(poly.get_name())

        tour_poly_map[tour_key] = {"layers": tour_polys, "color": color, "weight": 4, "opacity": 0.85}

        if tour["segments"]:
            longest_seg = max(tour["segments"], key=len)
            mid = midpoint(longest_seg)
            folium.Marker(
                location=mid,
                icon=folium.DivIcon(
                    html=f'<div style="'
                         f'background:{color};color:white;font-size:10px;font-family:Arial,sans-serif;'
                         f'font-weight:bold;padding:2px 5px;border-radius:3px;'
                         f'white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,0.4);'
                         f'opacity:0.92">'
                         f'{date_label}</div>',
                    icon_size=(80, 20),
                    icon_anchor=(40, 10),
                ),
                popup=folium.Popup(popup_html, max_width=230),
                tooltip=hover_text,
            ).add_to(layer)

        if tour["segments"]:
            start = tour["segments"][0][0]
            folium.CircleMarker(
                location=start,
                radius=5,
                color="white",
                weight=1.5,
                fill=True,
                fill_color=color,
                fill_opacity=1.0,
                popup=folium.Popup(popup_html, max_width=230),
                tooltip=hover_text,
            ).add_to(layer)

    used_months = sorted({t["date"].month for t in tours})
    legend_rows = "".join(
        f'<tr><td><span style="display:inline-block;width:16px;height:10px;'
        f'background:{MONTH_COLORS[m]};border-radius:2px;margin-right:6px"></span></td>'
        f'<td style="font-size:12px;padding:1px 0">{MONTHS_DE[m]}</td></tr>'
        for m in used_months
    )
    legend_html = f"""
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
                padding:10px 14px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.3);
                font-family:Arial,sans-serif">
      <b style="font-size:13px">Wanderungen {year}</b>
      <table style="margin-top:6px;border-collapse:collapse">{legend_rows}</table>
      <div style="margin-top:6px;font-size:11px;color:#888">{len(tours)} Touren · Klick auf Trail = Details</div>
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

  window.deleteTour = function(id) {{
    if (!confirm('Diese Tour wirklich ausblenden?')) return;
    fetch('/tour/' + id + '/delete', {{method: 'POST'}})
      .then(function(r) {{ if (r.ok) {{ location.reload(); }} else {{ alert('Ausblenden fehlgeschlagen.'); }} }});
  }};

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

    select_all_script = """
<script>
(function() {
  setTimeout(function() {
    var overlays = document.querySelector('.leaflet-control-layers-overlays');
    if (!overlays) return;

    var allDiv = document.createElement('div');
    allDiv.style.cssText = 'border-bottom:1px solid #ccc;margin-bottom:5px;padding-bottom:5px;';
    var label = document.createElement('label');
    label.style.cssText = 'display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:bold;';
    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = true;
    label.appendChild(cb);
    label.appendChild(document.createTextNode(' Alle'));
    allDiv.appendChild(label);
    overlays.insertBefore(allDiv, overlays.firstChild);

    function updateMaster() {
      var items = Array.from(overlays.querySelectorAll('input[type="checkbox"]')).filter(function(c){ return c !== cb; });
      var n = items.filter(function(c){ return c.checked; }).length;
      cb.checked = n === items.length;
      cb.indeterminate = n > 0 && n < items.length;
    }

    cb.addEventListener('change', function() {
      var want = cb.checked;
      overlays.querySelectorAll('input[type="checkbox"]').forEach(function(c) {
        if (c !== cb && c.checked !== want) c.click();
      });
    });

    overlays.querySelectorAll('input[type="checkbox"]').forEach(function(c) {
      if (c !== cb) c.addEventListener('change', updateMaster);
    });
  }, 300);
})();
</script>"""
    m.get_root().html.add_child(folium.Element(select_all_script))

    m.save(str(output_path))
    return str(output_path)
