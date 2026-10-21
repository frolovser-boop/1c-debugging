from setuptools import setup, find_packages

setup(
    name="onec-debug",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "onec-debug = onec_debug.cli:main",
        ],
    },
)
