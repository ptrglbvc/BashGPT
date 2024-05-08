from setuptools import setup, find_packages

setup(
    name="bashgpt",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "openai>=1.12.0", 
        "anthropic>=0.19.1", 
        "PyAudio>=0.2.13"],
    entry_points={"console_scripts": 
        ["dp=bashgpt.main:main"]
        },
    data_files=[
        ("",[
                # "src/bashgpt/history.db",
                "src/bashgpt/models.json", 
                "src/bashgpt/modes.json",
                "src/bashgpt/defaults.json"
            ]
        )
    ],
    include_package_data=True
)
