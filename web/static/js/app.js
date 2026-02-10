/**
 * A股量化选股系统 - 前端逻辑
 */

// 全局状态
let currentPage = 'dashboard';
let chartInstance = null;

// 页面切换
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        const page = item.dataset.page;
        switchPage(page);
    });
});

function switchPage(page) {
    currentPage = page;
    
    // 更新导航
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    // 更新页面标题
    const titles = {
        'dashboard': '系统概览',
        'stocks': '股票列表',
        'selection': '选股结果',
        'strategies': '策略配置'
    };
    document.getElementById('page-title').textContent = titles[page];
    
    // 显示对应页面
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === page + '-page');
    });
    
    // 加载页面数据
    if (page === 'dashboard') {
        loadStats();
    } else if (page === 'stocks') {
        loadStocks();
    } else if (page === 'strategies') {
        loadStrategies();
    }
}

// 加载统计信息
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('stat-stocks').textContent = result.data.total_stocks;
            document.getElementById('stat-date').textContent = result.data.latest_date;
            document.getElementById('stat-strategies').textContent = result.data.strategies;
        }
    } catch (error) {
        console.error('加载统计信息失败:', error);
    }
}

// 加载股票列表 - 支持分页获取所有股票
async function loadStocks() {
    const tbody = document.getElementById('stocks-tbody');
    tbody.innerHTML = '<tr><td colspan="7" class="loading">正在加载股票列表...</td></tr>';
    
    try {
        let allStocks = [];
        let page = 1;
        let totalPages = 1;
        
        // 分页获取所有股票
        do {
            const response = await fetch(`/api/stocks?page=${page}&per_page=500`);
            const result = await response.json();
            
            if (result.success) {
                allStocks = allStocks.concat(result.data);
                totalPages = result.total_pages;
                tbody.innerHTML = `<tr><td colspan="7" class="loading">已加载 ${allStocks.length} / ${result.total} 只股票...</td></tr>`;
                page++;
            } else {
                break;
            }
        } while (page <= totalPages);
        
        renderStocks(allStocks);
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="7" class="loading">加载失败: ${error.message}</td></tr>`;
    }
}

// 渲染股票列表
function renderStocks(stocks) {
    const tbody = document.getElementById('stocks-tbody');
    
    if (stocks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">暂无数据</td></tr>';
        return;
    }
    
    tbody.innerHTML = stocks.map(stock => `
        <tr>
            <td><strong>${stock.code}</strong></td>
            <td>${stock.name}</td>
            <td>¥${stock.latest_price}</td>
            <td>${stock.latest_date}</td>
            <td>${stock.market_cap}</td>
            <td>${stock.data_count}</td>
            <td>
                <button class="btn btn-secondary" onclick="viewStockDetail('${stock.code}')">
                    查看
                </button>
            </td>
        </tr>
    `).join('');
    
    // 搜索功能
    document.getElementById('stock-search').addEventListener('input', (e) => {
        const keyword = e.target.value.toLowerCase();
        const rows = tbody.querySelectorAll('tr');
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(keyword) ? '' : 'none';
        });
    });
}

// 查看股票详情
async function viewStockDetail(code) {
    try {
        const response = await fetch(`/api/stock/${code}`);
        const result = await response.json();
        
        if (result.success) {
            showStockModal(code, result.data);
        } else {
            alert('加载股票详情失败: ' + result.error);
        }
    } catch (error) {
        alert('加载股票详情失败: ' + error.message);
    }
}

// 显示股票详情弹窗
function showStockModal(code, data) {
    const modal = document.getElementById('stock-modal');
    document.getElementById('modal-title').textContent = `股票详情: ${code}`;
    
    // 准备图表数据（数据是最新的在前，图表需要最早的在前）
    const reversedData = [...data].reverse();
    const labels = reversedData.map(d => d.date);
    const prices = reversedData.map(d => d.close);
    const kValues = reversedData.map(d => d.K);
    const dValues = reversedData.map(d => d.D);
    const jValues = reversedData.map(d => d.J);
    
    // 绘制K线图和KDJ指标
    const ctx = document.getElementById('stock-chart').getContext('2d');
    
    if (chartInstance) {
        chartInstance.destroy();
    }
    
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '收盘价',
                    data: prices,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    fill: true,
                    tension: 0.1,
                    yAxisID: 'y'
                },
                {
                    label: 'K',
                    data: kValues,
                    borderColor: '#f59e0b',
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    pointRadius: 0,
                    yAxisID: 'y1'
                },
                {
                    label: 'D',
                    data: dValues,
                    borderColor: '#10b981',
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    pointRadius: 0,
                    yAxisID: 'y1'
                },
                {
                    label: 'J',
                    data: jValues,
                    borderColor: '#ef4444',
                    backgroundColor: 'transparent',
                    borderWidth: 1,
                    pointRadius: 0,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: true
                }
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: '价格'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: 'KDJ'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
    
    // 显示最新信息
    const latest = data[0];
    const jColor = latest.J > 80 ? '#ef4444' : (latest.J < 20 ? '#10b981' : '#666');
    document.getElementById('stock-info').innerHTML = `
        <div class="signal-details" style="margin-top: 16px;">
            <span>最新价: <strong>¥${latest.close}</strong></span>
            <span>最高: <strong>¥${latest.high}</strong></span>
            <span>最低: <strong>¥${latest.low}</strong></span>
            <span>成交量: <strong>${latest.volume}</strong></span>
            <span>市值: <strong>${latest.market_cap}亿</strong></span>
        </div>
        <div class="signal-details" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #e5e7eb;">
            <span>K: <strong style="color: #f59e0b">${latest.K}</strong></span>
            <span>D: <strong style="color: #10b981">${latest.D}</strong></span>
            <span>J: <strong style="color: ${jColor}">${latest.J}</strong></span>
        </div>
    `;
    
    modal.classList.add('active');
}

// 关闭弹窗
function closeModal() {
    document.getElementById('stock-modal').classList.remove('active');
}

// 执行选股
async function runSelection() {
    const btn = document.getElementById('run-selection-btn');
    const indicator = document.getElementById('status-indicator');
    
    btn.disabled = true;
    btn.innerHTML = '<span class="icon">⏳</span> 选股中...';
    indicator.innerHTML = '<span class="dot yellow"></span> 运行中';
    
    // 切换到选股结果页
    switchPage('selection');
    document.getElementById('selection-results').innerHTML = '<p class="loading">正在执行选股策略...</p>';
    
    try {
        const response = await fetch('/api/select');
        const result = await response.json();
        
        if (result.success) {
            renderSelectionResults(result.data, result.time);
        } else {
            document.getElementById('selection-results').innerHTML = 
                `<p class="loading text-danger">选股失败: ${result.error}</p>`;
        }
    } catch (error) {
        document.getElementById('selection-results').innerHTML = 
            `<p class="loading text-danger">选股失败: ${error.message}</p>`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="icon">▶️</span> 执行选股';
        indicator.innerHTML = '<span class="dot green"></span> 就绪';
    }
}

// 渲染选股结果
function renderSelectionResults(results, time) {
    document.getElementById('selection-time').textContent = `选股时间: ${time}`;
    
    const container = document.getElementById('selection-results');
    
    let html = '';
    let totalCount = 0;
    
    for (const [strategyName, signals] of Object.entries(results)) {
        totalCount += signals.length;
        
        html += `
            <div class="selection-strategy">
                <h4>${strategyName} (${signals.length}只)</h4>
        `;
        
        if (signals.length === 0) {
            html += '<p class="text-muted">暂无选股信号</p>';
        } else {
            html += signals.map(signal => {
                const s = signal.signals[0];
                return `
                    <div class="signal-card">
                        <div class="signal-header">
                            <span class="signal-title">${signal.code} ${signal.name}</span>
                            <div class="signal-tags">
                                ${s.reasons.map(r => `<span class="tag">${r}</span>`).join('')}
                            </div>
                        </div>
                        <div class="signal-details">
                            <span>当前价: <strong>¥${s.close}</strong></span>
                            <span>J值: <strong>${s.J}</strong></span>
                            <span>量比: <strong>${s.volume_ratio}x</strong></span>
                            <span>市值: <strong>${s.market_cap}亿</strong></span>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        html += '</div>';
    }
    
    html = `<p style="margin-bottom: 20px;"><strong>共选出 ${totalCount} 只股票</strong></p>` + html;
    
    container.innerHTML = html;
}

// 加载策略配置
async function loadStrategies() {
    const container = document.getElementById('strategies-config');
    container.innerHTML = '<p class="loading">加载中...</p>';
    
    try {
        const response = await fetch('/api/config');
        const result = await response.json();
        
        if (result.success) {
            renderStrategiesConfig(result.data);
        } else {
            container.innerHTML = `<p class="loading">加载失败: ${result.error}</p>`;
        }
    } catch (error) {
        container.innerHTML = `<p class="loading">加载失败: ${error.message}</p>`;
    }
}

// 渲染策略配置
function renderStrategiesConfig(config) {
    const container = document.getElementById('strategies-config');
    
    let html = '';
    
    for (const [strategyName, params] of Object.entries(config)) {
        html += `
            <div class="strategy-config-item" data-strategy="${strategyName}">
                <h4>${strategyName}</h4>
        `;
        
        for (const [paramName, value] of Object.entries(params)) {
            html += `
                <div class="param-row">
                    <label>${paramName}:</label>
                    <input type="text" 
                           name="${strategyName}.${paramName}" 
                           value="${value}"
                           data-strategy="${strategyName}"
                           data-param="${paramName}">
                </div>
            `;
        }
        
        html += '</div>';
    }
    
    container.innerHTML = html;
}

// 保存配置
async function saveConfig() {
    const inputs = document.querySelectorAll('#strategies-config input');
    const config = {};
    
    inputs.forEach(input => {
        const strategy = input.dataset.strategy;
        const param = input.dataset.param;
        let value = input.value;
        
        // 尝试转换为数字
        if (!isNaN(value) && value !== '') {
            value = Number(value);
        }
        
        if (!config[strategy]) {
            config[strategy] = {};
        }
        config[strategy][param] = value;
    });
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('配置保存成功！');
        } else {
            alert('保存失败: ' + result.error);
        }
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
}

// 绑定执行选股按钮
document.getElementById('run-selection-btn').addEventListener('click', runSelection);

// 点击弹窗外部关闭弹窗
document.getElementById('stock-modal').addEventListener('click', (e) => {
    if (e.target.id === 'stock-modal') {
        closeModal();
    }
});

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
});
