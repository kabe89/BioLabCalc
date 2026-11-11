#!/usr/bin/env python3
"""Helper script for building distributions and uploading to PyPI / TestPyPI using twine."""

import argparse
import subprocess
import sys
import os
import shutil
import glob

def clean_build_artifacts():
    for p in ["dist", "build"]:
        if os.path.exists(p):
            shutil.rmtree(p, ignore_errors=True)
    for pattern in ["*.egg-info", "src/*.egg-info"]:
        for match in glob.glob(pattern):
            if os.path.isdir(match):
                shutil.rmtree(match, ignore_errors=True)
            elif os.path.isfile(match):
                os.remove(match)

def run_cmd(cmd):
    print(f"--> Running: {cmd}")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"Error: command failed with return code {res.returncode}")
        sys.exit(res.returncode)

def main():
    parser = argparse.ArgumentParser(description="Build and publish BioLabCalc to PyPI.")
    parser.add_argument("--build", action="store_true", help="Build sdist and wheel")
    parser.add_argument("--check", action="store_true", help="Check dist package with twine")
    parser.add_argument("--test-pypi", action="store_true", help="Upload to TestPyPI")
    parser.add_argument("--pypi", action="store_true", help="Upload to production PyPI")
    args = parser.parse_args()

    # Default action if no args
    if not (args.build or args.check or args.test_pypi or args.pypi):
        args.build = True
        args.check = True

    if args.build:
        clean_build_artifacts()
        run_cmd(f"{sys.executable} setup.py sdist bdist_wheel")

    if args.check:
        run_cmd("twine check dist/*")

    if args.test_pypi:
        run_cmd("twine upload --repository testpypi dist/*")

    if args.pypi:
        run_cmd("twine upload dist/*")

if __name__ == "__main__":
    main()
