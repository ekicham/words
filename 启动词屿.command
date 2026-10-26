#!/bin/zsh
cd -- "$(dirname -- "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  print "请先安装 Python 3.9 或更高版本：https://www.python.org/downloads/"
  read "?按回车关闭"
  exit 1
fi
python3 app.py --open
