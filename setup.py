#!/usr/bin/env python
"""Setup script for neptun-api.

For most cases, install via:
    pip install -e .                  # core only
    pip install -e ".[survey]"        # with survey auto-fill (Playwright)
    pip install -e ".[dev]"           # with test dependencies
    pip install -e ".[all]"           # everything

Post-install for survey support:
    python -m playwright install chromium
"""
from setuptools import setup

if __name__ == "__main__":
    setup()
