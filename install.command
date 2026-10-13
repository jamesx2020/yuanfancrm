#!/bin/zsh
set -e
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python run.py init --name 管理员
echo '安装完成。双击 start.command 启动。'
read -k 1 '?按任意键关闭…'
