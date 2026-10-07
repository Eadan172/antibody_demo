#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""旧预测脚本。转交给 qsar_engine.py，避免在导入时读取不存在的模型。"""

import runpy
import sys
from pathlib import Path


if __name__ == "__main__":
    target = Path(__file__).with_name("qsar_engine.py")
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")
