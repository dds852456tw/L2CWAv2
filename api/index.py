import sys
import os

# 將專案根目錄加入 Python 搜尋路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import app

# Vercel Serverless Function 進入點
if __name__ == "__main__":
    app.run()
