#!/usr/bin/env python3

import pathlib
import subprocess
import sys

tests = list(map(str, pathlib.Path("tests").glob("*.py")))

if not tests:
    raise ValueError("No tests found!")

subprocess.check_call((sys.executable, "-m", "unittest", *tests))

