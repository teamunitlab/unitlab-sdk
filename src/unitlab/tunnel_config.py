"""
Cloudflare Tunnel Configuration for persistent subdomains
"""

import json
import subprocess
import socket
import time
import yaml
from pathlib import Path


class CloudflareTunnel:
    def __init__(self, base_domain, device_id):
        # Hardcode the base domain here
        self.base_domain = "1scan.uz"  # HARDCODED - ignore the passed base_domain
        self.device_id = device_id
        self.hostname = socket.gethostname()
        self.tunnel_name = f"device-{device_id}"
        self.config_dir = Path.home() / ".cloudflared"
        self.config_dir.mkdir(exist_ok=True)
        
        # Subdomain names
        self.jupyter_subdomain = f"jupyter-{device_id}"
        self.ssh_subdomain = f"ssh-{device_id}"
        
        # Full URLs - using hardcoded base_domain
        self.jupyter_url = f"https://{self.jupyter_subdomain}.{self.base_domain}"
        self.ssh_url = f"https://{self.ssh_subdomain}.{self.base_domain}"
        
        self.tunnel_uuid = None
        self.credentials_file = None

    def login(self):
        """Login to Cloudflare (one-time setup)"""
        try:
            print("🔐 Checking Cloudflare authentication...")
            result = subprocess.run(
                ["cloudflared", "tunnel", "login"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✅ Cloudflare authentication successful")
                return True
            else:
                print("❌ Cloudflare authentication failed")
                return False
        except Exception as e:
            print(f"❌ Error during Cloudflare login: {e}")
            return False

    def create_tunnel(self):
        """Create a named tunnel"""
        try:
            print(f"🚇 Creating tunnel: {self.tunnel_name}")
            
            # Check if tunnel already exists
            list_result = subprocess.run(
                ["cloudflared", "tunnel", "list", "--output", "json"],
                capture_output=True,
                text=True
            )
            
            if list_result.returncode == 0:
                tunnels = json.loads(list_result.stdout)
                for tunnel in tunnels:
                    if tunnel.get("name") == self.tunnel_name:
                        self.tunnel_uuid = tunnel.get("id")
                        print(f"✅ Tunnel already exists with ID: {self.tunnel_uuid}")
                        self.credentials_file = self.config_dir / f"{self.tunnel_uuid}.json"
                        return True
            
            # Create new tunnel
            result = subprocess.run(
                ["cloudflared", "tunnel", "create", self.tunnel_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if "Created tunnel" in line and "with id" in line:
                        self.tunnel_uuid = line.split("with id")[1].strip()
                        break
                
                if not self.tunnel_uuid:
                    list_result = subprocess.run(
                        ["cloudflared", "tunnel", "list", "--output", "json"],
                        capture_output=True,
                        text=True
                    )
                    if list_result.returncode == 0:
                        tunnels = json.loads(list_result.stdout)
                        for tunnel in tunnels:
                            if tunnel.get("name") == self.tunnel_name:
                                self.tunnel_uuid = tunnel.get("id")
                                break
                
                if self.tunnel_uuid:
                    self.credentials_file = self.config_dir / f"{self.tunnel_uuid}.json"
                    print(f"✅ Tunnel created with ID: {self.tunnel_uuid}")
                    return True
                    
            print(f"❌ Failed to create tunnel: {result.stderr}")
            return False
            
        except Exception as e:
            print(f"❌ Error creating tunnel: {e}")
            return False

    def configure_dns(self):
        """Configure DNS routes for the tunnel"""
        try:
            print("🌐 Configuring DNS routes...")
            
            # Route for Jupyter
            jupyter_result = subprocess.run(
                ["cloudflared", "tunnel", "route", "dns", 
                 self.tunnel_name, f"{self.jupyter_subdomain}.{self.base_domain}"],
                capture_output=True,
                text=True
            )
            
            if jupyter_result.returncode == 0:
                print(f"✅ Jupyter route configured: {self.jupyter_url}")
            else:
                print(f"⚠️  Jupyter route may already exist or failed: {jupyter_result.stderr}")
            
            # Route for SSH
            ssh_result = subprocess.run(
                ["cloudflared", "tunnel", "route", "dns",
                 self.tunnel_name, f"{self.ssh_subdomain}.{self.base_domain}"],
                capture_output=True,
                text=True
            )
            
            if ssh_result.returncode == 0:
                print(f"✅ SSH route configured: {self.ssh_url}")
            else:
                print(f"⚠️  SSH route may already exist or failed: {ssh_result.stderr}")
                
            return True
            
        except Exception as e:
            print(f"❌ Error configuring DNS: {e}")
            return False

    def create_config_file(self, jupyter_port):
        """Create tunnel configuration file"""
        config = {
            "tunnel": self.tunnel_uuid,
            "credentials-file": str(self.credentials_file),
            "ingress": [
                {
                    "hostname": f"{self.jupyter_subdomain}.{self.base_domain}",
                    "service": f"http://localhost:{jupyter_port}",
                    "originRequest": {
                        "noTLSVerify": True
                    }
                },
                {
                    "hostname": f"{self.ssh_subdomain}.{self.base_domain}",
                    "service": "ssh://localhost:22",
                    "originRequest": {
                        "noTLSVerify": True
                    }
                },
                {
                    "service": "http_status:404"
                }
            ]
        }
        
        config_file = self.config_dir / f"config-{self.device_id}.yml"
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        print(f"📝 Configuration saved to: {config_file}")
        return config_file

    def start_tunnel(self, config_file):
        """Start the tunnel with the configuration"""
        try:
            print("🚀 Starting Cloudflare tunnel...")
            
            cmd = ["cloudflared", "tunnel", "--config", str(config_file), "run"]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Wait for tunnel to establish
            time.sleep(5)
            
            if process.poll() is None:
                print("✅ Tunnel is running")
                return process
            else:
                print("❌ Tunnel failed to start")
                return None
                
        except Exception as e:
            print(f"❌ Error starting tunnel: {e}")
            return None

    def setup(self, jupyter_port):
        """Complete setup process"""
        # Check if we need to login
        if not (self.config_dir / "cert.pem").exists():
            if not self.login():
                return None
        
        # Create tunnel
        if not self.create_tunnel():
            return None
        
        # Configure DNS
        if not self.configure_dns():
            return None
        
        # Create config file
        config_file = self.create_config_file(jupyter_port)
        
        # Start tunnel
        tunnel_process = self.start_tunnel(config_file)
        
        if tunnel_process:
            print("\n✅ Tunnel setup complete!")
            print(f"📌 Jupyter URL: {self.jupyter_url}")
            print(f"📌 SSH URL: {self.ssh_url}")
            return tunnel_process
        
        return None