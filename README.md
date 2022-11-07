<p align="center">
    <br>
        <img src="assets/logo.aac4681.png" width="400"/>
    <br>
<p>
<br>
<p align="center">
    <a href="https://github.com/segments-ai/segments-ai/LICENSE">
        <img alt="GitHub" src="https://img.shields.io/github/license/segments-ai/segments-ai.svg?color=blue">
    </a>
    <!-- <a href="https://github.com/segments-ai/segments-ai/actions">
        <img alt="Tests" src="https://github.com/segments-ai/segments-ai/actions/workflows/tests.yml/badge.svg">
    </a> -->
    <a href="https://segments-python-sdk.readthedocs.io/en/latest/?badge=latest">
        <img alt="Documentation" src="https://readthedocs.org/projects/segments-python-sdk/badge/?version=latest">
    </a>
    <!-- <a href="https://github.com/segments-ai/segments-ai/releases">
        <img alt="GitHub release" src="https://img.shields.io/github/release/segments-ai/segments-ai.svg">
    </a> -->
    <a href="https://github.com/segments-ai/segments-ai/releases">
        <img alt="Downloads" src="https://img.shields.io/pypi/dm/segments-ai">
    </a>
</p>

Unitlab Inc. 

Easy and straightforward data annotation platform for any business or company to leverage AI models with powerful data. To achieve this, Unitlab provides the best service to rely on AI-powered tools and industry-level annotators with state-of-the-art models surpassing any open-source or alternative. Our mission is to ease and automate the platform for everybody. Unitlab serves a huge workspace to provide hiring labelers that make any scale of the projects. We aim to truly change the nature of our society for the better.

@axror please write more readme how to run etc.

## How to generate secure so files
python compile.py build_ext --inplace

## How to generate pip files

python setup.py sdist

## How to upload to pip clould
### [Note] change version to new

pip install twine

twine upload dist/*

Enter pip user & password
Done!