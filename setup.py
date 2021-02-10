from distutils.core import setup

from setuptools import find_packages

with open("README.md") as f:
    readme = f.read()


setup(
    name="amdfan",
    version="PROJECTVERSION",
    packages=find_packages(),
    url="https://github.com/mcgillij/amdfan",
    license="GPL-2.0",
    author="Jason McGillivray",
    author_email="mcgillivray.jason@gmail.com",
    maintainer="Jason McGillivray",
    maintainer_email="mcgillivray.jason@gmail.com",
    description="amdgpu fan controller",
    long_description=readme,
    install_requires=[
        "pyyaml",
        "numpy",
        "rich",
    ],
    entry_points="""
        [console_scripts]
        amdfan=amdfan.controller:main
    """,
)
