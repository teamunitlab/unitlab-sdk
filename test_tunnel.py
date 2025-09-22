#!/usr/bin/env python3
"""
Interactive test script for Cloudflare Tunnel Configuration
"""

import sys
import os
# Add the src directory to path to import directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'unitlab'))

from src.unitlab.tunnel_config import CloudflareTunnel
import time

def test_tunnel_setup():
    """Test the tunnel configuration setup"""
    
    # Test parameters
    base_domain = "1scan.uz"
    device_id = "test-device-001"
    jupyter_port = 8888
    
    print("=== Testing Cloudflare Tunnel Configuration ===\n")
    
    # Create tunnel instance
    tunnel = CloudflareTunnel(base_domain, device_id)
    
    print(f"Device ID: {device_id}")
    print(f"Base Domain: {base_domain}")
    print(f"Jupyter URL: {tunnel.jupyter_url}")
    print(f"SSH URL: {tunnel.ssh_url}")
    print(f"Tunnel Name: {tunnel.tunnel_name}")
    print(f"Config Directory: {tunnel.config_dir}\n")
    
    # Test login (interactive - will open browser if needed)
    print("Step 1: Testing Cloudflare Login...")
    if tunnel.login():
        print("✓ Login successful\n")
    else:
        print("✗ Login failed\n")
        return
    
    # Test tunnel creation
    print("Step 2: Creating/Finding Tunnel...")
    if tunnel.create_tunnel():
        print(f"✓ Tunnel ready with UUID: {tunnel.tunnel_uuid}\n")
    else:
        print("✗ Tunnel creation failed\n")
        return
    
    # Test DNS configuration
    print("Step 3: Configuring DNS routes...")
    if tunnel.configure_dns():
        print("✓ DNS routes configured\n")
    else:
        print("✗ DNS configuration failed\n")
        return
    
    # Test config file creation
    print("Step 4: Creating configuration file...")
    config_file = tunnel.create_config_file(jupyter_port)
    print(f"✓ Config file created: {config_file}\n")
    
    # Test tunnel start
    print("Step 5: Starting tunnel...")
    process = tunnel.start_tunnel(config_file)
    
    if process:
        print("\n=== Tunnel is Running ===")
        print(f"Jupyter accessible at: {tunnel.jupyter_url}")
        print(f"SSH accessible at: {tunnel.ssh_url}")
        print("\nPress Ctrl+C to stop the tunnel...")
        
        try:
            # Keep running until interrupted
            while True:
                time.sleep(1)
                if process.poll() is not None:
                    print("\n⚠️  Tunnel process stopped unexpectedly")
                    break
        except KeyboardInterrupt:
            print("\n\nStopping tunnel...")
            process.terminate()
            process.wait(timeout=5)
            print("✓ Tunnel stopped")
    else:
        print("✗ Failed to start tunnel")

def test_individual_methods():
    """Test individual methods of the CloudflareTunnel class"""
    
    base_domain = "1scan.uz"
    device_id = "test-device-002"
    
    print("=== Testing Individual Methods ===\n")
    
    tunnel = CloudflareTunnel(base_domain, device_id)
    
    # Test 1: Check if credentials exist
    print("Test 1: Checking for existing credentials...")
    cert_file = tunnel.config_dir / "cert.pem"
    if cert_file.exists():
        print(f"✓ Credentials found at: {cert_file}")
    else:
        print("✗ No credentials found - login required")
    
    # Test 2: List existing tunnels
    print("\nTest 2: Listing existing tunnels...")
    import subprocess
    import json
    
    try:
        result = subprocess.run(
            ["cloudflared", "tunnel", "list", "--output", "json"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            tunnels = json.loads(result.stdout)
            print(f"Found {len(tunnels)} tunnel(s):")
            for t in tunnels:
                print(f"  - {t.get('name')} (ID: {t.get('id')})")
        else:
            print("✗ Failed to list tunnels")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "="*50)

if __name__ == "__main__":
    import sys
    
    print("Cloudflare Tunnel Test Script")
    print("="*50)
    print("\nOptions:")
    print("1. Test full tunnel setup (interactive)")
    print("2. Test individual methods")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        test_tunnel_setup()
    elif choice == "2":
        test_individual_methods()
    elif choice == "3":
        print("Exiting...")
        sys.exit(0)
    else:
        print("Invalid choice")
        sys.exit(1)