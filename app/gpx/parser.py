import os
import math
import xml.etree.ElementTree as ET
from datetime import datetime

MAX_SPEED_KMH = 25.0
MAX_GAP_SEC = 900
MAX_STEP_KM = 0.5


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_gpx(filepath):
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError:
        return None

    trkpts = root.findall(".//{http://www.topografix.com/GPX/1/1}trkpt")
    if not trkpts:
        trkpts = root.findall(".//trkpt")
    if not trkpts:
        return None

    coords = []
    elevations = []
    timestamps = []
    first_time = None

    for pt in trkpts:
        try:
            lat = float(pt.get("lat"))
            lon = float(pt.get("lon"))
        except (TypeError, ValueError):
            continue

        ele_el = pt.find("{http://www.topografix.com/GPX/1/1}ele")
        if ele_el is None:
            ele_el = pt.find("ele")
        ele = float(ele_el.text) if ele_el is not None and ele_el.text else None

        ts = None
        time_el = pt.find("{http://www.topografix.com/GPX/1/1}time")
        if time_el is None:
            time_el = pt.find("time")
        if time_el is not None and time_el.text:
            try:
                ts = datetime.strptime(time_el.text.strip(), "%Y-%m-%dT%H:%M:%SZ")
                if first_time is None:
                    first_time = ts
            except ValueError:
                pass

        coords.append((lat, lon))
        elevations.append(ele)
        timestamps.append(ts)

    if len(coords) < 2:
        return None

    has_times = all(t is not None for t in timestamps)
    distance_km = 0.0
    for i in range(len(coords) - 1):
        d = haversine(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
        if has_times:
            dt_sec = (timestamps[i + 1] - timestamps[i]).total_seconds()
            if dt_sec <= 0 or dt_sec > MAX_GAP_SEC:
                continue
            if (d / (dt_sec / 3600)) <= MAX_SPEED_KMH:
                distance_km += d
        else:
            if d <= MAX_STEP_KM:
                distance_km += d

    ascent = descent = 0.0
    valid_ele = [e for e in elevations if e is not None]
    for i in range(1, len(valid_ele)):
        diff = valid_ele[i] - valid_ele[i - 1]
        if diff > 0:
            ascent += diff
        else:
            descent += abs(diff)

    min_ele = min(valid_ele) if valid_ele else None
    max_ele = max(valid_ele) if valid_ele else None

    duration_min = None
    avg_speed_kmh = None

    extensions = root.find(".//{http://www.topografix.com/GPX/1/1}extensions")
    if extensions is None:
        extensions = root.find(".//extensions")
    if extensions is not None:
        for child in extensions:
            tag = child.tag.lower()
            if "realsecondsSpent".lower() in tag or "realseconts" in tag:
                try:
                    duration_min = float(child.text) / 60.0
                except (TypeError, ValueError):
                    pass
            if "realspeed" in tag:
                try:
                    avg_speed_kmh = float(child.text) * 3.6
                except (TypeError, ValueError):
                    pass

    if first_time is None:
        basename = os.path.basename(filepath)
        try:
            date_part = basename.replace("Maps3D ", "")[:10]
            first_time = datetime.strptime(date_part, "%Y-%m-%d")
        except ValueError:
            pass

    return {
        "filename": os.path.basename(filepath),
        "date": first_time,
        "distance_km": round(distance_km, 2),
        "duration_min": round(duration_min, 1) if duration_min else None,
        "avg_speed_kmh": round(avg_speed_kmh, 2) if avg_speed_kmh else None,
        "ascent_m": round(ascent, 0),
        "descent_m": round(descent, 0),
        "min_ele_m": round(min_ele, 0) if min_ele is not None else None,
        "max_ele_m": round(max_ele, 0) if max_ele is not None else None,
        "num_points": len(coords),
    }
