#!/usr/bin/env python3
"""
A股量化选股系统 - 主程序

使用方法:
    python main.py init      # 首次全量抓取
    python main.py update    # 每日增量更新
    python main.py select    # 执行选股
    python main.py run       # 完整流程（更新+选股+通知）
    python main.py schedule  # 启动定时调度
"""
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, time as dt_time
import time

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.akshare_fetcher import AKShareFetcher
from utils.csv_manager import CSVManager
from utils.dingtalk_notifier import DingTalkNotifier
from strategy.strategy_registry import get_registry
import yaml


class QuantSystem:
    """量化系统主类"""
    
    def __init__(self, config_file="config/config.yaml"):
        self.config = self._load_config(config_file)
        self.data_dir = self.config.get('data_dir', 'data')
        self.csv_manager = CSVManager(self.data_dir)
        self.fetcher = AKShareFetcher(self.data_dir)
        self.notifier = self._init_notifier()
        self.registry = get_registry("config/strategy_params.yaml")
    
    def _load_config(self, config_file):
        """加载配置文件"""
        config_path = Path(config_file)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def _init_notifier(self):
        """初始化通知器"""
        webhook = self.config.get('dingtalk', {}).get('webhook_url')
        secret = self.config.get('dingtalk', {}).get('secret')
        return DingTalkNotifier(webhook, secret)
    
    def _load_stock_names(self, stock_data):
        """加载股票名称（优先从CSV文件）"""
        names_file = Path(self.data_dir) / 'stock_names.json'
        
        # 尝试从网络获取
        try:
            stock_names = self.fetcher.get_all_stock_codes()
            if stock_names:
                # 保存到本地
                import json
                with open(names_file, 'w', encoding='utf-8') as f:
                    json.dump(stock_names, f, ensure_ascii=False)
                return stock_names
        except:
            pass
        
        # 从本地缓存读取
        if names_file.exists():
            import json
            with open(names_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 使用默认名称
        return {code: f"股票{code}" for code in stock_data.keys()}
    
    def init_data(self, max_stocks=None):
        """首次全量抓取"""
        print("=" * 60)
        print("🚀 首次全量数据抓取")
        print("=" * 60)
        self.fetcher.init_full_data(max_stocks=max_stocks)
        print("\n✓ 数据初始化完成")
    
    def update_data(self, max_stocks=None):
        """每日增量更新"""
        print("=" * 60)
        print("🔄 每日增量更新")
        print("=" * 60)
        self.fetcher.daily_update(max_stocks=max_stocks)
        print("\n✓ 数据更新完成")
    
    def select_stocks(self):
        """执行选股"""
        print("=" * 60)
        print("🎯 执行选股策略")
        print("=" * 60)
        
        # 加载策略
        print("\n加载策略...")
        self.registry.auto_register_from_directory("strategy")
        
        if not self.registry.list_strategies():
            print("✗ 没有找到可用策略")
            return {}
        
        print(f"已加载 {len(self.registry.list_strategies())} 个策略")
        
        # 输出当前策略参数
        print("\n当前策略参数:")
        for strategy_name, strategy in self.registry.strategies.items():
            print(f"\n  🎯 {strategy_name}:")
            for param_name, param_value in strategy.params.items():
                # 对特定参数添加说明
                note = ""
                if param_name == 'N':
                    note = " (成交量倍数)"
                elif param_name == 'M':
                    note = " (回溯天数)"
                elif param_name == 'CAP':
                    note = f" ({param_value/1e8:.0f}亿市值门槛)"
                elif param_name == 'J_VAL':
                    note = " (J值上限)"
                elif param_name in ['M1', 'M2', 'M3', 'M4']:
                    note = " (MA周期)"
                print(f"      {param_name}: {param_value}{note}")
        
        # 加载股票数据
        print("\n加载股票数据...")
        stock_codes = self.csv_manager.list_all_stocks()
        
        if not stock_codes:
            print("✗ 没有股票数据，请先执行 init 或 update")
            return {}
        
        print(f"共 {len(stock_codes)} 只股票")
        
        # 先获取股票名称
        stock_names = self._load_stock_names({})
        
        # 构建数据字典
        print("\n过滤有效股票数据...")
        stock_data = {}
        valid_count = 0
        invalid_count = 0
        for i, code in enumerate(stock_codes, 1):
            df = self.csv_manager.read_stock(code)
            name = stock_names.get(code, '未知')
            # 过滤退市/异常股票名称
            invalid_keywords = ['退', '未知', '退市', '已退']
            if any(kw in name for kw in invalid_keywords):
                invalid_count += 1
                continue
            if not df.empty and len(df) >= 60:
                stock_data[code] = (name, df)
                valid_count += 1
            # 每500只显示一次进度
            if i % 500 == 0 or i == len(stock_codes):
                print(f"  进度: [{i}/{len(stock_codes)}] 有效 {valid_count} 只，过滤 {invalid_count} 只...")
        
        print(f"\n✓ 有效数据: {len(stock_data)} 只 (过滤 {invalid_count} 只异常股票)")
        
        # 执行选股
        results = self.registry.run_all(stock_data)
        
        # 显示结果
        print("\n" + "=" * 60)
        print("📊 选股结果汇总")
        print("=" * 60)
        
        for strategy_name, signals in results.items():
            print(f"\n{strategy_name}: {len(signals)} 只")
            for signal in signals:
                code = signal['code']
                name = signal.get('name', stock_names.get(code, '未知'))
                for s in signal['signals']:
                    print(f"  - {code} {name}: 价格={s['close']}, J={s['J']}")
        
        return results, stock_names
    
    def run_full(self):
        """完整流程：更新 + 选股 + 通知"""
        print("=" * 60)
        print("🚀 执行完整流程")
        print("=" * 60)
        
        # 1. 更新数据
        self.update_data()
        
        # 2. 选股
        results, stock_names = self.select_stocks()
        
        # 3. 发送通知
        if results:
            self.notifier.send_stock_selection(results, stock_names)
        
        return results
    
    def run_schedule(self):
        """启动定时调度"""
        try:
            import schedule
        except ImportError:
            print("✗ 请安装 schedule: pip install schedule")
            return
        
        schedule_time = self.config.get('schedule', {}).get('time', '15:05')
        
        print("=" * 60)
        print(f"⏰ 启动定时调度")
        print(f"   每日 {schedule_time} 执行选股任务")
        print("=" * 60)
        
        # 设置定时任务
        schedule.every().day.at(schedule_time).do(self.run_full)
        
        print("\n按 Ctrl+C 停止")
        
        while True:
            schedule.run_pending()
            time.sleep(60)


def main():
    parser = argparse.ArgumentParser(
        description='A股量化选股系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py init          # 首次抓取6年历史数据
  python main.py update        # 每日增量更新
  python main.py select        # 执行选股
  python main.py run           # 完整流程（更新+选股+通知）
  python main.py schedule      # 启动定时调度（每天15:05）
  python main.py web           # 启动Web界面
        """
    )
    
    parser.add_argument(
        'command',
        choices=['init', 'update', 'select', 'run', 'schedule', 'web'],
        help='要执行的命令'
    )
    
    parser.add_argument(
        '--max-stocks',
        type=int,
        default=None,
        help='限制处理的股票数量（用于测试）'
    )
    
    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='配置文件路径'
    )
    
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Web服务器监听地址 (默认: 0.0.0.0)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Web服务器端口 (默认: 5000)'
    )
    
    args = parser.parse_args()
    
    # 切换工作目录
    os.chdir(project_root)
    
    # 创建系统实例
    quant = QuantSystem(args.config)
    
    # 执行命令
    if args.command == 'init':
        quant.init_data(max_stocks=args.max_stocks)
    
    elif args.command == 'update':
        quant.update_data(max_stocks=args.max_stocks)
    
    elif args.command == 'select':
        quant.select_stocks()
    
    elif args.command == 'run':
        quant.run_full()
    
    elif args.command == 'schedule':
        quant.run_schedule()
    
    elif args.command == 'web':
        # 启动Web服务器
        from web_server import run_web_server
        run_web_server(host=args.host, port=args.port)


if __name__ == '__main__':
    main()
