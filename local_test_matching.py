import json
import os
from datetime import datetime, timedelta

def find_closest_schedule_time(route_name, target_dt, schedules):
    """
    在時刻表中尋找與 target_dt 最接近的 departure_time。
    考慮跨日邊界（前一日、當日、翌日）。
    """
    route_schedules = [s for s in schedules if s["route_name"].strip() == route_name.strip()]
    if not route_schedules:
        return None, None

    closest_dt = None
    min_diff = None
    matched_time_str = None

    for s in route_schedules:
        dep_time_str = s["departure_time"] # 格式如 "05:55"
        try:
            dep_hour, dep_min = map(int, dep_time_str.split(":"))
            base_dt = target_dt.replace(hour=dep_hour, minute=dep_min, second=0, microsecond=0)
            candidates = [
                base_dt - timedelta(days=1),
                base_dt,
                base_dt + timedelta(days=1)
            ]
            for cand in candidates:
                diff = abs((target_dt - cand).total_seconds())
                if min_diff is None or diff < min_diff:
                    min_diff = diff
                    closest_dt = cand
                    matched_time_str = dep_time_str
        except Exception as e:
            continue

    return closest_dt, matched_time_str

def analyze_bus_transitions(target_plate, gps_logs, schedules):
    # 1. 篩選目標車輛資料
    plate_gps = [log for log in gps_logs if log["plate_number"] == target_plate]
    if not plate_gps:
        print(f"找不到車牌 {target_plate} 的 GPS 資料。")
        return

    # 2. 按日期分組 (台灣時間)
    gps_by_date = {}
    for log in plate_gps:
        try:
            ts = log["recorded_at"].replace(" ", "T")
            if "+" in ts:
                ts = ts.split("+")[0] + "Z"
            utc_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            tw_dt = utc_dt + timedelta(hours=8)
            log["recorded_at_tw"] = tw_dt
            
            date_str = tw_dt.strftime("%Y-%m-%d")
            if date_str not in gps_by_date:
                gps_by_date[date_str] = []
            gps_by_date[date_str].append(log)
        except Exception as e:
            print(f"解析時間錯誤: {log['recorded_at']} -> {e}")

    # 3. 逐日分析
    for date_str in sorted(gps_by_date.keys()):
        print(f"\n==================================================")
        print(f"分析日期: {date_str}  |  車牌: {target_plate}")
        print(f"==================================================")
        
        day_gps = gps_by_date[date_str]
        day_gps.sort(key=lambda x: x["recorded_at_tw"])

        # 過濾原地中退點 (與上一點位置差異極小)
        filtered_gps = []
        stationary_count = 0
        last_lat, last_lon = None, None
        for row in day_gps:
            curr_lat = row.get("lat")
            curr_lon = row.get("lon")
            if last_lat is not None and last_lon is not None:
                if abs(curr_lat - last_lat) < 0.0001 and abs(curr_lon - last_lon) < 0.0001:
                    stationary_count += 1
                    continue
            filtered_gps.append(row)
            last_lat, last_lon = curr_lat, curr_lon
        
        day_gps = filtered_gps
        print(f"GPS 點數: {len(day_gps)} (已過濾原地中退點: {stationary_count} 點)")

        # 追蹤 transition 狀態
        # 預設前一筆狀態為 False
        prev_operating = False
        transitions = []

        for i, row in enumerate(day_gps):
            curr_operating = row.get("is_operating", False)
            route_name = row.get("route_name", "")
            tw_time = row["recorded_at_tw"]

            # 檢測狀態移轉
            if not prev_operating and curr_operating:
                # False -> True: 開班 (Start)
                matched_dt, matched_str = find_closest_schedule_time(route_name, tw_time, schedules)
                transitions.append({
                    "type": "開班 (Start)",
                    "gps_time": tw_time,
                    "route": route_name,
                    "matched_time": matched_str,
                    "matched_dt": matched_dt,
                    "speed": row.get("speed", 0)
                })
            elif prev_operating and not curr_operating:
                # True -> False: 收班 (End)
                matched_dt, matched_str = find_closest_schedule_time(route_name, tw_time, schedules)
                transitions.append({
                    "type": "收班 (End)",
                    "gps_time": tw_time,
                    "route": route_name,
                    "matched_time": matched_str,
                    "matched_dt": matched_dt,
                    "speed": row.get("speed", 0)
                })
            
            prev_operating = curr_operating

        # 4. 輸出狀態移轉紀錄
        print("\n【狀態移轉與班表匹配明細】")
        for idx, t in enumerate(transitions):
            gps_str = t["gps_time"].strftime("%H:%M:%S")
            print(f"[{idx+1}] {t['type']} | 路線: {t['route']:<4} | GPS時間: {gps_str} | 匹配標準時間: {t['matched_time']}")
        
        # 如果最後狀態是營運中，補印一個持續中說明
        ongoing_trip = None
        if prev_operating and len(day_gps) > 0:
            # 尋找最後一個開班事件作為起點
            last_start = None
            for t in reversed(transitions):
                if t["type"] == "開班 (Start)":
                    last_start = t
                    break
            if last_start:
                ongoing_trip = last_start
                print(f"[*] 營運持續中... | 路線: {last_start['route']:<4} | GPS開班時間: {last_start['gps_time'].strftime('%H:%M:%S')} | 匹配開班時間: {last_start['matched_time']}")

        # 5. 組合成完整的「趟 (Trips)」與「中退時間 (Breaks)」
        trips = []
        current_trip = None
        
        for t in transitions:
            if t["type"] == "開班 (Start)":
                if current_trip is not None:
                    # 避免連續開班
                    trips.append(current_trip)
                current_trip = {
                    "start": t,
                    "end": None
                }
            elif t["type"] == "收班 (End)":
                if current_trip is not None:
                    current_trip["end"] = t
                    trips.append(current_trip)
                    current_trip = None
                else:
                    # 無開班的收班（單獨收班）
                    trips.append({
                        "start": None,
                        "end": t
                    })

        # 計算中退時間
        breaks = []
        for i in range(len(trips) - 1):
            prev_trip = trips[i]
            next_trip = trips[i+1]
            
            if prev_trip["end"] and next_trip["start"]:
                end_dt = prev_trip["end"]["matched_dt"]
                start_dt = next_trip["start"]["matched_dt"]
                
                if end_dt and start_dt:
                    duration_mins = int((start_dt - end_dt).total_seconds() / 60)
                    breaks.append({
                        "start_time": prev_trip["end"]["matched_time"],
                        "end_time": next_trip["start"]["matched_time"],
                        "duration_mins": duration_mins
                    })
        
        # 若最後有一趟已結束的趟次，且後續有未完結的趟次，亦計算其間的間隔為中退
        if trips and trips[-1]["end"] and ongoing_trip:
            end_dt = trips[-1]["end"]["matched_dt"]
            start_dt = ongoing_trip["matched_dt"]
            if end_dt and start_dt:
                duration_mins = int((start_dt - end_dt).total_seconds() / 60)
                breaks.append({
                    "start_time": trips[-1]["end"]["matched_time"],
                    "end_time": ongoing_trip["matched_time"],
                    "duration_mins": duration_mins
                })

        # 6. 列印當日每趟完整開/收班/中退時間
        print("\n【當日營運趟次與中退時間總覽】")
        
        print("\n--- 完整營運趟次 ---")
        if not trips:
            print("當天無已完結的完整營運趟次。")
        else:
            for idx, trip in enumerate(trips):
                start = trip["start"]
                end = trip["end"]
                
                start_str = start["matched_time"] if start else "未知"
                end_str = end["matched_time"] if end else "未收班"
                route_str = start["route"] if start else (end["route"] if end else "未知")
                
                gps_start_str = start["gps_time"].strftime("%H:%M:%S") if start else "未知"
                gps_end_str = end["gps_time"].strftime("%H:%M:%S") if end else "未知"
                
                # 計算趟次持續時間
                duration_str = "無法計算"
                if start and end and start["matched_dt"] and end["matched_dt"]:
                    dur_secs = (end["matched_dt"] - start["matched_dt"]).total_seconds()
                    if dur_secs >= 0:
                        dur_mins = int(dur_secs / 60)
                        duration_str = f"{dur_mins} 分鐘"
                    else:
                        duration_str = "時間異常(收班早於開班)"
                
                print(f"趟次 {idx+1} | 路線: {route_str:<4} | 開班: {start_str:<8} (GPS: {gps_start_str}) | 收班: {end_str:<8} (GPS: {gps_end_str}) | 持續: {duration_str}")

        if ongoing_trip:
            print("\n--- 未完結營運趟次 ---")
            gps_start_str = ongoing_trip["gps_time"].strftime("%H:%M:%S")
            print(f"持續趟 | 路線: {ongoing_trip['route']:<4} | 開班: {ongoing_trip['matched_time']:<8} (GPS: {gps_start_str}) | 收班: 未完結/營運中")

        print("\n--- 中退時間 ---")
        if breaks:
            for idx, brk in enumerate(breaks):
                print(f"中退 {idx+1} | 時間: {brk['start_time']} ~ {brk['end_time']} | 持續時間: {brk['duration_mins']} 分鐘")
        else:
            print("當天無中退時間。")

def main():
    # 取得本指令碼所在之目錄，使程式在任何工作目錄執行皆能正確找到 JSON 檔案
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gps_file = os.path.join(script_dir, "tainan_0515.json")
    schedule_file = os.path.join(script_dir, "route_chedules.json")
    
    if not os.path.exists(gps_file):
        print(f"找不到檔案: {gps_file}")
        return
    if not os.path.exists(schedule_file):
        print(f"找不到檔案: {schedule_file}")
        return
        
    print(f"載入 GPS 資料: {gps_file}...")
    with open(gps_file, "r", encoding="utf-8") as f:
        gps_logs = json.load(f)
        
    print(f"載入路線時刻表: {schedule_file}...")
    with open(schedule_file, "r", encoding="utf-8") as f:
        schedules = json.load(f)

    target_plate = "EAA-779"
    analyze_bus_transitions(target_plate, gps_logs, schedules)

if __name__ == "__main__":
    main()
