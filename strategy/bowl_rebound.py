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

4. 异动放量阳线 = V>=REF(V,1)*N AND C>O AND 总市值>CAP
   - 成交量是前一天的N倍以上 AND 阳线 AND 总市值达标

5. 异动 = EXIST(关键K线, M)
   - 在M天内存在关键K线

6. KDJ计算(9,3,3): RSV->K->D->J
   - J = 3*K - 2*D

7. J值低位 = J <= J_VAL

8. 分类标记（满足条件的按优先级标记）：
   - 回落碗中：价格位于知行短期趋势线和知行多空线之间（优先级最高）
   - 靠近多空线：价格距离知行多空线 ±duokong_pct% 范围内
   - 靠近短期趋势线：价格距离知行短期趋势线 ±short_pct% 范围内

9. 选股信号 = 异动 AND 趋势线在上 AND J值低位 AND (回落碗中 OR 靠近多空线 OR 靠近短期趋势线)
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
    """碗口反弹策略 - 分类标记版"""
    
    def __init__(self, params=None):
        # 默认参数
        default_params = {
            'N': 4,              # 成交量倍数
            'M': 15,             # 回溯天数
            'CAP': 4000000000,   # 总市值>40亿
            'J_VAL': 30,         # J值上限
            'duokong_pct': 3,    # 距离多空线百分比(默认3%)
            'short_pct': 2,      # 距离短期趋势线百分比(默认2%)
            'M1': 14,            # MA周期1 (多空线)
            'M2': 28,            # MA周期2 (多空线)
            'M3': 57,            # MA周期3 (多空线)
            'M4': 114            # MA周期4 (多空线)
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
        
        # 1. 知行趋势线（使用technical模块，正确处理倒序数据）
        from utils.technical import calculate_zhixing_trend
        trend_df = calculate_zhixing_trend(
            result, 
            m1=self.params['M1'],
            m2=self.params['M2'],
            m3=self.params['M3'],
            m4=self.params['M4']
        )
        result['short_term_trend'] = trend_df['short_term_trend']
        result['bull_bear_line'] = trend_df['bull_bear_line']
        
        # 2. 上升趋势
        result['trend_above'] = result['short_term_trend'] > result['bull_bear_line']
        
        # 3. 分类条件计算
        # 回落碗中：价格位于多空线和短期趋势线之间（优先级最高）
        result['fall_in_bowl'] = (
            (result['close'] >= result['bull_bear_line']) & 
            (result['close'] <= result['short_term_trend'])
        )
        
        # 靠近多空线：价格距离多空线 ±duokong_pct% 范围内
        duokong_pct = self.params['duokong_pct'] / 100
        result['near_duokong'] = (
            (result['close'] >= result['bull_bear_line'] * (1 - duokong_pct)) & 
            (result['close'] <= result['bull_bear_line'] * (1 + duokong_pct))
        )
        
        # 靠近短期趋势线：价格距离短期趋势线 ±short_pct% 范围内
        short_pct = self.params['short_pct'] / 100
        result['near_short_trend'] = (
            (result['close'] >= result['short_term_trend'] * (1 - short_pct)) & 
            (result['close'] <= result['short_term_trend'] * (1 + short_pct))
        )
        
        # 4. KDJ指标
        from utils.technical import KDJ
        kdj_df = KDJ(result, n=9, m1=3, m2=3)
        result['K'] = kdj_df['K']
        result['D'] = kdj_df['D']
        result['J'] = kdj_df['J']
        
        # 5. 放量阳线条件
        # 成交量 >= 前一日 * N
        from utils.technical import REF
        result['vol_ratio'] = result['volume'] / REF(result['volume'], 1)
        result['vol_surge'] = result['vol_ratio'] >= self.params['N']
        
        # 阳线：收盘价 > 开盘价
        result['positive_candle'] = result['close'] > result['open']
        
        # 总市值达标（优先从实时数据获取）
        result['market_cap_ok'] = self._check_market_cap_realtime(result)
        
        # 关键K线 = 放量 AND 阳线 AND 市值达标
        result['key_candle'] = (
            result['vol_surge'] & 
            result['positive_candle'] & 
            result['market_cap_ok']
        )
        
        # 6. 异动 = EXIST(关键K线, M)
        from utils.technical import EXIST
        result['abnormal'] = EXIST(result['key_candle'], self.params['M'])
        
        # 7. J值低位
        result['j_low'] = result['J'] <= self.params['J_VAL']
        
        return result
    
    def _check_market_cap_realtime(self, df) -> pd.Series:
        """
        检查总市值是否达标
        优先从CSV数据获取，如果异常则从实时数据获取
        """
        import akshare as ak
        
        # 尝试从CSV数据获取
        if 'market_cap' in df.columns:
            # 检查数据是否合理（单位应该是元）
            sample_cap = df['market_cap'].dropna().iloc[-1] if not df['market_cap'].dropna().empty else 0
            
            # 如果市值在合理范围（10亿到1000亿之间），使用CSV数据
            if 1e9 < sample_cap < 1e11:
                return df['market_cap'] > self.params['CAP']
        
        # 从实时数据获取总市值
        try:
            # 从股票代码推断市场
            stock_code = str(df['code'].iloc[0]) if 'code' in df.columns else None
            
            if stock_code:
                # 获取实时数据
                spot_df = ak.stock_individual_info_em(symbol=stock_code)
                if not spot_df.empty:
                    # 查找总市值
                    total_cap_row = spot_df[spot_df['item'] == '总市值']
                    if not total_cap_row.empty:
                        total_cap = total_cap_row['value'].values[0]
                        # 转换为数字（可能是字符串）
                        if isinstance(total_cap, str):
                            # 处理"33.19亿"格式
                            if '亿' in total_cap:
                                total_cap = float(total_cap.replace('亿', '')) * 1e8
                            else:
                                total_cap = float(total_cap)
                        
                        # 创建 Series
                        return pd.Series([total_cap > self.params['CAP']] * len(df), index=df.index)
        except Exception as e:
            # 如果实时获取失败，尝试用收盘价估算
            if 'close' in df.columns:
                # 假设总股本2亿股，估算市值
                estimated_cap = df['close'] * 2e8  # 粗略估计
                return estimated_cap > self.params['CAP']
        
        # 默认返回True（不过滤）
        return pd.Series([True] * len(df), index=df.index)
    
    def select_stocks(self, df, stock_name='') -> list:
        """
        选股逻辑 - 基于最新一天的数据进行筛选
        选股后按类型分类标记（优先级：回落碗中 > 靠近多空线 > 靠近短期趋势线）
        """
        if df.empty:
            return []
        
        # 过滤退市/异常股票
        if stock_name:
            invalid_keywords = ['退', '未知', '退市', '已退']
            if any(kw in stock_name for kw in invalid_keywords):
                return []
            
            # 过滤 ST/*ST 股票
            if stock_name.startswith('ST') or stock_name.startswith('*ST'):
                return []
        
        # 获取最新一天的数据
        latest = df.iloc[0]
        latest_date = latest['date']
        
        # 检查最新一天是否有有效交易
        if latest['volume'] <= 0 or pd.isna(latest['close']):
            return []
        
        # 过滤数据异常的股票
        recent_df = df.head(30)
        if recent_df['J'].abs().mean() > 80:
            return []
        
        # ========== 核心条件检查 ==========
        
        # 1. 上升趋势
        if not latest['trend_above']:
            return []
        
        # 2. J值条件
        if not latest['j_low']:
            return []
        
        # 3. 异动条件：在M天内存在放量阳线
        lookback_df = df.head(self.params['M'])

        # 剔除：如果回顾期内最大成交量的一天是阴线（最大量是阴量）
        max_volume_idx = lookback_df['volume'].idxmax()
        max_volume_row = lookback_df.loc[max_volume_idx]
        if max_volume_row['close'] < max_volume_row['open']:
            # 最大成交量那天是阴线，剔除
            return []

        key_candles = lookback_df[
            (lookback_df['key_candle'] == True) &
            (lookback_df['close'] > lookback_df['open'])
        ]

        if key_candles.empty:
            return []
        
        # ========== 分类标记（按优先级） ==========
        
        reasons = []
        category = None
        
        # 优先级1：回落碗中（价格位于多空线和短期趋势线之间）
        if latest['fall_in_bowl']:
            reasons.append('回落碗中')
            category = 'bowl_center'
        # 优先级2：靠近多空线
        elif latest['near_duokong']:
            reasons.append(f'靠近多空线(±{self.params["duokong_pct"]}%)')
            category = 'near_duokong'
        # 优先级3：靠近短期趋势线
        elif latest['near_short_trend']:
            reasons.append(f'靠近短期趋势线(±{self.params["short_pct"]}%)')
            category = 'near_short_trend'
        else:
            # 不满足任何位置条件
            return []
        
        # ========== 构建选股信号 ==========
        
        latest_key = key_candles.iloc[0]
        
        signal_info = {
            'date': latest_date,
            'close': round(latest['close'], 2),
            'J': round(latest['J'], 2),
            'volume_ratio': round(latest['vol_ratio'], 2) if not pd.isna(latest['vol_ratio']) else 1.0,
            'market_cap': round(latest['market_cap'] / 1e8, 2),
            'short_term_trend': round(latest['short_term_trend'], 2),
            'bull_bear_line': round(latest['bull_bear_line'], 2),
            'reasons': reasons,
            'category': category,  # 分类标记
            'key_candle_date': latest_key['date'],
        }
        
        return [signal_info]
