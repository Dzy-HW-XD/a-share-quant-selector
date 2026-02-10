"""
策略注册器 - 支持动态加载策略
"""
import importlib
import sys
from pathlib import Path
import yaml


class StrategyRegistry:
    """策略注册器"""
    
    def __init__(self, params_file="config/strategy_params.yaml"):
        self.strategies = {}
        self.params_file = Path(params_file)
        self.params = self._load_params()
    
    def _load_params(self):
        """加载策略参数配置"""
        if self.params_file.exists():
            with open(self.params_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def register(self, strategy_class, name=None):
        """
        注册策略
        :param strategy_class: 策略类
        :param name: 策略名称（默认使用类名）
        """
        strategy_name = name or strategy_class.__name__
        
        # 获取该策略的参数
        params = self.params.get(strategy_name, {})
        
        # 实例化策略
        strategy = strategy_class(params=params)
        self.strategies[strategy_name] = strategy
        
        return strategy
    
    def get_strategy(self, name):
        """获取已注册的策略"""
        return self.strategies.get(name)
    
    def list_strategies(self):
        """列出所有已注册的策略"""
        return list(self.strategies.keys())
    
    def auto_register_from_directory(self, strategy_dir="strategy"):
        """
        自动从目录加载策略
        导入所有非 _ 开头的 .py 文件
        """
        strategy_path = Path(strategy_dir)
        if not strategy_path.exists():
            strategy_path = Path(__file__).parent
        
        # 添加策略目录到路径
        if str(strategy_path) not in sys.path:
            sys.path.insert(0, str(strategy_path))
        
        # 遍历策略文件
        for py_file in strategy_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            
            module_name = py_file.stem
            
            try:
                # 动态导入模块
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                else:
                    module = importlib.import_module(module_name)
                
                # 查找策略类（继承自 BaseStrategy 的类）
                from strategy.base_strategy import BaseStrategy
                
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseStrategy) and 
                        attr is not BaseStrategy):
                        
                        # 注册策略（排除基类）
                        self.register(attr, name=attr_name)
                        print(f"  ✓ 注册策略: {attr_name}")
                        
            except Exception as e:
                print(f"  ✗ 加载 {module_name} 失败: {e}")
    
    def run_all(self, stock_data_dict):
        """
        运行所有策略
        :param stock_data_dict: {code: (name, df)} 格式的股票数据
        :return: {strategy_name: [signals]} 格式的结果
        """
        results = {}
        total_stocks = len(stock_data_dict)
        
        for strategy_name, strategy in self.strategies.items():
            print(f"\n执行策略: {strategy_name}")
            print(f"  共 {total_stocks} 只股票待分析...")
            signals = []
            processed = 0
            
            for code, (name, df) in stock_data_dict.items():
                result = strategy.analyze_stock(code, name, df)
                if result:
                    signals.append(result)
                
                processed += 1
                # 每100只股票显示一次进度
                if processed % 100 == 0 or processed == total_stocks:
                    print(f"  进度: [{processed}/{total_stocks}] 已分析 {processed} 只，选出 {len(signals)} 只...")
            
            results[strategy_name] = signals
            print(f"  ✓ 选股完成: 共 {len(signals)} 只股票符合策略")
        
        return results


# 全局注册器实例
_registry = None

def get_registry(params_file="config/strategy_params.yaml"):
    """获取全局策略注册器"""
    global _registry
    if _registry is None:
        _registry = StrategyRegistry(params_file)
    return _registry
