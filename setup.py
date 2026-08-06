#!/usr/bin/env python3
import sys
import glob
from setuptools import setup, find_packages

# Check Python version: support 3.8 to 3.11
if sys.version_info < (3, 8) or sys.version_info >= (3, 12):
    sys.exit("This package requires Python >=3.8 and <3.12")

# Read long description safely
def read_long_description():
    try:
        with open("README.md", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "ViOTUcluster: A high-speed pipeline for viromic analysis"

setup(
    name="viotucluster",
    version="0.6.0",
    packages=find_packages(),
    include_package_data=True,
    # Exclude the old Bash entry points to avoid conflict with new Python entry_points
    scripts=[f for f in glob.glob("Modules/*") if not f.endswith("ViOTUcluster") and not f.endswith("ViOTUcluster_AllinOne")],
    entry_points={
        'console_scripts': [
            'ViOTUcluster=ViOTUcluster.viotucluster_cli:main',
            'ViOTUcluster_AllinOne=ViOTUcluster.viotucluster_allinone_cli:main',
        ],
    },
    license="GPL-2.0",
    license_files=["LICENSE"],
    python_requires=">=3.8, <3.12",
    install_requires=[
        "biopython>=1.79",
        "pandas>=1.3.0",
        "numpy",
        "packaging",
    ],
    author="Sihang Liu",
    author_email="liusihang@tongji.edu.cn",
    description="ViOTUcluster: A high-speed, all-in-one solution for viromic analysis",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    package_data={'': ['Modules/*', 'ViOTUcluster/*']},
    url="https://github.com/liusihang/ViOTUcluster",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
    keywords="viromics, metagenomics, viral genomics, bioinformatics, vOTU",
)
