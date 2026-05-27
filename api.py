"""
Altcoin Nexus - 一体式 Web 入口
单端口服务，不对外暴露
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from web.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
