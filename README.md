<p align="center">
    <br>
        <img src="https://unitlab-storage.s3.us-east-2.amazonaws.com/Logo.png" width="400"/>
    <br>
<p>

<p align="center">
    <a href="https://pypi.org/project/unitlab/">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/unitlab">
    </a>
    <a href="https://pypi.org/project/unitlab/">
        <img alt="Python" src="https://img.shields.io/pypi/pyversions/unitlab">
    </a>
    <a href="https://github.com/teamunitlab/unitlab-sdk">
        <img alt="Downloads" src="https://img.shields.io/pypi/dm/unitlab">
    </a>
    <a href="https://github.com/teamunitlab/unitlab-sdk/blob/main/LICENSE.md">
        <img alt="License" src="https://img.shields.io/pypi/l/unitlab">
    </a>
</p>

[Unitlab.ai](https://unitlab.ai/) is an AI-driven data annotation platform that automates the collection of raw data, facilitating collaboration with human annotators to produce highly accurate labels for your machine learning models. With our service, you can optimize work efficiency, improve data quality, and reduce costs.

![](https://unitlab-storage.s3.us-east-2.amazonaws.com/unitlab.png)

# Unitlab Python SDK

Python SDK and CLI for the [Unitlab.ai](https://unitlab.ai/) data annotation platform. Manage projects, upload data, and download datasets programmatically or from the command line.

## Installation

```bash
pip install --upgrade unitlab
```

Requires Python 3.10+.

## Configuration

Get your API key from [unitlab.ai](https://unitlab.ai/) and configure the CLI:

```bash
# Set API key
unitlab configure --api-key YOUR_API_KEY

# Set a custom API URL
unitlab configure --api-url https://api.unitlab.ai

# Set both at once
unitlab configure --api-key YOUR_API_KEY --api-url https://api.unitlab.ai
```

Or set environment variables:

```bash
export UNITLAB_API_KEY=YOUR_API_KEY

# Optional: point to a custom API server (e.g. self-hosted)
export UNITLAB_API_URL=https://api.unitlab.ai
```

## Python SDK

```python
from unitlab import UnitlabClient

# Initialize with an explicit key
client = UnitlabClient(api_key="YOUR_API_KEY")

# Or read from UNITLAB_API_KEY env var / config file
client = UnitlabClient()
```

The client can also be used as a context manager:

```python
with UnitlabClient() as client:
    projects = client.projects()
```

### Projects

```python
# List all projects
projects = client.projects()

# Get project details
project = client.project("PROJECT_ID")

# Get project members
members = client.project_members("PROJECT_ID")
```

### Upload data

```python
client.project_upload_data(
    project_id="PROJECT_ID",
    directory="./images",
)
```

Additional options for specific project types:

```python
# Text projects
client.project_upload_data("PROJECT_ID", "./docs", sentences_per_chunk=10)

# Video projects
client.project_upload_data("PROJECT_ID", "./videos", fps=30.0)
```

### Datasets

```python
# List all datasets
datasets = client.datasets()

# Download annotations (COCO, YOLOv8, YOLOv5, etc.)
path = client.dataset_download("DATASET_ID", export_type="COCO", split_type="train")

# Download raw files
folder = client.dataset_download_files("DATASET_ID")
```

## CLI

### Projects

```bash
# List projects
unitlab project list

# Project details
unitlab project detail PROJECT_ID

# Project members
unitlab project members PROJECT_ID

# Upload data to a project
unitlab project upload PROJECT_ID --directory ./images
```

### Datasets

```bash
# List datasets
unitlab dataset list

# Download annotations
unitlab dataset download DATASET_ID --export-type COCO --split-type train

# Download raw files
unitlab dataset download DATASET_ID --download-type files
```


## Documentation

See the [full documentation](https://docs.unitlab.ai/) for detailed guides:

- [CLI reference](https://docs.unitlab.ai/cli-python-sdk/unitlab-cli)
- [Python SDK quickstart](https://docs.unitlab.ai/cli-python-sdk/unitlab-python-sdk)

## License

[MIT](LICENSE.md)
