#!/bin/zsh
set -e
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  echo '请先双击 install.command 安装。'
  read -k 1 '?按任意键关闭…'
  exit 1
fi
exec .venv/bin/python run.py serve
