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
    
    def send_markdown(self, title, content):
        """
        发送 Markdown 格式消息
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
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": content
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
                    print("✓ 钉钉通知发送成功")
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
    
    def format_stock_results(self, results, stock_names=None):
        """
        格式化选股结果为 Markdown (适配手机端)
        :param results: {strategy_name: [signals]} 格式的结果
        :param stock_names: {code: name} 股票名称字典
        """
        if stock_names is None:
            stock_names = {}
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        content = f"📊 A股量化选股结果\n\n"
        content += f"⏰ 时间: {now}\n"
        content += "━" * 30 + "\n\n"
        
        total_signals = 0
        
        for strategy_name, signals in results.items():
            content += f"🎯 {strategy_name}\n\n"
            
            if not signals:
                content += "暂无选股信号\n\n"
                continue
            
            total_signals += len(signals)
            
            for i, signal in enumerate(signals, 1):
                code = signal['code']
                name = signal.get('name', stock_names.get(code, '未知'))
                
                for s in signal['signals']:
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
            
            content += "━" * 30 + "\n\n"
        
        content += f"📈 共选出 {total_signals} 只股票\n\n"
        content += "⚠️ 提示: 以上结果仅供参考，不构成投资建议"
        
        return content
    
    def send_text(self, content):
        """
        发送纯文本消息（手机端兼容性更好）
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
                    print("✓ 钉钉通知发送成功")
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

    def send_stock_selection(self, results, stock_names=None):
        """
        发送选股结果到钉钉
        """
        content = self.format_stock_results(results, stock_names)
        # 优先使用纯文本格式，手机端兼容性更好
        return self.send_text(content)


# 为了处理 pandas 导入
import pandas as pd
