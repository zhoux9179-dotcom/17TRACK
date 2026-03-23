import os, sys
sys.path.insert(0, r"d:\【周】17TRACK\0310 AI 可读文件\07_项目代码\热点追踪器")
os.environ['DEEPSEEK_API_KEY'] = 'sk-516b1fd3acf441f9ba974daaff44a88f'
os.environ['SENDER_EMAIL'] = '286590856@qq.com'
os.environ['SENDER_PASSWORD'] = 'shzwokuplwagbjad'
os.environ['SMTP_HOST'] = 'smtp.qq.com'
os.environ['SMTP_PORT'] = '587'

from pathlib import Path
import mailer

html_path = Path(r"d:\【周】17TRACK\0310 AI 可读文件\07_项目代码\热点追踪器\输出\热点日报_2026-03-20.html")
html_content = html_path.read_text(encoding='utf-8')
result = mailer.send_report(html_content, '2026年03月20日', recipient='286590856@qq.com')
print('发送结果:', result)
