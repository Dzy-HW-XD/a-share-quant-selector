"""
钉钉群通知模块
"""
import os
import requests
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime
from pathlib import Path

# 导入K线图模块
try:
    # 优先使用快速版
    from utils.kline_chart_fast import generate_kline_chart_fast as generate_kline_chart
    KLINE_CHART_AVAILABLE = True
    print("✓ 使用快速K线图生成")
except ImportError:
    try:
        from utils.kline_chart import generate_kline_chart
        KLINE_CHART_AVAILABLE = True
    except ImportError:
        KLINE_CHART_AVAILABLE = False
        print("警告: K线图模块未安装，图片功能不可用")


class DingTalkNotifier:
    """钉钉通知器"""
    
    def __init__(self, webhook_url=None, secret=None):
        self.webhook_url = webhook_url
        self.secret = secret
        self._last_send_time = 0
        self._min_interval = 1.0  # 最小发送间隔1秒，避免触发限速（660026错误）
    
    def _generate_sign(self):
        """生成钉钉签名"""
        if not self.secret:
            return "", ""

        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{self.secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    def _send_request(self, data: dict) -> bool:
        """发送HTTP请求到钉钉（带速率限制）"""
        # 速率限制：确保最小间隔
        elapsed = time.time() - self._last_send_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        
        timestamp, sign = self._generate_sign()

        if self.secret:
            webhook_url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
        else:
            webhook_url = self.webhook_url

        try:
            response = requests.post(
                webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            # 更新最后发送时间
            self._last_send_time = time.time()

            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    return True
                else:
                    print(f"✗ 钉钉返回错误: {result}")
                    # 如果是限速错误，等待更长时间
                    if result.get('errcode') == 660026:
                        time.sleep(2)
                    return False
            else:
                print(f"✗ HTTP错误: {response.status_code}")
                return False

        except Exception as e:
            print(f"✗ 请求异常: {e}")
            return False
    
    def _send_single_markdown(self, title, content, part_info=""):
        """
        发送单条 Markdown 格式消息（带速率限制）
        """
        if not self.webhook_url:
            print("警告: 未配置钉钉 webhook")
            return False
        
        # 速率限制：确保最小间隔
        elapsed = time.time() - self._last_send_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        
        # 生成签名
        timestamp, sign = self._generate_sign()
        
        # 构建带签名的URL
        if self.secret:
            webhook_url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
        else:
            webhook_url = self.webhook_url
        
        # 添加分段信息到内容
        text = content
        if part_info:
            text = f"> {part_info}\n\n{text}"
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text
            }
        }
        
        try:
            response = requests.post(
                webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            # 更新最后发送时间
            self._last_send_time = time.time()
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    return True
                else:
                    print(f"✗ 钉钉发送失败: {result}")
                    # 如果是限速错误，等待更长时间
                    if result.get('errcode') == 660026:
                        time.sleep(2)
                    return False
            else:
                print(f"✗ HTTP错误: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ 发送异常: {e}")
            return False

    def send_markdown(self, title, content):
        """
        发送 Markdown 格式消息
        如果消息超过20000字节，自动分段发送
        """
        # 钉钉限制：消息体大小不超过20000字节
        MAX_SIZE = 18000  # 留足够余量（预留 ~2000 字节给 part_info 和 JSON 包装）
        
        # 计算内容字节数
        content_bytes = content.encode('utf-8')
        content_size = len(content_bytes)
        
        if content_size <= MAX_SIZE:
            # 单条发送
            if self._send_single_markdown(title, content):
                print("✓ 钉钉通知发送成功")
                return True
            return False
        
        # 需要分段发送
        print(f"消息大小 {content_size} 字节，超过限制，将分段发送...")
        
        # 按行分割内容
        lines = content.split('\n')
        parts = []
        current_part = []
        current_size = 0
        
        for line in lines:
            line_bytes = line.encode('utf-8')
            line_size = len(line_bytes) + 1  # +1 for newline
            
            # 处理超长行：如果单行超过限制，强制截断
            if line_size > MAX_SIZE:
                chunk_size = 15000
                for j in range(0, len(line_bytes), chunk_size):
                    chunk = line_bytes[j:j+chunk_size].decode('utf-8', errors='ignore')
                    if current_part:
                        parts.append('\n'.join(current_part))
                        current_part = []
                        current_size = 0
                    parts.append(chunk)
                continue
            
            if current_size + line_size > MAX_SIZE and current_part:
                # 当前部分已满，保存并开始新部分
                parts.append('\n'.join(current_part))
                current_part = [line]
                current_size = line_size
            else:
                current_part.append(line)
                current_size += line_size
        
        # 添加最后一部分
        if current_part:
            parts.append('\n'.join(current_part))
        
        # 分段发送（带重试）
        total_parts = len(parts)
        success_count = 0
        max_retries = 3
        
        for i, part in enumerate(parts, 1):
            part_info = f"📨 消息分段 ({i}/{total_parts})"
            
            # 重试机制
            for attempt in range(max_retries):
                if self._send_single_markdown(title, part, part_info):
                    success_count += 1
                    break
                else:
                    print(f"  第 {i}/{total_parts} 段发送失败，重试 {attempt + 1}/{max_retries}...")
                    time.sleep(1 + attempt)
            
            time.sleep(1)  # 段间延迟增加到 1 秒
        
        if success_count == total_parts:
            print(f"✓ 钉钉通知分段发送成功 ({total_parts}条)")
            return True
        else:
            print(f"✗ 部分消息发送失败 ({success_count}/{total_parts})")
            return False
    
    def format_stock_results(self, results, stock_names=None, category_filter='all'):
        """
        格式化选股结果为 Markdown (适配手机端)
        :param results: {strategy_name: [signals]} 格式的结果
        :param stock_names: {code: name} 股票名称字典
        :param category_filter: 分类筛选，'all'表示全部
        """
        if stock_names is None:
            stock_names = {}
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 分类名称映射
        category_names = {
            'bowl_center': '🥣 回落碗中',
            'near_duokong': '📊 靠近多空线',
            'near_short_trend': '📈 靠近短期趋势线'
        }
        
        # 筛选标签
        filter_label = "全部" if category_filter == 'all' else category_names.get(category_filter, category_filter)
        
        content = f"📊 A股量化选股结果\n\n"
        content += f"⏰ 时间: {now}\n"
        content += f"🔍 筛选: {filter_label}\n"
        content += "━" * 30 + "\n\n"
        
        total_signals = 0
        # 按分类统计
        category_count = {'bowl_center': 0, 'near_duokong': 0, 'near_short_trend': 0}
        
        for strategy_name, signals in results.items():
            content += f"🎯 {strategy_name}\n\n"
            
            if not signals:
                content += "暂无选股信号\n\n"
                continue
            
            # 按分类分组，并根据 category_filter 过滤
            category_groups = {}
            for signal in signals:
                for s in signal['signals']:
                    cat = s.get('category', 'unknown')
                    # 如果指定了分类筛选，只保留对应分类
                    if category_filter != 'all' and cat != category_filter:
                        continue
                    if cat not in category_groups:
                        category_groups[cat] = []
                    category_groups[cat].append((signal, s))
                    category_count[cat] = category_count.get(cat, 0) + 1
            
            total_signals += sum(len(group) for group in category_groups.values())
            
            # 按优先级顺序显示分类
            display_order = ['bowl_center', 'near_duokong', 'near_short_trend']
            # 如果指定了分类，只显示该分类
            if category_filter != 'all' and category_filter in display_order:
                display_order = [category_filter]
            
            for cat in display_order:
                if cat in category_groups:
                    group_signals = category_groups[cat]
                    cat_name = category_names.get(cat, cat)
                    content += f"{cat_name} ({len(group_signals)}只)\n"
                    content += "-" * 20 + "\n"
                    
                    for i, (signal, s) in enumerate(group_signals, 1):
                        code = signal['code']
                        name = signal.get('name', stock_names.get(code, '未知'))
                        close = s.get('close', '-')
                        j_val = s.get('J', '-')
                        key_date = s.get('key_candle_date', '-')
                        if isinstance(key_date, pd.Timestamp):
                            key_date = key_date.strftime("%m-%d")
                        reasons = ' '.join(s.get('reasons', []))
                        
                        # 手机端友好的格式
                        content += f"{i}. {code} {name}\n"
                        content += f"   💰 价格: {close}  |  J值: {j_val}\n"
                        content += f"   📅 关键K线: {key_date}\n"
                        content += f"   📝 {reasons}\n\n"
                    
                    content += "\n"
            
            content += "━" * 30 + "\n\n"
        
        # 显示分类统计
        content += "📊 分类统计:\n"
        content += f"   🥣 回落碗中: {category_count.get('bowl_center', 0)} 只\n"
        content += f"   📊 靠近多空线: {category_count.get('near_duokong', 0)} 只\n"
        content += f"   📈 靠近短期趋势线: {category_count.get('near_short_trend', 0)} 只\n"
        content += f"   📈 共选出: {total_signals} 只\n\n"
        content += "⚠️ 提示: 以上结果仅供参考，不构成投资建议"
        
        return content
    
    def _send_single_text(self, content, part_info=""):
        """
        发送单条纯文本消息
        """
        if not self.webhook_url:
            print("警告: 未配置钉钉 webhook")
            return False
        
        # 生成签名
        timestamp, sign = self._generate_sign()
        
        # 构建带签名的URL
        if self.secret:
            webhook_url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
        else:
            webhook_url = self.webhook_url
        
        # 添加分段信息
        if part_info:
            content = f"{part_info}\n{content}"
        
        data = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }
        
        try:
            response = requests.post(
                webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    return True
                else:
                    print(f"✗ 钉钉发送失败: {result}")
                    return False
            else:
                print(f"✗ HTTP错误: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ 发送异常: {e}")
            return False
    
    def send_text(self, content):
        """
        发送纯文本消息（手机端兼容性更好）
        如果消息超过20000字节，自动分段发送
        """
        # 钉钉限制：消息体大小不超过20000字节
        MAX_SIZE = 18000  # 留足够余量（预留 ~2000 字节给 part_info 和 JSON 包装）
        
        # 计算内容字节数
        content_bytes = content.encode('utf-8')
        content_size = len(content_bytes)
        
        if content_size <= MAX_SIZE:
            # 单条发送
            if self._send_single_text(content):
                print("✓ 钉钉通知发送成功")
                return True
            return False
        
        # 需要分段发送
        print(f"消息大小 {content_size} 字节，超过限制，将分段发送...")
        
        # 按行分割内容
        lines = content.split('\n')
        parts = []
        current_part = []
        current_size = 0
        
        for line in lines:
            line_bytes = line.encode('utf-8')
            line_size = len(line_bytes) + 1  # +1 for newline
            
            # 处理超长行：如果单行超过限制，强制截断
            if line_size > MAX_SIZE:
                # 将超长行分段（每段约 15000 字符）
                chunk_size = 15000
                for j in range(0, len(line_bytes), chunk_size):
                    chunk = line_bytes[j:j+chunk_size].decode('utf-8', errors='ignore')
                    if current_part:
                        parts.append('\n'.join(current_part))
                        current_part = []
                        current_size = 0
                    parts.append(chunk)  # 单独作为一段
                continue
            
            if current_size + line_size > MAX_SIZE and current_part:
                # 当前部分已满，保存并开始新部分
                parts.append('\n'.join(current_part))
                current_part = [line]
                current_size = line_size
            else:
                current_part.append(line)
                current_size += line_size
        
        # 添加最后一部分
        if current_part:
            parts.append('\n'.join(current_part))
        
        # 分段发送（带重试）
        total_parts = len(parts)
        success_count = 0
        max_retries = 3
        
        for i, part in enumerate(parts, 1):
            part_info = f"📨 消息分段 ({i}/{total_parts})"
            
            # 重试机制
            for attempt in range(max_retries):
                if self._send_single_text(part, part_info):
                    success_count += 1
                    break
                else:
                    print(f"  第 {i}/{total_parts} 段发送失败，重试 {attempt + 1}/{max_retries}...")
                    time.sleep(1 + attempt)  # 递增延迟
            
            time.sleep(1)  # 段间延迟增加到 1 秒，避免限流
        
        if success_count == total_parts:
            print(f"✓ 钉钉通知分段发送成功 ({total_parts}条)")
            return True
        else:
            print(f"✗ 部分消息发送失败 ({success_count}/{total_parts})")
            return False

    def send_stock_selection(self, results, stock_names=None, category_filter='all'):
        """
        发送选股结果到钉钉（按分类单独发送，避免截断）
        :param results: 选股结果
        :param stock_names: 股票名称字典
        :param category_filter: 分类筛选
        """
        if stock_names is None:
            stock_names = {}
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        category_names = {
            'bowl_center': '🥣 回落碗中',
            'near_duokong': '📊 靠近多空线',
            'near_short_trend': '📈 靠近短期趋势线'
        }
        
        total_sent = 0
        total_failed = 0
        
        # 先发送汇总消息
        summary = f"📊 A股量化选股结果\n⏰ {now}\n"
        if category_filter != 'all':
            summary += f"🔍 筛选: {category_names.get(category_filter, category_filter)}\n"
        summary += "━" * 20 + "\n\n"
        
        # 统计各分类数量
        category_count = {'bowl_center': 0, 'near_duokong': 0, 'near_short_trend': 0}
        for strategy_name, signals in results.items():
            for signal in signals:
                for s in signal['signals']:
                    cat = s.get('category', 'unknown')
                    if category_filter == 'all' or cat == category_filter:
                        category_count[cat] = category_count.get(cat, 0) + 1
        
        summary += f"🥣 回落碗中: {category_count.get('bowl_center', 0)} 只\n"
        summary += f"📊 靠近多空线: {category_count.get('near_duokong', 0)} 只\n"
        summary += f"📈 靠近短期趋势线: {category_count.get('near_short_trend', 0)} 只\n"
        total = sum(category_count.values())
        summary += f"📈 共选出: {total} 只\n\n"
        summary += "详细列表见下方消息 👇"
        
        if self.send_text(summary):
            total_sent += 1
        else:
            total_failed += 1
        
        time.sleep(1)  # 间隔1秒
        
        # 按分类单独发送详细列表
        for strategy_name, signals in results.items():
            # 按分类分组
            category_groups = {}
            for signal in signals:
                for s in signal['signals']:
                    cat = s.get('category', 'unknown')
                    if category_filter != 'all' and cat != category_filter:
                        continue
                    if cat not in category_groups:
                        category_groups[cat] = []
                    category_groups[cat].append((signal, s))
            
            # 按优先级顺序发送
            for cat in ['bowl_center', 'near_duokong', 'near_short_trend']:
                if cat not in category_groups or not category_groups[cat]:
                    continue
                
                group = category_groups[cat]
                cat_name = category_names.get(cat, cat)
                
                # 构建该分类的消息
                content = f"{cat_name} ({len(group)}只)\n"
                content += "━" * 20 + "\n\n"
                
                for i, (signal, s) in enumerate(group, 1):
                    code = signal['code']
                    name = signal.get('name', stock_names.get(code, '未知'))
                    close = s.get('close', '-')
                    j_val = s.get('J', '-')
                    key_date = s.get('key_candle_date', '-')
                    if isinstance(key_date, pd.Timestamp):
                        key_date = key_date.strftime("%m-%d")
                    
                    # 紧凑格式
                    content += f"{i}. {code} {name}\n"
                    content += f"   价格:{close} J:{j_val} 关键K:{key_date}\n\n"
                    
                    # 每20只分段发送，避免单条过长
                    if i % 20 == 0 and i < len(group):
                        if self.send_text(content):
                            total_sent += 1
                        else:
                            total_failed += 1
                        time.sleep(1)
                        content = f"{cat_name} (续 {i+1}-{len(group)}只)\n"
                        content += "━" * 20 + "\n\n"
                
                # 发送该分类的最后一段
                if content.strip():
                    if self.send_text(content):
                        total_sent += 1
                    else:
                        total_failed += 1
                    time.sleep(1)
        
        # 发送结束提示
        footer = f"⚠️ 提示: 以上结果仅供参考\n共 {total} 只股票"
        if self.send_text(footer):
            total_sent += 1
        else:
            total_failed += 1
        
        print(f"✓ 钉钉通知发送完成 ({total_sent}条成功, {total_failed}条失败)")
        return total_failed == 0

    def send_image(self, image_path: str, title: str = "K线图") -> bool:
        """
        发送图片到钉钉（使用markdown格式嵌入图片URL）
        注：Webhook机器人不支持直接base64图片，需要先上传图片获取URL
        临时方案：将图片转为base64 data URL（部分钉钉客户端支持）

        Args:
            image_path: 图片文件路径
            title: 消息标题

        Returns:
            bool: 发送是否成功
        """
        if not self.webhook_url:
            print("警告: 未配置钉钉 webhook")
            return False

        if not Path(image_path).exists():
            print(f"✗ 图片文件不存在: {image_path}")
            return False

        try:
            # 读取图片
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # 转为base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # 检查大小（钉钉限制约2MB）
            if len(image_data) > 2 * 1024 * 1024:
                print(f"⚠️ 图片超过2MB，可能发送失败")

            # 构建data URL（markdown格式）
            # 使用png格式（K线图保存为png）
            data_url = f"data:image/png;base64,{image_base64}"

            # 使用markdown格式发送图片
            # 钉钉markdown支持data URL图片
            markdown_text = f"### {title}\n\n![K线图]({data_url})"

            data = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": markdown_text
                }
            }

            # 发送
            success = self._send_request(data)

            # 发送成功后删除本地图片
            if success:
                import os
                os.remove(image_path)
                print(f"✓ 已删除本地图片: {image_path}")

            return success

        except Exception as e:
            print(f"✗ 图片发送失败: {e}")
            return False

    def _format_stock_info_message(self, stock_code, stock_name, category, params, signal):
        """
        格式化股票信息文字消息
        
        Returns:
            str: 格式化的Markdown消息
        """
        category_names = {
            'bowl_center': '🥣 回落碗中',
            'near_duokong': '📊 靠近多空线',
            'near_short_trend': '📈 靠近短期趋势线'
        }
        category_name = category_names.get(category, category)
        
        # 格式化参数
        cap = params.get('CAP', 4000000000)
        cap_display = f"{cap/1e8:.0f}亿" if cap >= 1e8 else f"{cap/1e4:.0f}万"
        
        # 获取信号数据
        close = signal.get('close', '-')
        j_val = signal.get('J', '-')
        key_date = signal.get('key_candle_date', '-')
        if hasattr(key_date, 'strftime'):
            key_date = key_date.strftime("%m-%d")
        reasons = ' '.join(signal.get('reasons', []))
        
        message = f"""### 📊 {stock_code} {stock_name}

**分类**: {category_name}
**价格**: {close} | **J值**: {j_val}
**关键K线日期**: {key_date}
**入选理由**: {reasons}

**K线图**:
"""
        return message

    def send_stock_selection_with_charts(
        self, 
        results, 
        stock_names=None, 
        category_filter='all',
        stock_data_dict=None,
        params=None,
        send_text_first: bool = True
    ):
        """
        发送选股结果（带K线图）到钉钉
        
        Args:
            results: 选股结果 {strategy_name: [signals]}
            stock_names: 股票名称字典 {code: name}
            category_filter: 分类筛选
            stock_data_dict: 股票数据字典 {code: DataFrame}，用于生成K线图
            params: 策略参数
            send_text_first: 是否先发送文字再发送图片（默认True，文字图片分离）
            
        Returns:
            bool: 发送是否成功
        """
        if not KLINE_CHART_AVAILABLE:
            print("⚠️ K线图模块不可用，发送普通文本消息")
            return self.send_stock_selection(results, stock_names, category_filter)
        
        if stock_names is None:
            stock_names = {}
        
        if params is None:
            params = {
                'N': 4,
                'M': 15,
                'CAP': 4000000000,
                'J_VAL': 30,
                'duokong_pct': 3,
                'short_pct': 2
            }
        
        # 先发送汇总消息
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        category_names = {
            'bowl_center': '🥣 回落碗中',
            'near_duokong': '📊 靠近多空线',
            'near_short_trend': '📈 靠近短期趋势线'
        }
        
        total_sent = 0
        total_failed = 0
        
        # 统计各分类数量
        category_count = {'bowl_center': 0, 'near_duokong': 0, 'near_short_trend': 0}
        chart_count = 0

        for strategy_name, signals in results.items():
            for signal in signals:
                for s in signal['signals']:
                    cat = s.get('category', 'unknown')
                    if category_filter == 'all' or cat == category_filter:
                        category_count[cat] = category_count.get(cat, 0) + 1
        
        # 发送汇总消息
        summary = f"🎯 BowlReboundStrategy:\n"
        summary += f"N: {params.get('N', 4)} (成交量倍数)\n"
        summary += f"M: {params.get('M', 15)} (回溯天数)\n"
        summary += f"CAP: {params.get('CAP', 4000000000)} (40亿市值门槛)\n"
        summary += f"J_VAL: {params.get('J_VAL', 30)} (J值上限)\n"
        summary += f"duokong_pct: {params.get('duokong_pct', 3)}\n"
        summary += f"short_pct: {params.get('short_pct', 2)}\n"
        summary += f"M1: {params.get('M1', 14)} (MA周期)\n"
        summary += f"M2: {params.get('M2', 28)} (MA周期)\n"
        summary += f"M3: {params.get('M3', 57)} (MA周期)\n"
        summary += f"M4: {params.get('M4', 114)} (MA周期)\n\n"
        
        summary += f"⏰ {now}\n"
        if category_filter != 'all':
            summary += f"🔍 筛选: {category_names.get(category_filter, category_filter)}\n"
        summary += "━" * 20 + "\n\n"
        summary += f"🥣 回落碗中: {category_count.get('bowl_center', 0)} 只\n"
        summary += f"📊 靠近多空线: {category_count.get('near_duokong', 0)} 只\n"
        summary += f"📈 靠近短期趋势线: {category_count.get('near_short_trend', 0)} 只\n"
        total = sum(category_count.values())
        summary += f"📈 共选出: {total} 只\n\n"
        
        if stock_data_dict:
            summary += "📈 正在为每只股票生成K线图...\n"
            if send_text_first:
                summary += "（文字说明与图片分离发送，节省流量）\n"
        else:
            summary += "详细列表见下方消息 👇"
        
        if self.send_text(summary):
            total_sent += 1
        else:
            total_failed += 1
        
        time.sleep(1)
        
        # 如果提供了股票数据，生成并发送K线图
        if stock_data_dict:
            print(f"📊 准备发送 {len(stock_data_dict)} 只股票的K线图...")
            for strategy_name, signals in results.items():
                print(f"  处理策略: {strategy_name}, {len(signals)} 只信号")
                for signal in signals:
                    code = signal['code']
                    name = signal.get('name', stock_names.get(code, '未知'))
                    
                    for s in signal['signals']:
                        cat = s.get('category', 'unknown')
                        if category_filter != 'all' and cat != category_filter:
                            continue
                        
                        # 获取股票数据
                        if code not in stock_data_dict:
                            print(f"  ⚠️ {code} 不在stock_data_dict中")
                            continue
                        
                        df = stock_data_dict[code]
                        if df.empty:
                            print(f"  ⚠️ {code} 数据为空")
                            continue
                        
                        try:
                            print(f"  📈 处理 {code} {name}...")
                            # 准备关键K线日期
                            key_date = s.get('key_candle_date')
                            key_dates = [key_date] if key_date else []
                            
                            if send_text_first:
                                # 先发送文字说明
                                info_message = self._format_stock_info_message(
                                    code, name, cat, params, s
                                )
                                cat_name = category_names.get(cat, cat)
                                title = f"{code} {name}"
                                print(f"    发送文字...")
                                self.send_markdown(title, info_message)
                                time.sleep(0.05)  # 减少延迟
                                
                                print(f"    生成K线图...")
                                t0 = time.time()
                                # 再生成无文字版本K线图
                                chart_path = generate_kline_chart(
                                    stock_code=code,
                                    stock_name=name,
                                    df=df,
                                    category=cat,
                                    params=params,
                                    key_candle_dates=key_dates,
                                    output_dir='/tmp/kline_charts',
                                    show_text=False,  # 无文字版本
                                    show_legend=True
                                )
                                t1 = time.time()
                                print(f"    生成K线图耗时: {t1-t0:.2f}秒")
                                
                                print(f"    发送图片...")
                                t0 = time.time()
                                # 发送图片（标题简化）
                                if self.send_image(chart_path, f"{code} K线图"):
                                    chart_count += 1
                                t1 = time.time()
                                print(f"    发送图片耗时: {t1-t0:.2f}秒")
                            else:
                                # 旧方式：生成带文字的K线图
                                chart_path = generate_kline_chart(
                                    stock_code=code,
                                    stock_name=name,
                                    df=df,
                                    category=cat,
                                    params=params,
                                    key_candle_dates=key_dates,
                                    output_dir='/tmp/kline_charts',
                                    show_text=True,
                                    show_legend=True
                                )
                                
                                # 发送图片信息
                                cat_name = category_names.get(cat, cat)
                                title = f"{code} {name} - {cat_name}"
                                if self.send_image(chart_path, title):
                                    chart_count += 1

                            time.sleep(0.1)  # 避免发送过快，减少延迟
                            
                        except Exception as e:
                            print(f"✗ 生成 {code} 的K线图失败: {e}")
                            continue
        
        # 发送普通文本详情（作为备份）
        text_result = self.send_stock_selection(results, stock_names, category_filter)

        print(f"\n✓ 已发送 {chart_count} 张K线图到钉钉")

        return text_result


# 为了处理 pandas 导入
import pandas as pd
