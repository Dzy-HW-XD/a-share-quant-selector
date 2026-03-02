"""
钉钉群通知模块
"""
import requests
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime


class DingTalkNotifier:
    """钉钉通知器"""
    
    def __init__(self, webhook_url=None, secret=None):
        self.webhook_url = webhook_url
        self.secret = secret
    
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
    
    def _send_single_markdown(self, title, content, part_info=""):
        """
        发送单条 Markdown 格式消息
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
        发送选股结果到钉钉
        :param results: 选股结果
        :param stock_names: 股票名称字典
        :param category_filter: 分类筛选，用于显示在通知中
        """
        content = self.format_stock_results(results, stock_names, category_filter)
        # 优先使用纯文本格式，手机端兼容性更好
        return self.send_text(content)


# 为了处理 pandas 导入
import pandas as pd
