# 📊 A股量化选股系统

基于 Python + akshare 的A股量化选股系统，实现碗口反弹策略。

## ✨ 特性

- 📈 **碗口反弹策略** - 基于KDJ、趋势线和成交量异动选股
- 🔔 **钉钉通知** - 选股结果自动推送到钉钉群
- 🌐 **Web管理界面** - 可视化查看股票数据、K线图和KDJ指标
- ⏰ **定时任务** - 支持 crontab 定时执行
- 🔄 **自动过滤** - 自动过滤退市、ST、债基、ETF等

## 📁 项目结构

```
/root/quant-csv/
├── main.py                    # 主程序入口
├── web_server.py              # Web服务器
├── quant.sh                   # 快捷命令脚本
├── requirements.txt           # Python依赖
├── README.md                  # 项目说明
├── config/                    # 配置文件
│   ├── config.yaml            # 主配置（钉钉、定时等）
│   ├── strategy_params.yaml   # 策略参数配置
│   └── crontab.txt            # 定时任务配置示例
├── data/                      # 股票数据目录
│   ├── 00/                    # 按代码前缀分组存储
│   ├── 30/
│   ├── 60/
│   ├── stock_names.json       # 股票名称缓存
│   └── failed_stocks.json     # 获取失败的股票记录
├── utils/                     # 工具模块
│   ├── akshare_fetcher.py     # 数据抓取
│   ├── csv_manager.py         # CSV文件管理
│   ├── technical.py           # 技术指标计算（KDJ、MA等）
│   └── dingtalk_notifier.py   # 钉钉通知
├── strategy/                  # 策略模块
│   ├── base_strategy.py       # 策略基类
│   ├── strategy_registry.py   # 策略注册器
│   └── bowl_rebound.py        # 碗口反弹策略实现
└── web/                       # Web前端
    ├── templates/index.html   # 主页面
    └── static/
        ├── css/style.css      # 样式
        └── js/app.js          # 前端逻辑
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /root/quant-csv
pip3 install -r requirements.txt --break-system-packages
```

### 2. 配置钉钉通知（可选）

编辑 `config/config.yaml`：

```yaml
dingtalk:
  webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=你的token"
  secret: "你的secret"
```

### 3. 首次全量抓取

```bash
python3 main.py init
```

### 4. 执行选股

```bash
python3 main.py select
```

### 5. 完整流程（更新+选股+通知）

```bash
python3 main.py run
```

## 📋 命令说明

| 命令 | 说明 |
|-----|------|
| `python3 main.py init` | 首次全量抓取6年历史数据 |
| `python3 main.py update` | 每日增量更新 |
| `python3 main.py select` | 执行选股策略 |
| `python3 main.py run` | 完整流程（更新+选股+通知） |
| `python3 main.py schedule` | 启动定时调度 |
| `python3 main.py web` | 启动Web界面 (端口5000) |

或使用快捷脚本：
```bash
./quant.sh init
./quant.sh run
./quant.sh web
```

## ⚙️ 策略配置

编辑 `config/strategy_params.yaml`：

```yaml
BowlReboundStrategy:
  N: 4                    # 成交量倍数（关键K线放量标准）
  M: 15                   # 回溯天数（查找异动K线）
  CAP: 4000000000         # 流通市值门槛（40亿）
  J_VAL: 30               # J值上限（超买超卖阈值）
```

## 📝 碗口反弹策略逻辑

1. **知行短期趋势线** = EMA(EMA(CLOSE,10),10)
2. **知行多空线** = (MA5 + MA10 + MA20 + MA30) / 4
3. **上升趋势** = 短期趋势线 > 多空线
4. **回落条件** = 价格回落至碗中或短期趋势线附近(±2%)
5. **KDJ指标** = 计算K、D、J值，要求 J <= J_VAL
6. **异动检测** = 近期(M天内)存在放量阳线(成交量>=前日*N倍)
7. **选股信号** = 上升趋势 AND 回落条件 AND 异动 AND J低位

## 🕐 定时任务

添加到 crontab：

```bash
crontab -l                    # 查看现有任务
crontab -e                    # 编辑任务
```

复制 `config/crontab.txt` 内容，修改路径后添加。

## 🌐 Web 界面

```bash
python3 main.py web              # 默认端口 5000
python3 main.py web --port 8080  # 指定端口
```

### 功能

- **📊 概览** - 股票数量、最新数据日期
- **📈 股票列表** - 查看所有股票，点击查看K线图和KDJ指标
- **🎯 选股结果** - 执行选股并查看信号
- **⚙️ 策略配置** - 在线修改策略参数

## 🔧 扩展新策略

1. 在 `strategy/` 创建新文件，继承 `BaseStrategy`：

```python
from strategy.base_strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__("我的策略", params)
    
    def calculate_indicators(self, df):
        # 计算指标
        return df
    
    def select_stocks(self, df, stock_name=''):
        # 选股逻辑
        return signals
```

2. 在 `config/strategy_params.yaml` 添加参数
3. 系统自动识别并执行

## ⚠️ 注意事项

1. **首次运行** - 使用 `init` 命令抓取历史数据，约需10-15分钟
2. **网络连接** - 如无法连接 akshare，会自动使用内置股票列表(129只)
3. **数据过滤** - 自动过滤退市、ST、债基、ETF等
4. **日志查看** - `/var/log/quant-csv/` 目录查看运行日志

## 📞 依赖要求

- Python >= 3.8
- 主要依赖: akshare, pandas, numpy, flask, PyYAML

```
akshare>=1.11.0
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
PyYAML>=6.0
flask>=3.0.0
```
