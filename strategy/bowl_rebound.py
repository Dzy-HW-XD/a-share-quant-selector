"""
碗口反弹策略 - 通达信公式 Python 实现

指标定义：
1. 知行短期趋势线 = EMA(EMA(CLOSE,10),10)
   - 对收盘价先做一次10日EMA，再做一次10日EMA

2. 知行多空线 = (MA(CLOSE,5) + MA(CLOSE,10) + MA(CLOSE,20) + MA(CLOSE,30)) / 4
   - 5日、10日、20日、30日均线平均值

选股条件：
3. 趋势线在上 = 知行短期趋势线 > 知行多空线
   - 短期趋势在多空线上方，表示上升趋势

4. 回落碗中 = CLOSE >= 知行多空线 AND CLOSE <= 知行短期趋势线
   - 价格回落至碗中（多空线和短期趋势线之间）

5. 回落短期趋势 = CLOSE >= 知行短期趋势线*0.98 AND CLOSE <= 知行短期趋势线*1.02
   - 价格在短期趋势线附近±2%范围内

6. KDJ计算(9,3,3): RSV->K->D->J
   - RSV = (CLOSE - LLV(LOW,9)) / (HHV(HIGH,9) - LLV(LOW,9)) * 100
   - K = SMA(RSV,3,1)
   - D = SMA(K,3,1)
   - J = 3*K - 2*D

7. 关键K线 = V>=REF(V,1)*N AND C>O AND 流通市值>CAP
   - 成交量是前一天的N倍以上 AND 阳线 AND 流通市值达标

8. 异动 = EXIST(关键K线, M)
   - 在M天内存在关键K线

9. 选股信号 = 异动 AND 趋势线在上 AND (回落碗中 OR 回落短期趋势) AND J<=J_VAL
   - 同时满足以上所有条件
"""
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from strategy.base_strategy import BaseStrategy
from utils.technical import (
    MA, EMA, LLV, HHV, REF, EXIST,
    KDJ, calculate_zhixing_trend
)


class BowlReboundStrategy(BaseStrategy):
    """碗口反弹策略"""
    
    def __init__(self, params=None):
        # 默认参数
        default_params = {
            'N': 4,              # 成交量倍数
            'M': 15,             # 回溯天数
            'CAP': 4000000000,   # 流通市值>40亿
            'J_VAL': 30,         # J值上限
            'M1': 5,             # MA周期1
            'M2': 10,            # MA周期2
            'M3': 20,            # MA周期3
            'M4': 30             # MA周期4
        }
        
        # 合并用户参数
        if params:
            default_params.update(params)
        
        super().__init__("碗口反弹策略", default_params)
    
    def calculate_indicators(self, df) -> pd.DataFrame:
        """
        计算碗口反弹策略所需的所有指标
        """
        result = df.copy()
        
        # 1. 知行趋势线
        trend_df = calculate_zhixing_trend(result)
        result['short_term_trend'] = trend_df['short_term_trend']
        result['bull_bear_line'] = trend_df['bull_bear_line']
        
        # 2. 趋势线在上
        result['trend_above'] = result['short_term_trend'] > result['bull_bear_line']
        
        # 3. 回落碗中
        result['fall_in_bowl'] = ((result['close'] >= result['bull_bear_line']) & 
                                   (result['close'] <= result['short_term_trend']))
        
        # 4. 回落短期趋势 (在趋势线附近±2%)
        result['near_short_trend'] = (
            (result['close'] >= result['short_term_trend'] * 0.98) & 
            (result['close'] <= result['short_term_trend'] * 1.02)
        )
        
        # 5. KDJ指标
        kdj_df = KDJ(result, n=9, m1=3, m2=3)
        result['K'] = kdj_df['K']
        result['D'] = kdj_df['D']
        result['J'] = kdj_df['J']
        
        # 6. 关键K线条件
        # V >= REF(V,1) * N (成交量是前一天的N倍)
        result['vol_ratio'] = result['volume'] / REF(result['volume'], 1)
        result['vol_surge'] = result['vol_ratio'] >= self.params['N']
        
        # C > O (收盘价>开盘价，阳线)
        result['positive_candle'] = result['close'] > result['open']
        
        # 流通市值 > CAP
        result['market_cap_ok'] = result['market_cap'] > self.params['CAP']
        
        # 关键K线 = 放量 AND 阳线 AND 市值达标
        result['key_candle'] = (
            result['vol_surge'] & 
            result['positive_candle'] & 
            result['market_cap_ok']
        )
        
        # 7. 异动 = EXIST(关键K线, M)
        result['abnormal'] = EXIST(result['key_candle'], self.params['M'])
        
        # 8. J值条件
        result['j_low'] = result['J'] <= self.params['J_VAL']
        
        # 9. 选股信号
        result['signal'] = (
            result['abnormal'] & 
            result['trend_above'] & 
            (result['fall_in_bowl'] | result['near_short_trend']) & 
            result['j_low']
        )
        
        return result
    
    def select_stocks(self, df, stock_name='') -> list:
        """
        选股逻辑 - 返回最新的选股信号
        """
        if df.empty:
            return []
        
        # 过滤退市/异常股票
        if stock_name:
            # 过滤名称包含退市标识的股票
            invalid_keywords = ['退', '未知', '退市', '已退']
            if any(kw in stock_name for kw in invalid_keywords):
                return []
        
        # 过滤数据异常的股票（如J值极端异常，可能是退市股票）
        recent_df = df.head(30)  # 最近30天
        if recent_df['J'].abs().mean() > 80:
            # J值长期极端，可能是停牌/退市股票
            return []
        
        # 检查最近是否有有效交易（成交量>0）
        if recent_df['volume'].sum() <= 0:
            return []
        
        signals = []
        
        # 获取最近有信号的日子
        signal_df = df[df['signal'] == True].copy()
        
        if signal_df.empty:
            return []
        
        # 取最新的信号
        latest = signal_df.iloc[0]
        
        # 获取最新信号的索引位置
        latest_idx = df.index[df['date'] == latest['date']][0]
        
        # 在回溯期内(M天内)查找关键K线，并确保是阳线
        lookback_start = max(0, latest_idx)
        lookback_end = min(len(df), latest_idx + self.params['M'] + 1)
        lookback_df = df.iloc[lookback_start:lookback_end]
        
        # 关键K线必须是阳线 (close > open)
        key_candles_in_range = lookback_df[
            (lookback_df['key_candle'] == True) & 
            (lookback_df['close'] > lookback_df['open'])  # 确保是阳线
        ]
        
        # 如果没有符合条件的阳线关键K线，则放弃此信号
        if key_candles_in_range.empty:
            return []
        
        # 构建信号详情
        signal_info = {
            'date': latest['date'],
            'close': round(latest['close'], 2),
            'J': round(latest['J'], 2),
            'volume_ratio': round(latest['vol_ratio'], 2) if not pd.isna(latest['vol_ratio']) else 1.0,
            'market_cap': round(latest['market_cap'] / 1e8, 2),  # 转换为亿
            'reasons': []
        }
        
        # 判断买入理由
        if latest['fall_in_bowl']:
            signal_info['reasons'].append('回落碗中')
        if latest['near_short_trend']:
            signal_info['reasons'].append('回落短期趋势线')
        
        # 记录最近的关键K线日期（已确保是阳线）
        latest_key = key_candles_in_range.iloc[0]
        signal_info['key_candle_date'] = latest_key['date']
        
        signals.append(signal_info)
        
        return signals
