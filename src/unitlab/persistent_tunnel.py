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
import secrets

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

        self.cf_account_id = "29df28cf48a30be3b1aa344b840400e6"  # Your account ID
        self.cf_zone_id = "eae80a730730b3b218a80dace996535a"  # Zone ID for unitlab-ai.com
        
        # Clean device ID for subdomain
        if device_id:
            self.device_id = device_id.replace('_', '').replace('.', '').lower()[:30]
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
    
    
    
    def _get_headers(self):
        """Get API headers for Global API Key"""
     
    
        return { 
            "Authorization":  f"Bearer {self.cf_api_key}",                                                                                                                                                         
            "Content-Type": "application/json"                                                                                          
        } 
    
    # def get_or_create_tunnel(self):
    #     """Always create a new tunnel with unique name to avoid conflicts"""
    #     # Generate unique tunnel name to avoid conflicts
    #     import uuid
    #     unique_suffix = str(uuid.uuid4())[:8]
    #     self.tunnel_name = "agent-{}-{}".format(self.device_id, unique_suffix)
    #     print("🔧 Creating tunnel: {}...".format(self.tunnel_name))
        
    #     # Always create new tunnel
    #     return self.create_new_tunnel()


    def create_new_tunnel(self):
        """Create a new tunnel via Cloudflare API"""
        print("🔧 Creating new tunnel: {}...".format(self.tunnel_name))
        
        # Generate random tunnel secret (32 bytes)
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
            
            # Save credentials to file
            cred_file = "/tmp/tunnel-{}.json".format(self.tunnel_name)
            with open(cred_file, 'w') as f:
                json.dump(self.tunnel_credentials, f)
            
            print("✅ Tunnel created: {}".format(self.tunnel_id))
            print("✅ Credentials saved to: {}".format(cred_file))
            return cred_file
        else:
            print("❌ Failed to create tunnel: {}".format(response.text))
            return None
    
    def create_dns_record(self):
        """Create DNS CNAME records for main domain and SSH subdomain"""
        if not self.tunnel_id:
            return False
        
        print("🔧 Creating DNS records...")
        
        # self.get_zone_id()
        
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
        
        # First, check if SSH DNS record exists and delete it
        # print("🔍 Checking for existing SSH DNS record: {}.{}".format(self.ssh_subdomain, self.domain))
        # list_url = "{}?name={}.{}".format(url, self.ssh_subdomain, self.domain)
        # list_response = requests.get(list_url, headers=headers)
        
        # if list_response.status_code == 200:
        #     records = list_response.json().get("result", [])
        #     print("Found {} existing DNS records".format(len(records)))
        #     print('this is new version')
        #     for record in records:
        #         if record["name"] == "{}.{}".format(self.ssh_subdomain, self.domain):
        #             record_id = record["id"]
        #             print("🗑️  Deleting old SSH DNS record: {}".format(record_id))
        #             delete_url = "{}/{}".format(url, record_id)
        #             delete_response = requests.delete(delete_url, headers=headers)
        #             if delete_response.status_code in [200, 204]:
        #                 print("✅ Deleted old SSH DNS record")
        #             else:
        #                 print("⚠️  Could not delete old SSH DNS record: {}".format(delete_response.text[:200]))
        # else:
        #     print("⚠️  Could not list DNS records: {}".format(list_response.text[:200]))
        
        # Wait a moment for DNS deletion to propagate
        time.sleep(2)
        
        # Create new SSH subdomain record pointing to new tunnel
        ssh_data = {
            "type": "CNAME",
            "name": self.ssh_subdomain,
            "content": "{}.cfargotunnel.com".format(self.tunnel_id),
            "proxied": True,
            "ttl": 1
        }
        
        print("📝 Creating SSH DNS record: {} -> {}".format(self.ssh_subdomain, self.tunnel_id))
        ssh_response = requests.post(url, headers=headers, json=ssh_data)
        
        if ssh_response.status_code in [200, 201]:
            print("✅ SSH DNS record created: {}.{}".format(self.ssh_subdomain, self.domain))
            print("   Points to: {}.cfargotunnel.com".format(self.tunnel_id))
        else:
            print("❌ Failed to create SSH DNS: Status {} - {}".format(ssh_response.status_code, ssh_response.text))
            # Try to parse error
            try:
                error_data = ssh_response.json()
                if "errors" in error_data:
                    for error in error_data["errors"]:
                        print("   Error: {}".format(error.get("message", error)))
            except:
                pass
        
        return True
    
    def create_access_application(self):
        """Create Cloudflare Access application for SSH with bypass policy"""
        print("🔧 Creating Access application for SSH...")
        
        # Create Access application
        app_url = "https://api.cloudflare.com/client/v4/zones/{}/access/apps".format(self.cf_zone_id)
        headers = self._get_headers()
        
        app_data = {
            "name": "SSH-{}".format(self.device_id),
            "domain": "{}.{}".format(self.ssh_subdomain, self.domain),
            "type": "ssh",
            "session_duration": "24h",
            "auto_redirect_to_identity": False
        }
        
        app_response = requests.post(app_url, headers=headers, json=app_data)
        
        if app_response.status_code in [200, 201]:
            app_id = app_response.json()["result"]["id"]
            print("✅ Access application created: {}".format(app_id))
            
            # Create bypass policy (no authentication required)
            policy_url = "https://api.cloudflare.com/client/v4/zones/{}/access/apps/{}/policies".format(
                self.cf_zone_id, app_id
            )
            
            policy_data = {
                "name": "Public Access",
                "decision": "bypass",
                "include": [
                    {"everyone": {}}
                ],
                "precedence": 1
            }
            
            policy_response = requests.post(policy_url, headers=headers, json=policy_data)
            
            
            if policy_response.status_code in [200, 201]:
                print("✅ Bypass policy created - SSH is publicly accessible")
                return True
            else:
                print("⚠️  Could not create bypass policy: {}".format(policy_response.text[:200]))
                return False
        elif "already exists" in app_response.text:
            print("⚠️  Access application already exists")
            return True
        else:
            print("⚠️  Could not create Access application: {}".format(app_response.text[:200]))
            return False
    
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
            cred_file = self.create_new_tunnel()
        
            
            # 2. Create DNS record
            self.create_dns_record()
            
            # 3. Create Access application for SSH
            self.create_access_application()
            
            # 4. Create config
            config_file = self.create_tunnel_config(cred_file)
            
            # 5. Start services
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
    

    
    def stop(self):
        """Stop everything"""
        if self.jupyter_process:
            self.jupyter_process.terminate()
        if self.tunnel_process:
            self.tunnel_process.terminate()
            try:
                self.tunnel_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tunnel_process.kill()
                self.tunnel_process.wait()
            print("✅ Tunnel stopped")
        
    #     # Optionally delete tunnel when stopping
    #     if self.tunnel_id:
    #         try:
    #             url = "https://api.cloudflare.com/client/v4/accounts/{}/cfd_tunnel/{}".format(
    #                 self.cf_account_id, self.tunnel_id
    #             )
    #             requests.delete(url, headers=self._get_headers())
    #             print("🗑️  Tunnel deleted")
    #         except Exception:
    #             pass  # Ignore cleanup errors
    
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