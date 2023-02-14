from setuptools import setup, find_packages


setup(
    name='unitlab',
    version='1.5.0',
    license='MIT',
    author="Unitlab Inc.",
    author_email='team@unitlab.ai',
    packages=find_packages('src'),
    include_package_data = True,
    package_data = {
    'static': ['*'],
    'Potato': ['*.so']
    },
    classifiers=[
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    package_dir={'': 'src'},
    url='https://github.com/teamunitlab/unitlab-sdk',
    keywords='unitlab-sdk',
    install_requires=[
          'aiohttp',
      ],
    entry_points={
        "console_scripts": [
            "ulab=unitlab.run:main"
        ],
    },

)
