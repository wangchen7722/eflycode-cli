from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="echo-ai",
    version="0.1.0",
    description="An AI-powered coding assistant",
    author="Echo Team",
    packages=find_packages(),
    install_requires=requirements,
    package_data={
        "echo": [
            "prompt/prompts/**/*.prompt"
        ]
    },
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "echoai=echo.main:main",
        ],
    },
    python_requires=">=3.11",
)