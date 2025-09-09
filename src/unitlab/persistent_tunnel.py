#!/usr/bin/env python3
"""
Persistent Tunnel - Each device gets deviceid.unitlab-ai.com
Uses Cloudflare API to create named tunnels
"""

import subprocess
import requests
import json
import time
import os
import base64
from fastapi import FastAPI
import uvicorn
import threading
import psutil


api = FastAPI()

@api.get("/api-agent/")
def get_cpu_info():
    cpu_usage_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    return  {"cpu_percentage": cpu_usage_percent, 'cpu_count': psutil.cpu_count(), 'ram_usage': ram.used }


class PersistentTunnel:
    def __init__(self, device_id=None):
        """Initialize with device ID"""
        
        # Cloudflare credentials (hardcoded for simplicity)
        
        self.cf_api_key = "RoIAn1t9rMqcGK7_Xja216pxbRTyFafC1jeRKIO3"  
        
        # Account and Zone IDs
        self.cf_account_id = "29df28cf48a30be3b1aa344b840400e6"  # Your account ID
        self.cf_zone_id = "eae80a730730b3b218a80dace996535a"  # Zone ID for unitlab-ai.com
        
        # Clean device ID for subdomain
        if device_id:
            self.device_id = device_id.replace('-', '').replace('_', '').replace('.', '').lower()[:20]
        else:
            import uuid
            self.device_id = str(uuid.uuid4())[:8]
        
        self.tunnel_name = "agent-{}".format(self.device_id)
        self.subdomain = self.device_id
        self.domain = "unitlab-ai.com"
        self.jupyter_url = "https://{}.{}".format(self.subdomain, self.domain)
        self.api_expose_url = "https://{}.{}/api-agent/".format(self.subdomain, self.domain)
        self.ssh_subdomain = "s{}".format(self.device_id)  # Shorter SSH subdomain to avoid length issues
        self.ssh_url = "{}.{}".format(self.ssh_subdomain, self.domain)  # SSH on s{deviceid}.unitlab-ai.com

        self.tunnel_id = None
        self.tunnel_credentials = None
        self.jupyter_process = None
        self.tunnel_process = None
    
    def get_zone_id(self):
        """Get Zone ID for unitlab-ai.com"""
        print("🔍 Getting Zone ID for {}...".format(self.domain))
        
        url = "https://api.cloudflare.com/client/v4/zones"
        headers = self._get_headers()
        params = {"name": self.domain}
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data["result"]:
                self.cf_zone_id = data["result"][0]["id"]
                print("✅ Zone ID: {}".format(self.cf_zone_id))
                return self.cf_zone_id
        
        print("❌ Could not get Zone ID")
        return None
    
    def _get_headers(self):
        """Get API headers for Global API Key"""
     
    
        return { 
            "Authorization":  f"Bearer {self.cf_api_key}",                                                                                                                                                         
            "Content-Type": "application/json"                                                                                          
        } 
    
    def get_or_create_tunnel(self):
        """Get existing tunnel or create a new one"""
        # First, check if tunnel already exists
        print("🔍 Checking for existing tunnel: {}...".format(self.tunnel_name))
        
        list_url = "https://api.cloudflare.com/client/v4/accounts/{}/cfd_tunnel".format(self.cf_account_id)
        headers = self._get_headers()
        
        # Check if tunnel exists
        response = requests.get(list_url, headers=headers)
        if response.status_code == 200:
            tunnels = response.json().get("result", [])
            for tunnel in tunnels:
                if tunnel["name"] == self.tunnel_name:
                    print("✅ Found existing tunnel: {}".format(tunnel["id"]))
                    self.tunnel_id = tunnel["id"]
                    
                    # Tunnel exists, create a new one with unique name
                    print("⚠️  Tunnel with this name already exists")
                    import uuid
                    unique_suffix = str(uuid.uuid4())[:8]
                    self.tunnel_name = "agent-{}-{}".format(self.device_id, unique_suffix)
                    print("🔄 Creating new tunnel with unique name: {}".format(self.tunnel_name))
                    # Don't break, let it continue to create new tunnel
                    return self.create_new_tunnel()
        
        # Create new tunnel
        return self.create_new_tunnel()
    
    def create_new_tunnel(self):
        """Create a brand new tunnel"""
        print("🔧 Creating new tunnel: {}...".format(self.tunnel_name))
        
        # Generate random tunnel secret (32 bytes)
        import secrets
        tunnel_secret = base64.b64encode(secrets.token_bytes(32)).decode()
        
        url = "https://api.cloudflare.com/client/v4/accounts/{}/cfd_tunnel".format(self.cf_account_id)
        headers = self._get_headers()
        
        data = {
            "name": self.tunnel_name,
            "tunnel_secret": tunnel_secret
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            result = response.json()["result"]
            self.tunnel_id = result["id"]
            
            # Create credentials JSON
            self.tunnel_credentials = {
                "AccountTag": self.cf_account_id,
                "TunnelSecret": tunnel_secret,
                "TunnelID": self.tunnel_id
            }
            
            # Save credentials to file with tunnel name (not ID) for consistency
            cred_file = "/tmp/tunnel-{}.json".format(self.tunnel_name)
            with open(cred_file, 'w') as f:
                json.dump(self.tunnel_credentials, f)
            
            print("✅ Tunnel created: {}".format(self.tunnel_id))
            return cred_file
        else:
            print("❌ Failed to create tunnel: {}".format(response.text))
            return None
    
    def create_dns_record(self):
        """Create DNS CNAME records for main domain and SSH subdomain"""
        if not self.tunnel_id:
            return False
        
        print("🔧 Creating DNS records...")
        
        # Get zone ID if we don't have it
        if self.cf_zone_id == "NEED_ZONE_ID_FOR_1SCAN_UZ":
            self.get_zone_id()
        
        url = "https://api.cloudflare.com/client/v4/zones/{}/dns_records".format(self.cf_zone_id)
        headers = self._get_headers()
        
        # Create main subdomain record for Jupyter and API
        data = {
            "type": "CNAME",
            "name": self.subdomain,
            "content": "{}.cfargotunnel.com".format(self.tunnel_id),
            "proxied": True,
            "ttl": 1
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            print("✅ Main DNS record created: {}.{}".format(self.subdomain, self.domain))
        elif "already exists" in response.text:
            print("⚠️  Main DNS record already exists: {}.{}".format(self.subdomain, self.domain))
        else:
            print("❌ Failed to create main DNS: {}".format(response.text[:200]))
            return False
        
        # Create SSH subdomain record (s{deviceid}.unitlab-ai.com)
        ssh_data = {
            "type": "CNAME",
            "name": self.ssh_subdomain,
            "content": "{}.cfargotunnel.com".format(self.tunnel_id),
            "proxied": True,
            "ttl": 1
        }
        
        ssh_response = requests.post(url, headers=headers, json=ssh_data)
        
        if ssh_response.status_code in [200, 201]:
            print("✅ SSH DNS record created: {}.{}".format(self.ssh_subdomain, self.domain))
        elif "already exists" in ssh_response.text:
            print("⚠️  SSH DNS record already exists: {}.{}".format(self.ssh_subdomain, self.domain))
        else:
            print("⚠️  Could not create SSH DNS: {}".format(ssh_response.text[:200]))
            # SSH is optional, so we continue even if SSH DNS fails
        
        return True
    
    def create_tunnel_config(self, cred_file):
        """Create tunnel config file"""
        config_file = "/tmp/tunnel-config-{}.yml".format(self.tunnel_name)
        with open(config_file, 'w') as f:
            f.write("tunnel: {}\n".format(self.tunnel_id))
            f.write("credentials-file: {}\n\n".format(cred_file))
            f.write("ingress:\n")

            # SSH service on dedicated subdomain (s{deviceid}.unitlab-ai.com)
            f.write("  - hostname: {}.{}\n".format(self.ssh_subdomain, self.domain))
            f.write("    service: ssh://localhost:22\n")

            # API (more specific path goes first)
            f.write("  - hostname: {}.{}\n".format(self.subdomain, self.domain))
            f.write("    path: /api-agent/*\n")
            f.write("    service: http://localhost:8001\n")

            # Jupyter (general hostname for HTTP)
            f.write("  - hostname: {}.{}\n".format(self.subdomain, self.domain))
            f.write("    service: http://localhost:8888\n")

            # Catch-all 404 (MUST be last!)
            f.write("  - service: http_status:404\n")
        return config_file 

    
    def get_cloudflared_path(self):
        """Get or download cloudflared for any platform"""
        import shutil
        import platform
        
        # Check if already in system PATH
        if shutil.which("cloudflared"):
            return "cloudflared"
        
        # Determine binary location based on OS
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        if system == "windows":
            local_bin = os.path.expanduser("~/cloudflared/cloudflared.exe")
        else:
            local_bin = os.path.expanduser("~/.local/bin/cloudflared")
        
        # Check if already downloaded
        if os.path.exists(local_bin):
            return local_bin
        
        # Download based on platform
        print("📦 Downloading cloudflared for {}...".format(system))
        
        if system == "linux":
            # Linux: detect architecture
            if "arm" in machine or "aarch64" in machine:
                arch = "arm64"
            elif "386" in machine or "i686" in machine:
                arch = "386"
            else:
                arch = "amd64"
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{}".format(arch)
            
            os.makedirs(os.path.dirname(local_bin), exist_ok=True)
            subprocess.run("curl -L {} -o {}".format(url, local_bin), shell=True, capture_output=True)
            subprocess.run("chmod +x {}".format(local_bin), shell=True)
            
        elif system == "darwin":
            # macOS: supports both Intel and Apple Silicon
            if "arm" in machine:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz"
            else:
                url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"
            
            os.makedirs(os.path.dirname(local_bin), exist_ok=True)
            # Download and extract tar.gz
            subprocess.run("curl -L {} | tar xz -C {}".format(url, os.path.dirname(local_bin)), shell=True, capture_output=True)
            subprocess.run("chmod +x {}".format(local_bin), shell=True)
            
        elif system == "windows":
            # Windows: typically amd64
            if "arm" in machine:
                arch = "arm64"
            elif "386" in machine:
                arch = "386"
            else:
                arch = "amd64"
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-{}.exe".format(arch)
            
            os.makedirs(os.path.dirname(local_bin), exist_ok=True)
            # Use PowerShell on Windows to download
            subprocess.run("powershell -Command \"Invoke-WebRequest -Uri {} -OutFile {}\"".format(url, local_bin), shell=True, capture_output=True)
        
        else:
            print("❌ Unsupported platform: {}".format(system))
            raise Exception("Platform {} not supported".format(system))
        
        print("✅ cloudflared downloaded successfully")
        return local_bin
    
   

    
    def start_jupyter(self):
        """Start Jupyter"""
        print("🚀 Starting Jupyter...")
        
        cmd = [
            "jupyter", "notebook",
            "--port", "8888",
            "--no-browser",
            "--ip", "0.0.0.0",
            "--NotebookApp.token=''",
            "--NotebookApp.password=''",
            "--NotebookApp.allow_origin='*'"

            
        ]
        
        self.jupyter_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        time.sleep(3)
        print("✅ Jupyter started")
        return True
    
    def start_api(self):
        def run_api():
            uvicorn.run(
                api,
                port=8001
            )
        
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        print('API is started')

    def start_tunnel(self, config_file):                                                         
        """Start tunnel with config"""                                                           
        print("🔧 Starting tunnel...")                                                           
                                                                                                
        cloudflared = self.get_cloudflared_path()                                                
                                                                                                
        cmd = [                                                                                  
            cloudflared,                                                                         
            "tunnel",                                                                            
            "--config", config_file,                                                             
            "run"                                                                                
        ]                                                                                        
                                                                                                
        self.tunnel_process = subprocess.Popen(                                                  
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE                                  
        )                                                                                        
                                                                                                
        time.sleep(2)                                                                            
                                                                                                
        # Check if process is still running                                                      
        if self.tunnel_process.poll() is not None:                                               
            print("❌ Tunnel process died!")                                                      
            # Try to read error output                                                           
            try:                                                                                 
                stdout, stderr = self.tunnel_process.communicate(timeout=1)                      
                if stderr:                                                                       
                    print(f"Error: {stderr.decode()}")                                           
                if stdout:                                                                       
                    print(f"Output: {stdout.decode()}")                                          
            except:                                                                              
                pass                                                                             
            return False                                                                         
                                                                                                
        print("✅ Tunnel running at {}".format(self.jupyter_url))                                 
        print("✅ API running at {}".format(self.api_expose_url))
        print("✅ SSH available at {}".format(self.ssh_url))                                        
        return True        
    
    def start(self):
        """Main entry point"""
        try:
            print("="*50)
            print("🌐 Persistent Tunnel with API")
            print("Device: {}".format(self.device_id))
            print("Target: {}.{}".format(self.subdomain, self.domain))
            print("="*50)
            
            # API credentials are hardcoded, so we're ready to go
            
            # 1. Get existing or create new tunnel via API
            cred_file = self.get_or_create_tunnel()
        
            
            # 2. Create DNS record
            self.create_dns_record()
            
            # 3. Create config
            config_file = self.create_tunnel_config(cred_file)
            
            # 4. Start services
            self.start_jupyter()
            self.start_api()
            self.start_tunnel(config_file)
            
            print("\n" + "="*50)
            print("🎉 SUCCESS! Persistent URLs created:")
            print("📔 Jupyter:   {}".format(self.jupyter_url))
            print("🔧 API:       {}".format(self.api_expose_url))
            print("🔐 SSH:       {}".format(self.ssh_url))
            print("")
            print("SSH Connection Command:")
            import getpass
            current_user = getpass.getuser()
            print("ssh -o ProxyCommand='cloudflared access ssh --hostname {}' {}@{}".format(
                self.ssh_url, current_user, self.ssh_url))
            print("")
            print("Tunnel ID: {}".format(self.tunnel_id))
            print("="*50)
  
            
            return True
            
        except Exception as e:
            print("❌ Error: {}".format(e))
            import traceback
            traceback.print_exc()
            self.stop()
            return False
    
    def start_quick_tunnel(self):
        """Fallback to quick tunnel"""
        print("🔧 Using quick tunnel (temporary URL)...")
        
        # Start Jupyter first
        self.start_jupyter()
        
        # Start quick tunnel
        cloudflared = self.get_cloudflared_path()
        cmd = [cloudflared, "tunnel", "--url", "http://localhost:8888"]
        
        self.tunnel_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        
        # Get URL from output
        for _ in range(30):
            line = self.tunnel_process.stdout.readline()
            if "trycloudflare.com" in line:
                import re
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    self.jupyter_url = match.group(0)
                    print("✅ Quick tunnel: {}".format(self.jupyter_url))
                    return True
            time.sleep(0.5)
        
        return False
    
    def stop(self):
        """Stop everything"""
        if self.jupyter_process:
            self.jupyter_process.terminate()
        if self.tunnel_process:
            self.tunnel_process.terminate()
        
        # Optionally delete tunnel when stopping
        if self.tunnel_id:
            try:
                url = "https://api.cloudflare.com/client/v4/accounts/{}/cfd_tunnel/{}".format(
                    self.cf_account_id, self.tunnel_id
                )
                requests.delete(url, headers=self._get_headers())
                print("🗑️  Tunnel deleted")
            except Exception:
                pass  # Ignore cleanup errors
    
    def run(self):
        """Run and keep alive"""
        try:
            if self.start():
                print("\nPress Ctrl+C to stop...")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  Shutting down...")
            self.stop()


def main():
    import platform
    import uuid
    
    hostname = platform.node().replace('.', '-')[:20]
    device_id = "{}-{}".format(hostname, str(uuid.uuid4())[:8])
    
    print("Device ID: {}".format(device_id))
    
    tunnel = PersistentTunnel(device_id=device_id)
    tunnel.run()


if __name__ == "__main__":
    main()