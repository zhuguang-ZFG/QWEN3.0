"""
g4f API 服务器启动脚本
设置代理环境变量后启动 g4f OpenAI 兼容 API
端口: 4503
"""
import os
import sys

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7897'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7897'
os.environ['ALL_PROXY'] = 'http://127.0.0.1:7897'

sys.argv = ['g4f', '--port', '4503', '--proxy', 'http://127.0.0.1:7897']

from g4f.cli import main

main()
