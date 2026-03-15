from setuptools import find_packages, setup


setup(
    name="cheri",
    version="1.0.0",
    packages=find_packages(include=["cheri_cloud_cli", "cheri_cloud_cli.*"]),
    python_requires=">=3.9",
    install_requires=["click>=8.1", "requests>=2.31", "rich>=13.0"],
    entry_points={
        "console_scripts": [
            "cheri=cheri_cloud_cli.cli:main",
        ]
    },
)
