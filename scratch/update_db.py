import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database

def main():
    try:
        client = Database.get_client()
        print("Updating '方向燈座' to '方向燈座及撥桿'...")
        res = client.table('reports').update({'component': '方向燈座及撥桿'}).eq('component', '方向燈座').execute()
        print(f"Updated component name: {len(res.data)} records.")
        
        print("Updating AA to '維修前艙蓋補膠'...")
        res_aa = client.table('reports').update({'solution': '維修前艙蓋補膠'}).eq('solution', 'AA').execute()
        print(f"Updated AA: {len(res_aa.data)} records.")
        
        print("Updating AB to '已完成'...")
        res_ab = client.table('reports').update({'status': '已完成'}).eq('status', 'AB').execute()
        print(f"Updated AB: {len(res_ab.data)} records.")
        
        print("Updating AC to '設計修改'...")
        res_ac = client.table('reports').update({'solution_type': '設計修改'}).eq('solution_type', 'AC').execute()
        print(f"Updated AC: {len(res_ac.data)} records.")
        
        print("Updating AD to '車體外裝'...")
        res_ad = client.table('reports').update({'component': '車體外裝'}).eq('component', 'AD').execute()
        print(f"Updated AD: {len(res_ad.data)} records.")
        
        print("Database updates completed successfully!")
    except Exception as e:
        print(f"Error during database update: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()
