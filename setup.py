from setuptools import find_packages, setup

setup(
    name="unitlab",
    version="1.9.3",
    license="MIT",
    author="Unitlab Inc.",
    author_email="team@unitlab.ai",
    packages=find_packages("src"),
    include_package_data=True,
    package_data={"static": ["*"], "Potato": ["*.so"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    package_dir={"": "src"},
    url="https://github.com/teamunitlab/unitlab-sdk",
    keywords="unitlab-sdk",
    install_requires=[
        "aiohttp",
        "numpy",
        "opencv-python",
        "Pillow",
        "requests",
        "tqdm",
        "typer",
    ],
    entry_points={
        "console_scripts": ["unitlab=unitlab.run:app"],
    },
)
