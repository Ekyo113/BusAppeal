import json
import asyncio
import os
from datetime import datetime, timedelta
from ai_service import AIService
from utils import haversine_meters

async def local_test():
    # 1. 載入資料
    print("Loading data...")
    with open("gps_log.json", "r", encoding="utf-8") as f:
        gps_logs = json.load(f)
    
    with open("route_chedules.json", "r", encoding="utf-8") as f:
        all_schedules = json.load(f)
    
    # 2. 過濾 EAA-782
    target_plate = "EAA-782"
    eaa782_gps = [log for log in gps_logs if log["plate_number"] == target_plate]
    print(f"Total GPS logs for {target_plate}: {len(eaa782_gps)}")
    
    if not eaa782_gps:
        print("No GPS data found for EAA-782.")
        return

    # 3. 按日期分組
    gps_by_date = {}
    for log in eaa782_gps:
        # recorded_at format: "2026-05-05 02:00:00.000927+00"
        date_str = log["recorded_at"].split(" ")[0]
        if date_str not in gps_by_date:
            gps_by_date[date_str] = []
        gps_by_date[date_str].append(log)
    
    print(f"Found data for dates: {sorted(list(gps_by_date.keys()))}")

    ai_service = AIService()

    # 4. 對每一天進行測試
    for date_str in sorted(gps_by_date.keys()):
        print(f"\n{'='*50}")
        print(f"Testing for date: {date_str}")
        
        day_gps = gps_by_date[date_str]
        
        # 轉換時間並排序 (比照 bus_service.py)
        gps_data = []
        for row in day_gps:
            try:
                # TDX/DB 格式可能是 "2026-05-05 02:00:00.000927+00"
                # 我們轉換為 ISO 格式方便處理
                ts = row["recorded_at"].replace(" ", "T")
                if "+" in ts:
                    ts = ts.split("+")[0] + "Z"
                
                utc_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                tw_dt = utc_dt + timedelta(hours=8)
                row["recorded_at_tw"] = tw_dt.isoformat()
                gps_data.append(row)
            except Exception as e:
                print(f"Error parsing time: {row['recorded_at']} -> {e}")
                gps_data.append(row)
        
        gps_data.sort(key=lambda x: x["recorded_at"])
        
        # 4. 過濾「原地中退」點 (經緯度差異皆小於 0.0001)
        filtered_gps = []
        stationary_count = 0
        last_lat, last_lon = None, None
        
        for row in gps_data:
            curr_lat = row.get("lat")
            curr_lon = row.get("lon")
            
            if last_lat is not None and last_lon is not None:
                if abs(curr_lat - last_lat) < 0.0001 and abs(curr_lon - last_lon) < 0.0001:
                    stationary_count += 1
                    continue
            
            filtered_gps.append(row)
            last_lat, last_lon = curr_lat, curr_lon
        
        gps_data = filtered_gps
        if stationary_count > 0:
            print(f"Stationary points filtered (原地中退): {stationary_count}")
        
        # 識別當天出現過的路線
        routes = sorted(list(set([r["route_name"] for r in gps_data if r.get("route_name")])))
        print(f"Routes identified: {routes}")
        
        # 過濾時刻表
        day_schedules = [s for s in all_schedules if s["route_name"] in routes]
        print(f"Schedules found: {len(day_schedules)} entries")
        
        # 5. 呼叫 AI 分析
        print("Calling AI for analysis...")
        analysis = await ai_service.analyze_bus_operating_plan(
            target_plate, date_str, gps_data, day_schedules
        )
        
        # 6. 輸出結果
        print("\n[AI Analysis Result]")
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        
        # 簡單驗證
        if analysis.get("plan_name") == "分析失敗":
            print("!!! WARNING: AI Analysis Failed for this day.")
        elif not analysis.get("route_details"):
            print("!!! WARNING: No route details generated.")
        else:
            print("Analysis successful.")

if __name__ == "__main__":
    asyncio.run(local_test())
