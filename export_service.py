from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.units import cm
from io import BytesIO
from datetime import datetime

class ExportService:
    @staticmethod
    def setup_font():
        """註冊中文字體 (使用 CID 字體 STSong-Light，不需字體檔)"""
        try:
            pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
            return 'STSong-Light'
        except:
            return 'Helvetica'

    @staticmethod
    @staticmethod
    def generate_pdf(reports, export_type: str, content_field: str = "solution"):
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        font_name = ExportService.setup_font()
        
        if export_type == 'report':
            ExportService._draw_report_pdf(c, reports, font_name, width, height, content_field)
        else:
            ExportService._draw_replacement_pdf(c, reports, font_name, width, height, content_field)
            
        c.save()
        buffer.seek(0)
        return buffer

    @staticmethod
    def _draw_report_pdf(c, reports, font, width, height, content_field: str = "solution"):
        """通報紀錄：一頁一筆"""
        for r in reports:
            # 標題
            c.setFont(font, 18)
            c.drawCentredString(width/2, height - 2*cm, f"公車維修通報紀錄單")
            
            # 基本資訊區
            c.setFont(font, 12)
            y = height - 4*cm
            c.drawString(2*cm, y, f"客運公司：{r.get('vendor_name', '-')}")
            c.drawString(10*cm, y, f"車號：{r.get('car_number', '-')}")
            
            y -= 0.8*cm
            c.drawString(2*cm, y, f"完成時間：{r.get('completed_at', '-')[:16].replace('T', ' ') if r.get('completed_at') else '-'}")
            c.drawString(10*cm, y, f"處理人員：{r.get('handler_name', '-')}")

            y -= 0.8*cm
            c.drawString(2*cm, y, f"目前里程：{r.get('mileage', '-') or '-'} KM")
            
            # 分隔線
            y -= 0.5*cm
            c.line(2*cm, y, width - 2*cm, y)
            
            # 問題描述
            y -= 1*cm
            c.setFont(font, 14)
            c.drawString(2*cm, y, "【問題描述】")
            y -= 0.8*cm
            c.setFont(font, 11)
            desc = r.get('description', '')
            text_obj = c.beginText(2.5*cm, y)
            text_obj.setFont(font, 11)
            for line in ExportService._wrap_text(desc, 40):
                text_obj.textLine(line)
            c.drawText(text_obj)
            
            # 內容 (處理方案 or 通報回覆)
            y -= 4*cm
            c.setFont(font, 14)
            if content_field == "reply":
                c.drawString(2*cm, y, "【通報回覆】")
                y -= 0.8*cm
                c.setFont(font, 11)
                reply_val = r.get('reply') or r.get('solution') or ''
            else:
                c.drawString(2*cm, y, "【處理方案】")
                y -= 0.8*cm
                c.setFont(font, 11)
                reply_val = r.get('solution') or ''
                
            text_obj = c.beginText(2.5*cm, y)
            text_obj.setFont(font, 11)
            for line in ExportService._wrap_text(reply_val, 40):
                text_obj.textLine(line)
            c.drawText(text_obj)
            
            # 底部空白預留線
            y = 8*cm
            c.setDash(1, 2)
            c.line(2*cm, y, width - 2*cm, y)
            c.setFont(font, 10)
            c.drawString(2*cm, y - 0.5*cm, "( 以下為預留空白處，供新增資訊 or 核章使用 )")
            
            c.showPage() # 換頁

    @staticmethod
    def _draw_replacement_pdf(c, reports, font, width, height, content_field: str = "solution"):
        """換件紀錄：清單式"""
        c.setFont(font, 18)
        c.drawCentredString(width/2, height - 2*cm, f"公車零件更換紀錄表")
        
        y = height - 4*cm
        c.setFont(font, 10)
        
        header_content = "通報回覆" if content_field == "reply" else "更換零件"
        headers = ["日期", "客運", "車號", header_content, "里程", "人員"]
        widths = [3*cm, 3*cm, 3*cm, 6*cm, 2.5*cm, 2*cm]
        
        # 畫表頭
        x = 1*cm
        for i, h in enumerate(headers):
            c.drawString(x, y, h)
            x += widths[i]
        
        y -= 0.3*cm
        c.line(1*cm, y, width - 1*cm, y)
        y -= 0.6*cm
        
        for r in reports:
            if y < 2*cm: # 換頁檢查
                c.showPage()
                y = height - 2*cm
                c.setFont(font, 10)
            
            x = 1*cm
            date_str = r.get('completed_at', '')[:10]
            c.drawString(x, y, date_str)
            x += widths[0]
            c.drawString(x, y, r.get('vendor_name', '-')[:6])
            x += widths[1]
            c.drawString(x, y, r.get('car_number', '-'))
            x += widths[2]
            
            content_val = r.get('reply') if content_field == 'reply' else r.get('solution')
            if not content_val:
                content_val = r.get('solution') or '-'
            c.drawString(x, y, str(content_val)[:15])
            
            x += widths[3]
            c.drawString(x, y, str(r.get('mileage', '-') or '-'))
            x += widths[4]
            c.drawString(x, y, r.get('handler_name', '-')[:5])
            
            y -= 0.8*cm
            c.setDash(1, 1)
            c.line(1*cm, y + 0.2*cm, width - 1*cm, y + 0.2*cm)
            c.setDash(1, 0) # 恢復實線

    @staticmethod
    def _wrap_text(text, limit):
        """簡單的文字換行處理"""
        if not text: return ["-"]
        lines = []
        for i in range(0, len(text), limit):
            lines.append(text[i:i+limit])
        return lines

    @staticmethod
    def generate_excel(reports, content_field="solution"):
        """產生 Excel XLSX 檔案，若未安裝 openpyxl 則自動降級為帶有 UTF-8 BOM 的 CSV 檔案"""
        # 依日期由遠到近（建立/完成時間遞增）排序
        reports = sorted(reports, key=lambda r: r.get('completed_at') or r.get('created_at') or '')
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "維修通報紀錄"
            
            font_header = Font(name="微軟正黑體", size=11, bold=True, color="FFFFFF")
            font_body = Font(name="微軟正黑體", size=10)
            fill_header = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
            align_center = Alignment(horizontal="center", vertical="center")
            align_left = Alignment(horizontal="left", vertical="center")
            
            thin_border = Border(
                left=Side(style='thin', color='DDDDDD'),
                right=Side(style='thin', color='DDDDDD'),
                top=Side(style='thin', color='DDDDDD'),
                bottom=Side(style='thin', color='DDDDDD')
            )
            
            content_header = "內容(通報回覆)" if content_field == "reply" else "內容(處理方案)"
            # Order: 客運商/問題描述/車號/處理人/完成日(年-月-日)/里程/類型/內容
            headers = ["客運商", "問題描述", "車號", "處理人", "完成日(年-月-日)", "里程", "類型", content_header]
            ws.append(headers)
            
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.font = font_header
                cell.fill = fill_header
                cell.alignment = align_center
                cell.border = thin_border
                
            for r in reports:
                completed_at = r.get('completed_at', '')
                if completed_at:
                    completed_at = completed_at[:10] # 年-月-日
                
                content_val = r.get('reply') if content_field == 'reply' else r.get('solution')
                if not content_val:
                    content_val = r.get('solution') or '-'
                    
                row_data = [
                    r.get('vendor_name', '-'),
                    r.get('description', '-'),
                    r.get('car_number', '-'),
                    r.get('handler_name', '-'),
                    completed_at or '-',
                    r.get('mileage', '-') or '-',
                    r.get('solution_type', '-'),
                    content_val
                ]
                ws.append(row_data)
                
            for row_idx in range(2, len(reports) + 2):
                for col_idx in range(1, len(headers) + 1):
                    cell = ws.cell(row=row_idx, column=col_idx)
                    cell.font = font_body
                    cell.border = thin_border
                    # Align: 1,3,4,5,6,7 center; 2,8 left
                    if col_idx in [1, 3, 4, 5, 6, 7]:
                        cell.alignment = align_center
                    else:
                        cell.alignment = align_left
                        
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    val_str = str(cell.value or '')
                    val_len = sum(2 if ord(char) > 127 else 1 for char in val_str)
                    if val_len > max_len:
                        max_len = val_len
                ws.column_dimensions[col_letter].width = max(max_len + 3, 10)
                
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            return buffer
        except ImportError:
            # Fallback to UTF-8 BOM CSV
            import csv
            from io import StringIO
            
            buffer = BytesIO()
            buffer.write(b'\xef\xbb\xbf') # BOM for Excel
            
            text_buffer = StringIO()
            writer = csv.writer(text_buffer)
            
            content_header = "內容(通報回覆)" if content_field == "reply" else "內容(處理方案)"
            writer.writerow(["客運商", "問題描述", "車號", "處理人", "完成日(年-月-日)", "里程", "類型", content_header])
            
            for r in reports:
                completed_at = r.get('completed_at', '')
                if completed_at:
                    completed_at = completed_at[:10]
                    
                content_val = r.get('reply') if content_field == 'reply' else r.get('solution')
                if not content_val:
                    content_val = r.get('solution') or '-'
                    
                writer.writerow([
                    r.get('vendor_name', '-'),
                    r.get('description', '-'),
                    r.get('car_number', '-'),
                    r.get('handler_name', '-'),
                    completed_at or '-',
                    r.get('mileage', '-') or '-',
                    r.get('solution_type', '-'),
                    content_val
                ])
                
            buffer.write(text_buffer.getvalue().encode('utf-8'))
            buffer.seek(0)
            return buffer

    @staticmethod
    def setup_matplotlib_font():
        """設定 Matplotlib 中文字型，若無字型則下載 Noto Sans TC"""
        import os
        import urllib.request
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        os.makedirs(static_dir, exist_ok=True)
        font_path = os.path.join(static_dir, "NotoSansTC-Regular.ttf")
        
        if not os.path.exists(font_path):
            print("NotoSansTC-Regular.ttf not found. Downloading from Google Fonts CJK/g0v mirror...")
            try:
                url = "https://raw.githubusercontent.com/g0v/ogp-commitments/main/NotoSansTC-Regular.ttf"
                headers = {'User-Agent': 'Mozilla/5.0'}
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req) as response, open(font_path, 'wb') as out_file:
                    out_file.write(response.read())
                print("Download completed successfully.")
            except Exception as e:
                print(f"Failed to download font: {e}")
                
        if os.path.exists(font_path):
            try:
                fm.fontManager.addfont(font_path)
                plt.rcParams['font.sans-serif'] = ['Noto Sans TC']
                plt.rcParams['axes.unicode_minus'] = False
            except Exception as e:
                print(f"Failed to add font to matplotlib: {e}")

    @staticmethod
    def generate_monthly_report_pdf(reports, month: str, start_date: str, end_date: str):
        import os
        import io
        from datetime import datetime, timedelta
        import matplotlib.pyplot as plt
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        font_name = ExportService.setup_font()
        
        # Parse month number
        try:
            target_year, target_month_num = map(int, month.split("-"))
        except ValueError:
            target_year, target_month_num = datetime.now().year, datetime.now().month

        # 1. Page 1: Cover
        c.setFont(font_name, 24)
        c.drawCentredString(width/2, height/2 + 50, f"({target_month_num}月)市場組維修報表")
        
        c.setFont(font_name, 12)
        c.drawCentredString(width/2, height/2 - 10, f"產出日期：{datetime.now().strftime('%Y-%m-%d')}")
        c.showPage()
        
        # 2. Setup Matplotlib Font
        ExportService.setup_matplotlib_font()
        
        # 3. Compile Monthly trend statistics (Jan to target_month_num)
        months_list = [f"{target_year}-{m:02d}" for m in range(1, target_month_num + 1)]
        months_display = [f"{m}月" for m in range(1, target_month_num + 1)]
        
        quality_counts = {m: 0 for m in months_list}
        all_counts = {m: 0 for m in months_list}
        
        for r in reports:
            comp_at = r.get('completed_at', '')
            if not comp_at:
                continue
            r_month = comp_at[:7] # YYYY-MM
            if r_month in quality_counts:
                all_counts[r_month] += 1
                if r.get('solution_type') in ['維修', '更換', '售服']:
                    quality_counts[r_month] += 1
                    
        quality_monthly = [quality_counts[m] for m in months_list]
        all_monthly = [all_counts[m] for m in months_list]
        
        quality_cumulative = []
        acc_q = 0
        for val in quality_monthly:
            acc_q += val
            quality_cumulative.append(acc_q)
            
        all_cumulative = []
        acc_a = 0
        for val in all_monthly:
            acc_a += val
            all_cumulative.append(acc_a)

        # Plot Page 1 Charts
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2), dpi=150)
        x = range(len(months_display))
        
        # Left Subplot: Quality
        ax1.bar(x, quality_monthly, color='#3b82f6', width=0.4, label='當月完成')
        ax1.set_ylabel('當月完成數量 (件)', color='#3b82f6', fontsize=9)
        ax1.tick_params(axis='y', labelcolor='#3b82f6', labelsize=8)
        ax1.set_xticks(x)
        ax1.set_xticklabels(months_display, fontsize=8)
        ax1.grid(True, axis='y', linestyle='--', alpha=0.5)
        
        ax1_twin = ax1.twinx()
        ax1_twin.plot(x, quality_cumulative, color='#f59e0b', marker='o', linewidth=2, label='累計完成')
        ax1_twin.set_ylabel('累計完成數量 (件)', color='#f59e0b', fontsize=9)
        ax1_twin.tick_params(axis='y', labelcolor='#f59e0b', labelsize=8)
        
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_twin.get_legend_handles_labels()
        ax1.legend(lines + lines2, labels + labels2, loc='upper left', fontsize=8)
        ax1.set_title("每月品情(維修+更換+售服)統計趨勢", fontsize=10, fontweight='bold', pad=10)
        
        # Right Subplot: All Types
        ax2.bar(x, all_monthly, color='#10b981', width=0.4, label='當月完成')
        ax2.set_ylabel('當月完成數量 (件)', color='#10b981', fontsize=9)
        ax2.tick_params(axis='y', labelcolor='#10b981', labelsize=8)
        ax2.set_xticks(x)
        ax2.set_xticklabels(months_display, fontsize=8)
        ax2.grid(True, axis='y', linestyle='--', alpha=0.5)
        
        ax2_twin = ax2.twinx()
        ax2_twin.plot(x, all_cumulative, color='#ef4444', marker='s', linewidth=2, label='累計完成')
        ax2_twin.set_ylabel('累計完成數量 (件)', color='#ef4444', fontsize=9)
        ax2_twin.tick_params(axis='y', labelcolor='#ef4444', labelsize=8)
        
        lines, labels = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper left', fontsize=8)
        ax2.set_title("每月所有類型完成統計趨勢", fontsize=10, fontweight='bold', pad=10)
        
        fig.tight_layout()
        page1_img_buf = io.BytesIO()
        plt.savefig(page1_img_buf, format='png', bbox_inches='tight')
        plt.close(fig)
        page1_img_buf.seek(0)
        
        # Draw Page 1 in PDF
        c.setFont(font_name, 16)
        c.drawString(40, height - 40, "一、 每月維修統計趨勢")
        c.drawImage(ImageReader(page1_img_buf), 30, 480, width=535, height=250)
        
        # 繪製當月及累計數量表格
        table_y = 420
        row_height = 20
        col_widths = [80, 130, 90, 90, 90]  # 總寬度 = 480
        start_x = (width - 480) / 2 # 置中
        
        # 繪製表頭背景
        c.setFillColorRGB(0.92, 0.94, 0.98) # 淺藍色背景
        c.rect(start_x, table_y, 480, row_height, fill=True, stroke=False)
        c.setFillColorRGB(0, 0, 0)
        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.setLineWidth(0.5)
        c.line(start_x, table_y, start_x + 480, table_y)
        c.line(start_x, table_y + row_height, start_x + 480, table_y + row_height)
        
        headers = ["月份", "品情當月", "品情累計", "所有當月", "所有累計"]
        curr_x = start_x
        c.setFont(font_name, 9)
        for i, h in enumerate(headers):
            c.drawCentredString(curr_x + col_widths[i]/2, table_y + 5, h)
            curr_x += col_widths[i]
            if i < len(headers) - 1:
                c.line(curr_x, table_y, curr_x, table_y + row_height)
                
        # 繪製資料列
        for idx, m_disp in enumerate(months_display):
            table_y -= row_height
            c.line(start_x, table_y, start_x + 480, table_y)
            
            q_m = quality_monthly[idx]
            q_c = quality_cumulative[idx]
            a_m = all_monthly[idx]
            a_c = all_cumulative[idx]
            
            curr_x = start_x
            row_data = [m_disp, f"{q_m} 件", f"{q_c} 件", f"{a_m} 件", f"{a_c} 件"]
            for i, val in enumerate(row_data):
                c.drawCentredString(curr_x + col_widths[i]/2, table_y + 5, val)
                curr_x += col_widths[i]
                if i < len(headers) - 1:
                    c.line(curr_x, table_y, curr_x, table_y + row_height)
                    
        # 繪製外框左右兩邊的垂直線
        c.line(start_x, table_y, start_x, 420 + row_height)
        c.line(start_x + 480, table_y, start_x + 480, 420 + row_height)
        
        c.showPage()
        
        # 4. Page 2: Operator & Component breakdown
        month_reports = [r for r in reports if r.get('completed_at', '').startswith(month)]
        components_list = ["TMS", "動力", "BMS", "冷氣", "電子影像", "方向燈座", "車門", "車裝", "車體外裝", "燈光", "底盤件", "儀錶", "其他", "未分類"]
        component_colors = {
            "TMS": '#3b82f6',
            "動力": '#f59e0b',
            "BMS": '#10b981',
            "冷氣": '#0ea5e9',
            "電子影像": '#d946ef',
            "方向燈座": '#ec4899',
            "車門": '#8b5cf6',
            "車裝": '#06b6d4',
            "車體外裝": '#84cc16',
            "燈光": '#ef4444',
            "底盤件": '#14b8a6',
            "儀錶": '#f97316',
            "其他": '#6b7280',
            "未分類": '#9ca3af'
        }
        
        def compute_and_plot_page2_row(row_reports, title_text):
            vendor_stats = {}
            component_totals = {c: 0 for c in components_list}
            
            for r in row_reports:
                vendor = r.get('vendor_name', '未知客運') or '未知客運'
                comp = (r.get('component') or '').strip()
                if not comp:
                    comp = '未分類'
                elif comp not in components_list:
                    comp = '其他'
                    
                if vendor not in vendor_stats:
                    vendor_stats[vendor] = {c: 0 for c in components_list}
                vendor_stats[vendor][comp] += 1
                component_totals[comp] += 1
                
            vendor_totals = {v: sum(comps.values()) for v, comps in vendor_stats.items()}
            sorted_vendors = sorted(vendor_totals.items(), key=lambda x: x[1], reverse=True)
            # 為了讓數量最多的客運商顯示在長條圖的最上方(Matplotlib 預設 y=0 在最下方)，我們將 operators 反轉
            operators = [item[0] for item in sorted_vendors]
            operators.reverse()
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 2.5), dpi=150)
            
            # Left Subplot
            if not operators:
                ax1.text(0.5, 0.5, '當月無資料', ha='center', va='center', fontsize=9)
                ax1.set_axis_off()
            else:
                y_pos = range(len(operators))
                left_accum = [0] * len(operators)
                for comp in components_list:
                    comp_data = [vendor_stats[op][comp] for op in operators]
                    if sum(comp_data) > 0:
                        ax1.barh(y_pos, comp_data, left=left_accum, label=comp, color=component_colors.get(comp, '#9ca3af'), height=0.55)
                        for i in range(len(operators)):
                            left_accum[i] += comp_data[i]
                # 在各客運商長條圖末端顯示當月總件數
                for i, op in enumerate(operators):
                    total_val = vendor_totals[op]
                    ax1.text(total_val + 0.1, i, f"{total_val}", va='center', ha='left', fontsize=7, fontweight='bold')
                ax1.set_yticks(y_pos)
                ax1.set_yticklabels(operators, fontsize=8)
                ax1.set_xlabel('件數', fontsize=8)
                ax1.tick_params(axis='x', labelsize=8)
                ax1.set_title('各客運商部件件數統計', fontsize=9, fontweight='bold')
                ax1.legend(loc='upper right', fontsize=6, ncol=2, framealpha=0.5)
                
            # Right Subplot
            active_components = {k: v for k, v in component_totals.items() if v > 0}
            if not active_components:
                ax2.text(0.5, 0.5, '當月無資料', ha='center', va='center', fontsize=9)
                ax2.set_axis_off()
            else:
                sorted_comps = sorted(active_components.items(), key=lambda x: x[1])
                comp_names = [item[0] for item in sorted_comps]
                comp_values = [item[1] for item in sorted_comps]
                colors = [component_colors.get(c, '#9ca3af') for c in comp_names]
                
                y_pos = range(len(comp_names))
                ax2.barh(y_pos, comp_values, color=colors, height=0.55)
                ax2.set_yticks(y_pos)
                ax2.set_yticklabels(comp_names, fontsize=8)
                ax2.set_xlabel('累積數量 (件)', fontsize=8)
                ax2.tick_params(axis='x', labelsize=8)
                ax2.set_title('部件累計數量統計', fontsize=9, fontweight='bold')
                for i, val in enumerate(comp_values):
                    ax2.text(val + 0.1, i, f"{val}", va='center', fontsize=7, fontweight='bold')
                    
            fig.suptitle(title_text, fontsize=10, fontweight='bold', y=0.98)
            fig.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return buf

        # Generate the three rows
        row1_reports = month_reports
        row2_reports = [r for r in month_reports if r.get('solution_type') in ['更換', '維修', '售服']]
        row3_reports = [r for r in month_reports if r.get('solution_type') == '設計修改']
        
        row1_img_buf = compute_and_plot_page2_row(row1_reports, "【全部類型圖表】")
        row2_img_buf = compute_and_plot_page2_row(row2_reports, "【品情 (更換 + 維修 + 售服) 圖表】")
        row3_img_buf = compute_and_plot_page2_row(row3_reports, "【設計修改圖表】")
        
        # Draw Page 2 in PDF
        c.setFont(font_name, 16)
        c.drawString(40, height - 40, "二、 各客運商與部件統計分析")
        
        c.drawImage(ImageReader(row1_img_buf), 30, 560, width=535, height=190)
        c.drawImage(ImageReader(row2_img_buf), 30, 320, width=535, height=190)
        c.drawImage(ImageReader(row3_img_buf), 30, 80, width=535, height=190)
        
        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

