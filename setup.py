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
    description="amdfan control",
    long_description=readme,
    package_data={'': ['amdfan.service']},
    include_package_data=True,
    install_requires=[
        "pyyaml",
        "numpy",
        "rich",
        "click",
    ],
    entry_points="""
        [console_scripts]
        amdfan=amdfan.controller:main
    """,
)
