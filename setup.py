from setuptools import setup, find_packages

setup(
    name="bashgpt",
    version="0.1",
    packages=find_packages(),
    install_requires=["cs50", "openai", "simpleaudio", "pathlib", "pyaudio", "wave"],
    entry_points={"console_scripts": ["dp=main:main"]}
)
