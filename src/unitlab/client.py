import asyncio
import glob
import logging
import os
import urllib.parse
import aiofiles
import aiohttp
import requests
import tqdm
import socket
import subprocess
import signal
import re
import time
import threading
import psutil
from datetime import datetime, timezone
from .tunnel_config import CloudflareTunnel
from .utils import get_api_url, handle_exceptions


try:
    import GPUtil
    HAS_GPU = True
except ImportError:
    HAS_GPU = False


logger = logging.getLogger(__name__)

class UnitlabClient:
    """A client with a connection to the Unitlab.ai platform.

    Note:
        Please refer to the `Python SDK quickstart <https://docs.unitlab.ai/cli-python-sdk/unitlab-python-sdk>`__ for a full example of working with the Python SDK.

    First install the SDK.

    .. code-block:: bash

        pip install --upgrade unitlab

    Import the ``unitlab`` package in your python file and set up a client with an API key. An API key can be created on <https://unitlab.ai/>`__.

    .. code-block:: python

        from unitlab import UnitlabClient
        api_key = 'YOUR_API_KEY'
        client = UnitlabClient(api_key)

    Or store your Unitlab API key in your environment (``UNITLAB_API_KEY = 'YOUR_API_KEY'``):

    .. code-block:: python

        from unitlab import UnitlabClient
        client = UnitlabClient()

    Args:
        api_key: Your Unitlab.ai API key. If no API key given, reads ``UNITLAB_API_KEY`` from the environment. Defaults to :obj:`None`.
    Raises:
        :exc:`~unitlab.exceptions.AuthenticationError`: If an invalid API key is used or (when not passing the API key directly) if ``UNITLAB_API_KEY`` is not found in your environment.
    """

    def __init__(self, api_key, api_url=None):
        self.api_key = api_key
        self.api_url = api_url or get_api_url()
        self.api_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        self.api_session.mount("http://", adapter)
        self.api_session.mount("https://", adapter)
        
        # Device agent attributes (initialized when needed)
        self.device_id = None
        self.base_domain = None
        self.server_url = None
        self.hostname = socket.gethostname()
        self.tunnel_manager = None
        self.jupyter_url = None
        self.ssh_url = None
        self.jupyter_proc = None
        self.tunnel_proc = None
        self.jupyter_port = None
        self.running = True
        self.metrics_thread = None

    def close(self) -> None:
        """Close :class:`UnitlabClient` connections.

        You can manually close the Unitlab client's connections:

        .. code-block:: python

            client = UnitlabClient()
            client.projects()
            client.close()

        Or use the client as a context manager:

        .. code-block:: python

            with UnitlabClient() as client:
                client.projects()
        """
        self.api_session.close()

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()

    def _get_headers(self):
        return {"Authorization": f"Api-Key {self.api_key}"}

    @handle_exceptions
    def _get(self, endpoint):
        return self.api_session.get(
            urllib.parse.urljoin(self.api_url, endpoint), headers=self._get_headers()
        )

    @handle_exceptions
    def _post(self, endpoint, data=None):
        return self.api_session.post(
            urllib.parse.urljoin(self.api_url, endpoint),
            json=data or {},
            headers=self._get_headers(),
        )

    def projects(self, pretty=0):
        return self._get(f"/api/sdk/projects/?pretty={pretty}")

    def project(self, project_id, pretty=0):
        return self._get(f"/api/sdk/projects/{project_id}/?pretty={pretty}")

    def project_members(self, project_id, pretty=0):
        return self._get(f"/api/sdk/projects/{project_id}/members/?pretty={pretty}")

    def project_upload_data(self, project_id, directory, batch_size=100):
        if not os.path.isdir(directory):
            raise ValueError(f"Directory {directory} does not exist")

        files = [
            file
            for files_list in (
                glob.glob(os.path.join(directory, "") + extension)
                for extension in ["*jpg", "*png", "*jpeg", "*webp"]
            )
            for file in files_list
        ]
        filtered_files = []
        for file in files:
            file_size = os.path.getsize(file) / 1024 / 1024
            if file_size > 6:
                logger.warning(
                    f"File {file} is too large ({file_size:.4f} megabytes) skipping, max size is 6 MB"
                )
                continue
            filtered_files.append(file)

        num_files = len(filtered_files)
        num_batches = (num_files + batch_size - 1) // batch_size

        async def post_file(session: aiohttp.ClientSession, file: str, project_id: str):
            async with aiofiles.open(file, "rb") as f:
                form_data = aiohttp.FormData()
                form_data.add_field("project", project_id)
                form_data.add_field(
                    "file", await f.read(), filename=os.path.basename(file)
                )
                try:
                    await asyncio.sleep(0.1)
                    async with session.post(
                        urllib.parse.urljoin(self.api_url, "/api/sdk/upload-data/"),
                        data=form_data,
                    ) as response:
                        response.raise_for_status()
                        return 1
                except Exception as e:
                    logger.error(f"Error uploading file {file} - {e}")
                    return 0

        async def main():
            logger.info(f"Uploading {num_files} files to project {project_id}")
            with tqdm.tqdm(total=num_files, ncols=80) as pbar:
                async with aiohttp.ClientSession(
                    headers=self._get_headers()
                ) as session:
                    for i in range(num_batches):
                        tasks = []
                        for file in filtered_files[
                            i * batch_size : min((i + 1) * batch_size, num_files)
                        ]:
                            tasks.append(
                                post_file(
                                    session=session, file=file, project_id=project_id
                                )
                            )
                        for f in asyncio.as_completed(tasks):
                            pbar.update(await f)

        asyncio.run(main())

    def datasets(self, pretty=0):
        return self._get(f"/api/sdk/datasets/?pretty={pretty}")

    def dataset_download(self, dataset_id, export_type):
        response = self._post(
            f"/api/sdk/datasets/{dataset_id}/",
            data={"download_type": "annotation", "export_type": export_type},
        )

        with self.api_session.get(url=response["file"], stream=True) as r:
            r.raise_for_status()
            filename = f"dataset-{dataset_id}.json"
            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
            logger.info(f"File: {os.path.abspath(filename)}")
            return os.path.abspath(filename)

    def dataset_download_files(self, dataset_id):
        response = self._post(
            f"/api/sdk/datasets/{dataset_id}/", data={"download_type": "files"}
        )
        folder = f"dataset-files-{dataset_id}"
        os.makedirs(folder, exist_ok=True)
        dataset_files = [
            dataset_file
            for dataset_file in response
            if not os.path.isfile(os.path.join(folder, dataset_file["file_name"]))
        ]

        async def download_file(session: aiohttp.ClientSession, dataset_file: dict):
            async with session.get(url=dataset_file["source"]) as r:
                try:
                    r.raise_for_status()
                except Exception as e:
                    logger.error(
                        f"Error downloading file {dataset_file['file_name']} - {e}"
                    )
                    return 0
                async with aiofiles.open(
                    os.path.join(folder, dataset_file["file_name"]), "wb"
                ) as f:
                    async for chunk in r.content.iter_any():
                        await f.write(chunk)
                    return 1

        async def main():
            with tqdm.tqdm(total=len(dataset_files), ncols=80) as pbar:
                async with aiohttp.ClientSession() as session:
                    tasks = [
                        download_file(session=session, dataset_file=dataset_file)
                        for dataset_file in dataset_files
                    ]
                    for f in asyncio.as_completed(tasks):
                        pbar.update(await f)

        asyncio.run(main())
    
    def initialize_device_agent(self, server_url: str, device_id: str, base_domain: str):
        """Initialize device agent configuration"""
        self.server_url = server_url.rstrip('/')
        self.device_id = device_id
        self.base_domain = base_domain
        
        # Initialize tunnel manager if available
        if CloudflareTunnel:
            self.tunnel_manager = CloudflareTunnel(base_domain, device_id)
            self.jupyter_url = self.tunnel_manager.jupyter_url
            self.ssh_url = self.tunnel_manager.ssh_url
        else:
            self.tunnel_manager = None
            self.jupyter_url = f"https://jupyter-{device_id}.{base_domain}"
            self.ssh_url = f"https://ssh-{device_id}.{base_domain}"
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        _ = frame  # Unused but required by signal handler signature
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _get_device_headers(self):
        """Get headers for device agent API requests"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'UnitlabDeviceAgent/{self.device_id}'
        }
        
        # Add API key if provided
        if self.api_key:
            headers['Authorization'] = f'Api-Key {self.api_key}'
        
        return headers
    
    def _post_device(self, endpoint, data=None):
        """Make authenticated POST request for device agent"""
        full_url = urllib.parse.urljoin(self.server_url, endpoint)
        logger.debug(f"Posting to {full_url} with data: {data}")
        
        try:
            response = self.api_session.post(
                full_url,
                json=data or {},
                headers=self._get_device_headers(),
            )
            logger.debug(f"Response status: {response.status_code}, Response: {response.text}")
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"POST request failed to {full_url}: {e}")
            raise
    
    def start_jupyter(self) -> bool:
        """Start Jupyter notebook server"""
        try:
            logger.info("Starting Jupyter notebook...")
            
            cmd = [
                "jupyter", "notebook",
                "--no-browser",
                "--ServerApp.token=''",
                "--ServerApp.password=''",
                "--ServerApp.allow_origin='*'",
                "--ServerApp.ip='0.0.0.0'"
            ]
            
            self.jupyter_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Wait for Jupyter to start and get the port
            start_time = time.time()
            while time.time() - start_time < 30:
                line = self.jupyter_proc.stdout.readline()
                if not line:
                    break
                
                # Look for the port in the output
                match = re.search(r'http://.*:(\d+)/', line)
                if match:
                    self.jupyter_port = match.group(1)
                    logger.info(f"✅ Jupyter started on port {self.jupyter_port}")
                    return True
            
            raise Exception("Timeout waiting for Jupyter to start")
            
        except Exception as e:
            logger.error(f"Failed to start Jupyter: {e}")
            if self.jupyter_proc:
                self.jupyter_proc.terminate()
                self.jupyter_proc = None
            return False
    
    def setup_tunnels(self) -> bool:
        """Setup Cloudflare tunnels"""
        try:
            if not self.jupyter_port:
                logger.error("Jupyter port not available")
                return False
            
            if not self.tunnel_manager:
                logger.warning("CloudflareTunnel not available, skipping tunnel setup")
                return True
            
            logger.info("Setting up Cloudflare tunnels...")
            self.tunnel_proc = self.tunnel_manager.setup(self.jupyter_port)
            
            if self.tunnel_proc:
                logger.info("✅ Tunnels established")
                self.report_services()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Tunnel setup failed: {e}")
            return False
    
    def check_ssh(self) -> bool:
        """Check if SSH service is available"""
        try:
            # Check if SSH is running
            result = subprocess.run(
                ["systemctl", "is-active", "ssh"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.stdout.strip() == "active":
                logger.info("✅ SSH service is active")
                return True
            else:
                logger.warning("SSH service is not active")
                # Try to start SSH
                subprocess.run(["sudo", "systemctl", "start", "ssh"], timeout=10)
                time.sleep(2)
                return False
                
        except Exception as e:
            logger.error(f"SSH check failed: {e}")
            return False
    
    def report_services(self):
        """Report services to the server"""
        try:
            # Report Jupyter service
            jupyter_data = {
                'service_type': 'jupyter',
                'service_name': f'jupyter-{self.device_id}',
                'local_port': int(self.jupyter_port) if self.jupyter_port else 8888,
                'tunnel_url': self.jupyter_url,
                'status': 'online'
            }
            
            logger.info(f"Reporting Jupyter service with URL: {self.jupyter_url}")
            jupyter_response = self._post_device(
                f"/api/tunnel/agent/jupyter/{self.device_id}/", 
                jupyter_data
            )
            logger.info(f"Reported Jupyter service: {jupyter_response.status_code if hasattr(jupyter_response, 'status_code') else jupyter_response}")
            
            # Report SSH service (always report, even if SSH is not running locally)
            # Remove https:// prefix for SSH hostname
            ssh_hostname = self.ssh_url.replace('https://', '')
            
            # Get current system username
            import getpass
            current_user = getpass.getuser()
            
            # Create SSH connection command
            ssh_connection_cmd = f"ssh -o ProxyCommand='cloudflared access ssh --hostname {ssh_hostname}' {current_user}@{ssh_hostname}"
            
            # Check if SSH is available
            ssh_available = self.check_ssh()
            
            ssh_data = {
                'service_type': 'ssh',
                'service_name': f'ssh-{self.device_id}',
                'local_port': 22,
                'tunnel_url': ssh_connection_cmd,  # Send the SSH command instead of URL
                'status': 'online' if ssh_available else 'offline'
            }
            
            logger.info(f"Reporting SSH service with command: {ssh_connection_cmd}")
            ssh_response = self._post_device(
                f"/api/tunnel/agent/ssh/{self.device_id}/",
                ssh_data
            )
            logger.info(f"Reported SSH service: {ssh_response.status_code if hasattr(ssh_response, 'status_code') else ssh_response}")
            
        except Exception as e:
            logger.error(f"Failed to report services: {e}", exc_info=True)
    
    def collect_metrics(self) -> dict:
        """Collect system metrics"""
        metrics = {}
        
        # CPU metrics
        metrics['cpu'] = {
            'percent': psutil.cpu_percent(interval=1),
            'count': psutil.cpu_count(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Memory metrics
        mem = psutil.virtual_memory()
        metrics['ram'] = {
            'total': mem.total,
            'used': mem.used,
            'available': mem.available,
            'percent': mem.percent,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # GPU metrics (if available)
        if HAS_GPU:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    metrics['gpu'] = {
                        'name': gpu.name,
                        'load': gpu.load * 100,
                        'memory_used': gpu.memoryUsed,
                        'memory_total': gpu.memoryTotal,
                        'temperature': gpu.temperature,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
            except Exception as e:
                logger.debug(f"GPU metrics unavailable: {e}")
        
        return metrics
    
    def send_metrics(self):
        """Send metrics to server"""
        try:
            metrics = self.collect_metrics()
            
            # Send CPU metrics
            if 'cpu' in metrics:
                self._post_device(f"/api/tunnel/agent/cpu/{self.device_id}/", metrics['cpu'])
            
            # Send RAM metrics  
            if 'ram' in metrics:
                self._post_device(f"/api/tunnel/agent/ram/{self.device_id}/", metrics['ram'])
            
            # Send GPU metrics if available
            if 'gpu' in metrics and metrics['gpu']:
                self._post_device(f"/api/tunnel/agent/gpu/{self.device_id}/", metrics['gpu'])
            
            logger.debug(f"Metrics sent - CPU: {metrics['cpu']['percent']:.1f}%, RAM: {metrics['ram']['percent']:.1f}%")
            
        except Exception as e:
            logger.error(f"Failed to send metrics: {e}")
    
    def metrics_loop(self):
        """Background thread for sending metrics"""
        logger.info("Starting metrics thread")
        
        while self.running:
            try:
                self.send_metrics()
                
                # Check if processes are still running
                if self.jupyter_proc and self.jupyter_proc.poll() is not None:
                    logger.warning("Jupyter process died")
                    self.jupyter_proc = None
                
                if self.tunnel_proc and self.tunnel_proc.poll() is not None:
                    logger.warning("Tunnel process died")
                    self.tunnel_proc = None
                
            except Exception as e:
                logger.error(f"Metrics loop error: {e}")
            
            # Wait for next interval (default 5 seconds)
            for _ in range(3):
                if not self.running:
                    break
                time.sleep(1)
        
        logger.info("Metrics thread stopped")
    
    def run_device_agent(self):
        """Main run method for device agent"""
        logger.info("=" * 50)
        logger.info("Starting Device Agent")
        logger.info(f"Device ID: {self.device_id}")
        logger.info(f"Server: {self.server_url}")
        logger.info(f"Domain: {self.base_domain}")
        logger.info("=" * 50)
        
        # Check SSH
        self.check_ssh()
        
        # Start Jupyter
        if not self.start_jupyter():
            logger.error("Failed to start Jupyter")
            return
        
        # Wait a moment for Jupyter to fully initialize
        time.sleep(1)
        
        # Setup tunnels
        if not self.setup_tunnels():
            logger.error("Failed to setup tunnels")
            self.cleanup_device_agent()
            return
        
        # Print access information
        logger.info("=" * 50)
        logger.info("🎉 All services started successfully!")
        logger.info(f"📔 Jupyter: {self.jupyter_url}")
        logger.info(f"🔐 SSH: {self.ssh_url}")
        # Remove https:// prefix for SSH command display
        ssh_hostname = self.ssh_url.replace('https://', '')
        import getpass
        current_user = getpass.getuser()
        logger.info(f"🔐 SSH Command: ssh -o ProxyCommand='cloudflared access ssh --hostname {ssh_hostname}' {current_user}@{ssh_hostname}")
        logger.info("=" * 50)
        
        # Start metrics thread
        self.metrics_thread = threading.Thread(target=self.metrics_loop, daemon=True)
        self.metrics_thread.start()
        
        # Main loop
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        
        self.cleanup_device_agent()
    
    def cleanup_device_agent(self):
        """Clean up device agent resources"""
        logger.info("Cleaning up...")
        
        self.running = False
        
        # Stop Jupyter
        if self.jupyter_proc:
            logger.info("Stopping Jupyter...")
            self.jupyter_proc.terminate()
            try:
                self.jupyter_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.jupyter_proc.kill()
        
        # Stop tunnel
        if self.tunnel_proc:
            logger.info("Stopping tunnel...")
            self.tunnel_proc.terminate()
            try:
                self.tunnel_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tunnel_proc.kill()
        
        logger.info("Cleanup complete")
