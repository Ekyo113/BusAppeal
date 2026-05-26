import sys
import os

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from export_service import ExportService

# Mock data
reports = [
    # Some completed in 2026-05
    {"completed_at": "2026-05-10T12:00:00", "vendor_name": "高雄客運", "component": "冷氣", "solution_type": "維修", "car_number": "EAA-779", "description": "冷氣冷媒不足且管線出風不冷", "mileage": ""},
    {"completed_at": "2026-05-11T12:00:00", "vendor_name": "高雄客運", "component": "冷氣", "solution_type": "維修", "car_number": "EAA-779", "description": "冷氣出風不冷", "mileage": None},
    {"completed_at": "2026-05-12T12:00:00", "vendor_name": "高雄客運", "component": "TMS", "solution_type": "更換", "car_number": "EAA-780", "description": "TMS訊號模組無法連線", "mileage": 12500.5},
    {"completed_at": "2026-05-12T13:00:00", "vendor_name": "港都客運", "component": "BMS", "solution_type": "售服", "car_number": "EAA-801", "description": "BMS電池組單體電壓不平衡", "mileage": "45200"},
    {"completed_at": "2026-05-13T12:00:00", "vendor_name": "港都客運", "component": "BMS", "solution_type": "售服", "car_number": "EAA-801", "description": "BMS電池組單體電壓不平衡"},
    
    # Design modifications this month (qualifying count >= 5)
    {"completed_at": "2026-05-14T10:00:00", "vendor_name": "高雄客運", "solution_type": "設計修改", "solution": "加強型冷氣支架", "car_number": "EAA-779", "description": "冷氣支架結構加強施工"},
    {"completed_at": "2026-05-15T10:00:00", "vendor_name": "高雄客運", "solution_type": "設計修改", "solution": "加強型冷氣支架", "car_number": "EAA-780", "description": "冷氣支架結構加強施工"},
    {"completed_at": "2026-05-16T10:00:00", "vendor_name": "港都客運", "solution_type": "設計修改", "solution": "加強型冷氣支架", "car_number": "EAA-801", "description": "冷氣支架結構加強施工"},
    {"completed_at": "2026-05-17T10:00:00", "vendor_name": "港都客運", "solution_type": "設計修改", "solution": "加強型冷氣支架", "car_number": "EAA-802", "description": "冷氣支架結構加強施工"},
    {"completed_at": "2026-05-18T10:00:00", "vendor_name": "統聯客運", "solution_type": "設計修改", "solution": "加強型冷氣支架", "car_number": "EAA-905", "description": "冷氣支架結構加強施工"},
    
    # Another design modification this month (now >= 5 times to qualify)
    {"completed_at": "2026-05-14T10:00:00", "vendor_name": "高雄客運", "solution_type": "設計修改", "solution": "電池防護板優化", "car_number": "EAA-779", "description": "電池防護板加強防護施工"},
    {"completed_at": "2026-05-15T10:00:00", "vendor_name": "高雄客運", "solution_type": "設計修改", "solution": "電池防護板優化", "car_number": "EAA-780", "description": "電池防護板加強防護施工"},
    {"completed_at": "2026-05-16T10:00:00", "vendor_name": "港都客運", "solution_type": "設計修改", "solution": "電池防護板優化", "car_number": "EAA-801", "description": "電池防護板加強防護施工"},
    {"completed_at": "2026-05-17T10:00:00", "vendor_name": "港都客運", "solution_type": "設計修改", "solution": "電池防護板優化", "car_number": "EAA-802", "description": "電池防護板加強防護施工"},
    {"completed_at": "2026-05-18T10:00:00", "vendor_name": "統聯客運", "solution_type": "設計修改", "solution": "電池防護板優化", "car_number": "EAA-905", "description": "電池防護板加強防護施工"},
    
    # Older reports (historical) for monthly trend
    {"completed_at": "2026-01-10T12:00:00", "vendor_name": "高雄客運", "component": "冷氣", "solution_type": "維修", "car_number": "EAA-779", "description": "冷氣風扇故障"},
    {"completed_at": "2026-02-10T12:00:00", "vendor_name": "高雄客運", "component": "冷氣", "solution_type": "維修", "car_number": "EAA-779", "description": "冷氣風扇故障"},
    {"completed_at": "2026-03-10T12:00:00", "vendor_name": "高雄客運", "component": "冷氣", "solution_type": "維修", "car_number": "EAA-779", "description": "冷氣風扇故障"},
    {"completed_at": "2026-04-10T12:00:00", "vendor_name": "高雄客運", "component": "冷氣", "solution_type": "維修", "car_number": "EAA-779", "description": "冷氣風扇故障"},
]

all_time_design_reports = [
    # historical completions
    {"completed_at": "2026-04-05T12:00:00", "car_number": "EAA-779", "solution_type": "設計修改", "solution": "加強型冷氣支架"},
    {"completed_at": "2026-05-15T12:00:00", "car_number": "EAA-780", "solution_type": "設計修改", "solution": "加強型冷氣支架"},
    {"completed_at": "2026-05-16T12:00:00", "car_number": "EAA-801", "solution_type": "設計修改", "solution": "加強型冷氣支架"},
    {"completed_at": "2026-05-17T12:00:00", "car_number": "EAA-802", "solution_type": "設計修改", "solution": "加強型冷氣支架"},
    {"completed_at": "2026-05-18T12:00:00", "car_number": "EAA-905", "solution_type": "設計修改", "solution": "加強型冷氣支架"},
    
    # historical completions for Battery shield
    {"completed_at": "2026-05-14T12:00:00", "car_number": "EAA-779", "solution_type": "設計修改", "solution": "電池防護板優化"},
    {"completed_at": "2026-05-15T12:00:00", "car_number": "EAA-780", "solution_type": "設計修改", "solution": "電池防護板優化"},
    {"completed_at": "2026-05-16T12:00:00", "car_number": "EAA-801", "solution_type": "設計修改", "solution": "電池防護板優化"},
    {"completed_at": "2026-05-17T12:00:00", "car_number": "EAA-802", "solution_type": "設計修改", "solution": "電池防護板優化"},
    {"completed_at": "2026-05-18T12:00:00", "car_number": "EAA-905", "solution_type": "設計修改", "solution": "電池防護板優化"},
]

monitored_buses = [
    {"plate_number": "EAA-779", "vendor_name": "高雄客運"},
    {"plate_number": "EAA-780", "vendor_name": "高雄客運"},
    {"plate_number": "EAA-801", "vendor_name": "港都客運"},
    {"plate_number": "EAA-802", "vendor_name": "港都客運"},
    {"plate_number": "EAA-901", "vendor_name": "統聯客運"},
    {"plate_number": "EAA-905", "vendor_name": "統聯客運"},
]

try:
    print("Generating monthly PDF report...")
    selected_design_sols = ["加強型冷氣支架", "超薄型前擋泥板防噴優化方案"]
    
    # 增加測試資料：額外選取的方案的歷史完成記錄，驗證是否顯示打勾與日期
    all_time_design_reports.append({"completed_at": "2026-05-20T12:00:00", "car_number": "EAA-901", "solution_type": "設計修改", "solution": "超薄型前擋泥板防噴優化方案"})
    all_time_design_reports.append({"completed_at": "2026-05-22T12:00:00", "car_number": "EAA-905", "solution_type": "設計修改", "solution": "超薄型前擋泥板防噴優化方案"})

    pdf_buffer = ExportService.generate_monthly_report_pdf(
        reports, "2026-05", "2026-01-01", "2026-05-31",
        all_time_design_reports=all_time_design_reports,
        monitored_buses=monitored_buses,
        selected_design_sols=selected_design_sols
    )
    
    # Save buffer to a local file
    output_path = os.path.join(os.path.dirname(__file__), "test_monthly_report.pdf")
    with open(output_path, "wb") as f:
        f.write(pdf_buffer.read())
        
    print(f"Successfully generated PDF: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
