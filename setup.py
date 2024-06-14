from setuptools import setup, find_packages

setup(
    name="bashgpt",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "openai>=1.12.0", 
        "anthropic>=0.19.1", 
        "PyAudio>=0.2.13",
        "python-vlc>=3.0.20123",
        "google-generativeai>=0.6.0",
        "html2text>=2024.2.26",
        "PyMuPDF>=1.24.5"
        ],
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
