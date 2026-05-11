import asyncio
from bus_service import _fetch_tdx_realtime
data = _fetch_tdx_realtime('Kaohsiung')
if data:
    print(data[0].keys())
    if 'StopName' in data[0]:
        print("StopName exists:", data[0]['StopName'])
    else:
        print("No StopName in A1 data.")
