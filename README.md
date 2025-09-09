<p align="center"> 
    <br>
        <img src="assets/logo.png" width="400"/>
    <br>
<p>
<br>
<p align="center">
    <a href="https://github.com/teamunitlab/unitlab-sdk">
        <img alt="Downloads" src="https://img.shields.io/pypi/dm/unitlab">
    </a>
</p>

[Unitlab.ai](https://unitlab.ai/) is an AI-driven data annotation platform that automates the collection of raw data, facilitating collaboration with human annotators to produce highly accurate labels for your machine learning models. With our service, you can optimize work efficiency, improve data quality, and reduce costs.

![](https://github.com/teamunitlab/unitlab-sdk/blob/main/assets/unitlabDoc.png)

## Installation
To get started with the Unitlab.ai CLI/Python SDK, you'll need to install it using pip:

`pip install --upgrade unitlab`

Once you have successfully installed the Unitlab package, you can conveniently handle all projects using the terminal.

[This tutorial](https://docs.unitlab.ai/cli-python-sdk/unitlab-cli) walks you through the most common CLI commands.

## Quickstart 
Follow [the quickstart guide for the Python SDK](https://docs.unitlab.ai/cli-python-sdk/unitlab-python-sdk).

## CLI Commands

### Agent Commands

The agent module provides commands for running device agents with Jupyter, SSH tunnels, and metrics reporting.

#### Run Agent

Run a full device agent that sets up Jupyter notebooks, SSH tunnels, and system metrics reporting:

```bash
unitlab agent run --api-key YOUR_API_KEY [OPTIONS]
```

**Options:**
- `--api-key` (required): Your Unitlab API key

**Example:**
```bash
# Run with auto-generated device ID
unitlab agent run  your-api-key-here



The agent will:
- Initialize Jupyter notebook server
- Set up SSH tunnels for remote access
- Collect and report system metrics
- Handle graceful shutdown on interruption

## Documentation 
[The documentation](https://docs.unitlab.ai/) provides comprehensive instructions on how to utilize the Unilab SDK effectively.


## More about Unitlab
To learn more about our platform and Unitlab's products, please [visit our website](https://unitlab.ai/).

