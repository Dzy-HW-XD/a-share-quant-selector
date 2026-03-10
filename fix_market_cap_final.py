#!/usr/bin/env python3
"""
修复所有CSV文件的市值数据
使用akshare实时获取正确的总市值
"""
import pandas as pd
import glob
import akshare as ak
from pathlib import Path
import time

def fix_all_market_cap():
    """修复所有股票的market_cap"""
    
    print('获取实时行情数据...')
    try:
        spot_df = ak.stock_zh_a_spot_em()
        print(f'获取到 {len(spot_df)} 只股票')
    except Exception as e:
        print(f'获取失败: {e}')
        return
    
    # 创建代码到市值的映射
    cap_col = '总市值' if '总市值' in spot_df.columns else '总市值-亿元'
    
    market_cap_map = {}
    for _, row in spot_df.iterrows():
        code = str(row['代码']).zfill(6)
        cap = row[cap_col]
        if pd.notna(cap) and cap > 0:
            # 如果单位是亿元(小于1万亿)，转为元
            if cap < 1e10:
                cap = cap * 1e8
            market_cap_map[code] = int(cap)
    
    print(f'成功映射 {len(market_cap_map)} 只股票市值')
    
    # 获取所有CSV文件
    csv_files = glob.glob('data/**/*.csv', recursive=True)
    print(f'\n总CSV文件: {len(csv_files)}')
    
    # 修复所有CSV
    updated = 0
    skipped = 0
    failed = 0
    
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
            
            # 更新市值
            df['market_cap'] = market_cap_map[code]
            df.to_csv(csv_file, index=False)
            updated += 1
            
            if (i + 1) % 500 == 0:
                print(f'  已修复 {updated} 个文件...')
                
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f'  修复失败 {code}: {e}')
    
    print(f'\n完成: 成功{updated}, 失败{failed}, 跳过{skipped}')

if __name__ == '__main__':
    fix_all_market_cap()
