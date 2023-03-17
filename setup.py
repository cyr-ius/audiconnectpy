# -*- coding: utf-8 -*-
"""Setup package."""

import codecs
import os
import re

from setuptools import find_packages, setup

# Method for retrieving the version is taken from the setup.py of pip itself:
# https://github.com/pypa/pip/blob/master/setup.py
here = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    """Read file."""
    with codecs.open(os.path.join(here, *parts), "r") as fp:
        return fp.read()


def find_version(*file_paths):
    """Find version."""
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


# Get the long description from the README file
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()


setup(
    name="audiconnectpy",
    version="replace_by_workflow",
    packages=find_packages(),
    author="cyr-ius",
    author_email="cyr-ius@ipocus.net",
    description="Provides asynchronous authentication and access",
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=["aiohttp>=3.8.1", "voluptuous>=0.13.1", "beautifulsoup4>=4.11.2"],
    license="GPL-3",
    include_package_data=True,
    url="https://github.com/cyr-ius/audiconnectpy/tree/master/audiconnectpy",
    keywords=["connect", "async"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Framework :: AsyncIO",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Home Automation",
    ],
)
