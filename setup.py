from setuptools import setup, find_packages

setup(
    name="bashgpt",
    version="0.1",
    packages=find_packages(),
    install_requires=["cs50", "openai", "anthropic", "simpleaudio", "pyaudio", "wave"],
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
