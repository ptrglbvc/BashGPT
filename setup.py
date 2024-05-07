from setuptools import setup, find_packages

setup(
    name="bashgpt",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "openai>=1.12.0", 
        "anthropic>=0.19.1", 
        "PyAudio>=0.2.13"],
    entry_points={"console_scripts": ["dp=bashgpt.main:main"]},
    data_files=[
        ("",[
                "bashgpt/history.db",
                "bashgpt/models.json", 
                "bashgpt/modes.json",
                "bashgpt/defaults.json"
            ]
        )
    ],
    include_package_data=True
)
