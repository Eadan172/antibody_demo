#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""旧入口。转交给仓库根目录的 run_workflow.py。"""

import os
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    script = root / "run_workflow.py"
    os.chdir(root)
    os.execv(sys.executable, [sys.executable, str(script), *sys.argv[1:]])


if __name__ == "__main__":
    main()
