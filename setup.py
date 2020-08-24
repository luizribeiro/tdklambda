from setuptools import setup, find_packages
from os import path

here: str = path.abspath(path.dirname(__file__))

with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="labby",
    version="0.0.1",
    description="An utility for controlling laboratory equipment",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/luizribeiro/labby",
    author="Luiz Ribeiro",
    author_email="luizribeiro@gmail.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    keywords="lab automation, laboratory, instruments, experiments, science",
    packages=find_packages(exclude=["contrib", "docs", "tests"]),
    python_requires=">=3.7",
    install_requires=[
        "cffi==1.14.2",
        "mashumaro==1.12",
        "msgpack==1.0.0",
        "mypy-extensions==0.4.3",
        "numpy==1.19.1; python_version >= '3.6'",
        "pandas==1.1.0",
        "pycparser==2.20; python_version >= '2.7' and python_version not in '3.0, 3.1, 3.2, 3.3'",
        "pynng==0.5.0",
        "pyre-extensions==0.0.18",
        "pyserial==3.4",
        "python-dateutil==2.8.1; python_version >= '2.7' and python_version not in '3.0, 3.1, 3.2, 3.3'",
        "pytz==2020.1",
        "pyyaml==5.3.1",
        "ruamel.yaml==0.16.10",
        "ruamel.yaml.clib==0.2.0; python_version < '3.9' and platform_python_implementation == 'CPython'",
        "six==1.15.0; python_version >= '2.7' and python_version not in '3.0, 3.1, 3.2, 3.3'",
        "sniffio==1.1.0; python_version >= '3.5'",
        "strictyaml==1.1.0",
        "typed-argument-parser==1.5.4",
        "typing-extensions==3.7.4.3",
        "typing-inspect==0.6.0",
        "wasabi==0.7.1",
    ],
    dependency_links=[],
    project_urls={
        "Bug Reports": "https://github.com/luizribeiro/labby/issues",
        "Source": "https://github.com/luizribeiro/labby/",
    },
    entry_points={"console_scripts": ["labby=labby.cli:main"]},
)
