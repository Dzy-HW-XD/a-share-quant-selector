#!/usr/bin/env python3
"""
修复脚本：批量更新所有CSV文件的market_cap字段
在 init 完成后执行此脚本以确保市值数据正确
"""
import pandas as pd
import glob
from pathlib import Path
import akshare as ak

def fix_all_market_cap():
    """批量更新所有股票的market_cap"""
    
    print('获取实时行情数据（包含市值）...')
    
    # 获取实时行情
    spot_df = ak.stock_zh_a_spot_em()
    print(f'获取到 {len(spot_df)} 只股票')
    
    # 创建市值映射
    cap_col = '总市值' if '总市值' in spot_df.columns else '总市值-亿元'
    
    market_cap_map = {}
    for _, row in spot_df.iterrows():
        code = str(row['代码']).zfill(6)
        cap = row[cap_col]
        if pd.notna(cap) and cap > 0:
            if cap < 1e10:  # 单位是亿元
                cap = cap * 1e8
            market_cap_map[code] = int(cap)
    
    print(f'成功映射 {len(market_cap_map)} 只股票市值')
    
    # 批量更新CSV
    csv_files = glob.glob('data/**/*.csv', recursive=True)
    print(f'\n总CSV文件: {len(csv_files)}')
    
    updated = 0
    skipped = 0
    
    for i, csv_file in enumerate(csv_files):
        code = Path(csv_file).stem
        
        if code not in market_cap_map:
            skipped += 1
            continue
        
        try:
            df = pd.read_csv(csv_file)
            if df.empty:
                skipped += 1
                continue
            
            df['market_cap'] = market_cap_map[code]
            df.to_csv(csv_file, index=False)
            updated += 1
            
            if (i + 1) % 500 == 0:
                print(f'  已更新 {updated}...')
                
        except Exception as e:
            skipped += 1
    
    print(f'\n完成: 成功{updated}, 跳过{skipped}')
    print('市值数据已修复！')

if __name__ == '__main__':
    fix_all_market_cap()
