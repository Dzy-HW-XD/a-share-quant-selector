# 市值数据修复说明

## 问题背景
初始化数据时，部分数据源无法获取真实的总市值，会使用估算值填充。这会导致选股时市值过滤不准确。

## 解决方案

### 方案1：执行修复脚本（推荐）
在 `init` 完成后，执行以下命令修复所有CSV文件的市值数据：

```bash
cd /root/quant-csv
python3 fix_market_cap_after_init.py
```

### 方案2：策略实时获取（已内置）
选股策略 `BowlReboundStrategy` 已修改为从实时数据获取总市值，即使CSV中的数据不正确，选股结果也是准确的。

## 客户使用流程

```bash
# 1. 克隆仓库
git clone https://github.com/Dzy-HW-XD/a-share-quant-selector.git
cd a-share-quant-selector

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据（耗时较长，约30-60分钟）
python3 main.py init

# 4. 修复市值数据（重要！）
python3 fix_market_cap_after_init.py

# 5. 执行选股
python3 main.py run

# 或带B1匹配排序
python3 main.py run --b1-match
```

## 验证市值数据

检查华锋股份(002806)的市值：

```bash
python3 -c "
import pandas as pd
df = pd.read_csv('data/00/002806.csv')
print(f'总市值: {df[\"market_cap\"].iloc[0]:,.0f}元 ({df[\"market_cap\"].iloc[0]/1e8:.2f}亿)')
"
```

预期结果：约33.19亿（不是363亿）

## 注意事项

1. `fix_market_cap_after_init.py` 只需要在 `init` 后执行一次
2. 后续 `update` 会自动获取正确的市值
3. 即使不执行修复脚本，选股策略也会从实时数据获取正确市值
