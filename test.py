#!/usr/bin/env python3

import pathlib
import subprocess
import sys

tests = list(map(str, pathlib.Path("tests").glob("*.py")))

if not tests:
    raise ValueError("No tests found!")

sys.exit(subprocess.call((sys.executable, "-m", "unittest", *tests)))

