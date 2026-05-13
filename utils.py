import math

def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """計算兩個 GPS 座標之間的距離（公尺）。"""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0
    R = 6_371_000  # 地球半徑（公尺）
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
