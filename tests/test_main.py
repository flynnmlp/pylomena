#!/usr/bin/env python3

import pathlib
import subprocess
import sys


def main() -> None:
    this = pathlib.Path(__file__).name
    
    tests = [
        str(path)
        for path
        in pathlib.Path("tests").glob("*.py")
        if path.name != this
    ]
    
    if not tests:
        raise ValueError("No tests found!")
    
    sys.exit(subprocess.call((sys.executable, "-m", "unittest", *tests)))


if __name__ == "__main__":
    main()

