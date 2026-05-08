import asyncio
import httpx
import os
from bus_service import _get_tdx_token, TDX_BASE_URL

def test_a2(city_code):
    token = _get_tdx_token()
    url = f"{TDX_BASE_URL}/v2/Bus/RealTimeNearStop/City/{city_code}"
    params = {"$format": "JSON", "$top": 5}
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get(url, params=params, headers=headers)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    if data:
        print("First record keys:", data[0].keys())
        print("First record StopName:", data[0].get("StopName"))
        print("First record PlateNumb:", data[0].get("PlateNumb"))

test_a2("Tainan")
