#!/bin/zsh
set -e
cd "${0:A:h}"
.venv/bin/python run.py backup
read -k 1 '?按任意键关闭…'
