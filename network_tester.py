#!/usr/bin/env python3
"""
Interactive Layer 7 Network Tester
A comprehensive HTTP/HTTPS network testing tool with threading support
"""

import requests
import threading
import time
import json
import statistics
from urllib.parse import urlparse
from datetime import datetime
import concurrent.futures
from dataclasses import dataclass
from typing import List, Dict, Optional
import sys
import os

@dataclass
class TestResult:
    """Data class to store individual test results"""
    response_time: float
    status_code: int
    success: bool
    error: Optional[str] = None
    response_size: int = 0
    timestamp: datetime = None

class NetworkTester:
    def __init__(self, url: str, threads: int = 10, timeout: int = 30):
        """
        Initialize the network tester
        
        Args:
            url: Target URL to test
            threads: Number of concurrent threads
            timeout: Request timeout in seconds
        """
        self.url = url
        self.threads = threads
        self.timeout = timeout
        self.results: List[TestResult] = []
        self.lock = threading.Lock()
        self.session = requests.Session()
        self.stop_requested = False
        
        # Configure session with connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=threads,
            pool_maxsize=threads,
            max_retries=0
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid URL format")
    
    def single_get_request(self) -> TestResult:
        """Perform a single GET request"""
        start_time = time.time()
        timestamp = datetime.now()
        
        try:
            response = self.session.get(
                self.url,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            response_time = time.time() - start_time
            
            return TestResult(
                response_time=response_time,
                status_code=response.status_code,
                success=response.status_code < 400,
                response_size=len(response.content),
                timestamp=timestamp
            )
            
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            return TestResult(
                response_time=response_time,
                status_code=0,
                success=False,
                error=str(e),
                timestamp=timestamp
            )
    
    def single_post_request(self, data: Dict = None, json_data: Dict = None) -> TestResult:
        """Perform a single POST request"""
        start_time = time.time()
        timestamp = datetime.now()
        
        try:
            kwargs = {
                'timeout': self.timeout,
                'allow_redirects': True
            }
            
            if json_data:
                kwargs['json'] = json_data
            elif data:
                kwargs['data'] = data
            
            response = self.session.post(self.url, **kwargs)
            response_time = time.time() - start_time
            
            return TestResult(
                response_time=response_time,
                status_code=response.status_code,
                success=response.status_code < 400,
                response_size=len(response.content),
                timestamp=timestamp
            )
            
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            return TestResult(
                response_time=response_time,
                status_code=0,
                success=False,
                error=str(e),
                timestamp=timestamp
            )
    
    def load_test(self, request_count: int, method: str = 'GET', 
                  post_data: Dict = None, json_data: Dict = None) -> List[TestResult]:
        """Perform load testing with multiple threads"""
        self.results = []
        self.stop_requested = False
        
        print(f"\n{'='*60}")
        print(f"🚀 Starting {method} Load Test")
        print(f"{'='*60}")
        print(f"🎯 Target: {self.url}")
        print(f"📊 Requests: {request_count}")
        print(f"🧵 Threads: {self.threads}")
        print(f"⏱️  Timeout: {self.timeout}s")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            if method.upper() == 'GET':
                futures = [executor.submit(self.single_get_request) 
                          for _ in range(request_count)]
            else:  # POST
                futures = [executor.submit(self.single_post_request, post_data, json_data) 
                          for _ in range(request_count)]
            
            # Collect results as they complete
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                if self.stop_requested:
                    break
                    
                result = future.result()
                with self.lock:
                    self.results.append(result)
                
                # Print progress with visual indicators
                if i % max(1, request_count // 20) == 0 or i == request_count:
                    progress = (i / request_count) * 100
                    bar_length = 30
                    filled_length = int(bar_length * i // request_count)
                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                    
                    print(f"\r📈 Progress: [{bar}] {i}/{request_count} ({progress:.1f}%)", end='')
        
        total_time = time.time() - start_time
        print(f"\n\n✅ Load test completed in {total_time:.2f} seconds")
        
        return self.results
    
    def stress_test(self, duration: int, method: str = 'GET', 
                   post_data: Dict = None, json_data: Dict = None) -> List[TestResult]:
        """Perform stress testing for a specified duration"""
        self.results = []
        self.stop_requested = False
        
        print(f"\n{'='*60}")
        print(f"⚡ Starting {method} Stress Test")
        print(f"{'='*60}")
        print(f"🎯 Target: {self.url}")
        print(f"⏱️  Duration: {duration} seconds")
        print(f"🧵 Threads: {self.threads}")
        print(f"⏰ Timeout: {self.timeout}s")
        print(f"{'='*60}")
        print("💡 Press Ctrl+C to stop early\n")
        
        start_time = time.time()
        stop_event = threading.Event()
        
        def worker():
            while not stop_event.is_set() and not self.stop_requested:
                try:
                    if method.upper() == 'GET':
                        result = self.single_get_request()
                    else:  # POST
                        result = self.single_post_request(post_data, json_data)
                    
                    with self.lock:
                        self.results.append(result)
                        
                except Exception as e:
                    print(f"Worker error: {e}")
                    break
        
        # Start worker threads
        threads = []
        for _ in range(self.threads):
            t = threading.Thread(target=worker)
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Monitor progress
        try:
            while time.time() - start_time < duration and not self.stop_requested:
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                
                with self.lock:
                    current_count = len(self.results)
                    successful = sum(1 for r in self.results if r.success)
                    
                rate = current_count / elapsed if elapsed > 0 else 0
                success_rate = (successful / current_count * 100) if current_count > 0 else 0
                
                # Progress bar for time
                progress = elapsed / duration
                bar_length = 30
                filled_length = int(bar_length * progress)
                time_bar = '█' * filled_length + '░' * (bar_length - filled_length)
                
                print(f"\r⏱️  Time: [{time_bar}] {elapsed:.1f}s/{duration}s | "
                      f"📊 Requests: {current_count} | "
                      f"🚀 Rate: {rate:.1f}/s | "
                      f"✅ Success: {success_rate:.1f}%", end='')
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Stopping test early...")
            self.stop_requested = True
        
        # Stop all threads
        stop_event.set()
        time.sleep(1)
        
        total_time = time.time() - start_time
        print(f"\n\n✅ Stress test completed in {total_time:.2f} seconds")
        
        return self.results
    
    def analyze_results(self) -> Dict:
        """Analyze test results and return statistics"""
        if not self.results:
            return {}
        
        # Extract metrics
        response_times = [r.response_time for r in self.results]
        status_codes = [r.status_code for r in self.results]
        successful_requests = [r for r in self.results if r.success]
        failed_requests = [r for r in self.results if not r.success]
        
        # Calculate statistics
        stats = {
            'total_requests': len(self.results),
            'successful_requests': len(successful_requests),
            'failed_requests': len(failed_requests),
            'success_rate': (len(successful_requests) / len(self.results)) * 100,
            'avg_response_time': statistics.mean(response_times),
            'min_response_time': min(response_times),
            'max_response_time': max(response_times),
            'median_response_time': statistics.median(response_times),
            'response_time_95th': sorted(response_times)[int(len(response_times) * 0.95)] if len(response_times) > 20 else max(response_times),
            'total_data_transferred': sum(r.response_size for r in successful_requests),
            'requests_per_second': len(self.results) / (max(r.timestamp for r in self.results) - min(r.timestamp for r in self.results)).total_seconds() if len(self.results) > 1 else 0
        }
        
        # Status code distribution
        status_distribution = {}
        for code in status_codes:
            status_distribution[code] = status_distribution.get(code, 0) + 1
        
        stats['status_code_distribution'] = status_distribution
        
        # Error analysis
        if failed_requests:
            error_types = {}
            for req in failed_requests:
                if req.error:
                    error_types[req.error] = error_types.get(req.error, 0) + 1
            stats['error_types'] = error_types
        
        return stats
    
    def print_results(self):
        """Print formatted test results"""
        stats = self.analyze_results()
        
        if not stats:
            print("❌ No results to display")
            return
        
        print(f"\n{'='*70}")
        print("📊 NETWORK TEST RESULTS")
        print(f"{'='*70}")
        print(f"🎯 Target URL: {self.url}")
        print(f"📈 Total Requests: {stats['total_requests']}")
        print(f"✅ Successful: {stats['successful_requests']} ({stats['success_rate']:.1f}%)")
        print(f"❌ Failed: {stats['failed_requests']}")
        print(f"🚀 Average Rate: {stats['requests_per_second']:.2f} req/s")
        
        print(f"\n⏱️  RESPONSE TIME STATISTICS:")
        print(f"  📊 Average: {stats['avg_response_time']:.3f}s")
        print(f"  🚀 Minimum: {stats['min_response_time']:.3f}s")
        print(f"  🐌 Maximum: {stats['max_response_time']:.3f}s")
        print(f"  📈 Median:  {stats['median_response_time']:.3f}s")
        print(f"  🎯 95th Percentile: {stats['response_time_95th']:.3f}s")
        
        print(f"\n📋 STATUS CODE DISTRIBUTION:")
        for code, count in sorted(stats['status_code_distribution'].items()):
            emoji = "✅" if code < 400 else "❌"
            print(f"  {emoji} {code}: {count} requests")
        
        if 'error_types' in stats:
            print(f"\n⚠️  ERROR ANALYSIS:")
            for error, count in stats['error_types'].items():
                print(f"  ❌ {error}: {count} occurrences")
        
        print(f"\n📦 Data Transferred: {stats['total_data_transferred'] / 1024:.2f} KB")
        print(f"{'='*70}")

class InteractiveNetworkTester:
    def __init__(self):
        self.tester = None
        self.clear_screen()
        
    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def show_banner(self):
        """Display the application banner"""
        banner = """
╔══════════════════════════════════════════════════════════════════════╗
║                    🌐 LAYER 7 NETWORK TESTER 🌐                     ║
║                                                                      ║
║              Interactive HTTP/HTTPS Testing Tool                     ║
║                     with Threading Support                           ║
╚══════════════════════════════════════════════════════════════════════╝
        """
        print(banner)
        
    def get_url(self):
        """Get and validate target URL"""
        while True:
            print("🎯 Enter the target URL to test:")
            print("   Examples: https://httpbin.org/get")
            print("            https://www.google.com")
            print("            http://localhost:8080")
            
            url = input("🔗 URL: ").strip()
            
            if not url:
                print("❌ Please enter a valid URL\n")
                continue
                
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            try:
                parsed = urlparse(url)
                if not parsed.netloc:
                    raise ValueError("Invalid URL")
                return url
            except Exception:
                print("❌ Invalid URL format. Please try again.\n")
                
    def get_test_config(self):
        """Get test configuration from user"""
        print("\n⚙️  TEST CONFIGURATION")
        print("="*50)
        
        # Number of threads
        while True:
            try:
                threads = input("🧵 Number of threads (1-5000, default 10): ").strip()
                if not threads:
                    threads = 10
                else:
                    threads = int(threads)
                    if threads < 1 or threads > 5000:
                        raise ValueError()
                break
            except ValueError:
                print("❌ Please enter a number between 1 and 100")
        
        # Timeout
        while True:
            try:
                timeout = input("⏱️  Request timeout in seconds (1-300, default 30): ").strip()
                if not timeout:
                    timeout = 30
                else:
                    timeout = int(timeout)
                    if timeout < 1 or timeout > 300:
                        raise ValueError()
                break
            except ValueError:
                print("❌ Please enter a number between 1 and 300")
                
        return threads, timeout
        
    def get_http_method(self):
        """Get HTTP method and POST data if needed"""
        print("\n📡 HTTP METHOD")
        print("="*30)
        print("1. GET  - Retrieve data")
        print("2. POST - Send data")
        
        while True:
            choice = input("Choose method (1 or 2, default 1): ").strip()
            if not choice or choice == '1':
                return 'GET', None, None
            elif choice == '2':
                return self.get_post_data()
            else:
                print("❌ Please enter 1 or 2")
                
    def get_post_data(self):
        """Get POST data configuration"""
        print("\n📤 POST DATA CONFIGURATION")
        print("="*40)
        print("1. No data (empty POST)")
        print("2. JSON data")
        print("3. Form data")
        
        while True:
            choice = input("Choose data type (1, 2, or 3): ").strip()
            
            if choice == '1':
                return 'POST', None, None
            elif choice == '2':
                json_str = input("Enter JSON data (e.g., {\"key\": \"value\"}): ").strip()
                try:
                    json_data = json.loads(json_str) if json_str else {}
                    return 'POST', None, json_data
                except json.JSONDecodeError:
                    print("❌ Invalid JSON format")
                    continue
            elif choice == '3':
                form_str = input("Enter form data as JSON (e.g., {\"name\": \"value\"}): ").strip()
                try:
                    form_data = json.loads(form_str) if form_str else {}
                    return 'POST', form_data, None
                except json.JSONDecodeError:
                    print("❌ Invalid JSON format")
                    continue
            else:
                print("❌ Please enter 1, 2, or 3")
                
    def get_test_type(self):
        """Get test type and parameters"""
        print("\n🧪 TEST TYPE")
        print("="*30)
        print("1. 🚀 Load Test    - Specific number of requests")
        print("2. ⚡ Stress Test  - Duration-based continuous testing")
        print("3. 🔍 Single Test  - One request for quick check")
        
        while True:
            choice = input("Choose test type (1, 2, or 3): ").strip()
            
            if choice == '1':
                return self.get_load_test_params()
            elif choice == '2':
                return self.get_stress_test_params()
            elif choice == '3':
                return 'single', 1
            else:
                print("❌ Please enter 1, 2, or 3")
                
    def get_load_test_params(self):
        """Get load test parameters"""
        while True:
            try:
                requests = input("📊 Number of requests (1-10000, default 100): ").strip()
                if not requests:
                    requests = 100
                else:
                    requests = int(requests)
                    if requests < 1 or requests > 10000:
                        raise ValueError()
                return 'load', requests
            except ValueError:
                print("❌ Please enter a number between 1 and 10000")
                
    def get_stress_test_params(self):
        """Get stress test parameters"""
        while True:
            try:
                duration = input("⏱️  Test duration in seconds (1-3600, default 30): ").strip()
                if not duration:
                    duration = 30
                else:
                    duration = int(duration)
                    if duration < 1 or duration > 3600:
                        raise ValueError()
                return 'stress', duration
            except ValueError:
                print("❌ Please enter a number between 1 and 3600")
                
    def run_test(self):
        """Run the complete test workflow"""
        try:
            self.show_banner()
            
            # Get configuration
            url = self.get_url()
            threads, timeout = self.get_test_config()
            method, post_data, json_data = self.get_http_method()
            test_type, param = self.get_test_type()
            
            # Initialize tester
            self.tester = NetworkTester(url, threads, timeout)
            
            # Show test summary
            print(f"\n🔍 TEST SUMMARY")
            print("="*40)
            print(f"🎯 URL: {url}")
            print(f"📡 Method: {method}")
            print(f"🧵 Threads: {threads}")
            print(f"⏱️  Timeout: {timeout}s")
            print(f"🧪 Test Type: {test_type.upper()}")
            
            if post_data:
                print(f"📤 Form Data: {post_data}")
            if json_data:
                print(f"📤 JSON Data: {json_data}")
                
            print("\n" + "="*40)
            
            # Confirm before starting
            confirm = input("🚀 Start test? (y/n, default y): ").strip().lower()
            if confirm and confirm != 'y':
                print("❌ Test cancelled")
                return
                
            # Run the test
            if test_type == 'load':
                self.tester.load_test(param, method, post_data, json_data)
            elif test_type == 'stress':
                self.tester.stress_test(param, method, post_data, json_data)
            else:  # single
                print("\n🔍 Running single test...")
                if method == 'GET':
                    result = self.tester.single_get_request()
                else:
                    result = self.tester.single_post_request(post_data, json_data)
                
                self.tester.results = [result]
                print(f"✅ Single test completed")
                
            # Show results
            self.tester.print_results()
            
            # Ask for another test
            print(f"\n{'='*70}")
            another = input("🔄 Run another test? (y/n): ").strip().lower()
            if another == 'y':
                self.clear_screen()
                self.run_test()
            else:
                print("👋 Thanks for using Layer 7 Network Tester!")
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
            if self.tester and self.tester.results:
                print("📊 Showing partial results...")
                self.tester.print_results()
        except Exception as e:
            print(f"\n❌ Error: {e}")
            
def main():
    """Main entry point"""
    tester = InteractiveNetworkTester()
    tester.run_test()

if __name__ == "__main__":
    main()