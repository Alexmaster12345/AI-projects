#!/usr/bin/env python3
"""
Simple SNMP Simulator for ASHD Testing

This script creates a minimal SNMP agent that responds to basic queries
for testing the ASHD SNMP monitoring functionality.
"""

import socket
import threading
import time
import struct
from datetime import datetime

class SNMPSimulator:
    def __init__(self, host='localhost', port=161):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        
        # Basic SNMP system information
        self.system_info = {
            '1.3.6.1.2.1.1.1.0': 'ASHD SNMP Simulator v1.0',  # sysDescr.0
            '1.3.6.1.2.1.1.3.0': str(int(time.time())),       # sysUpTime.0
            '1.3.6.1.2.1.1.5.0': 'ASHD-Simulator',           # sysName.0
            '1.3.6.1.2.1.1.6.0': 'Test Location',             # sysLocation.0
        }
    
    def start(self):
        """Start the SNMP simulator."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.running = True
            print(f"🚀 SNMP Simulator started on {self.host}:{self.port}")
            
            # Start server thread
            server_thread = threading.Thread(target=self._serve)
            server_thread.daemon = True
            server_thread.start()
            
            return True
        except PermissionError:
            print(f"❌ Permission denied. SNMP port 161 requires root privileges.")
            print(f"   Try running with sudo or use a different port (e.g., 1161)")
            return False
        except OSError as e:
            print(f"❌ Failed to start SNMP simulator: {e}")
            return False
    
    def stop(self):
        """Stop the SNMP simulator."""
        self.running = False
        if self.socket:
            self.socket.close()
        print(f"🛑 SNMP Simulator stopped")
    
    def _serve(self):
        """Main server loop."""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                response = self._handle_request(data, addr)
                if response:
                    self.socket.sendto(response, addr)
            except Exception as e:
                if self.running:
                    print(f"⚠️  Error handling request: {e}")
    
    def _handle_request(self, data, addr):
        """Handle SNMP request and return response."""
        try:
            # Very basic SNMP parsing - this is a minimal simulator
            # In real SNMP, we'd parse the ASN.1 structure properly
            
            # For testing purposes, we'll respond to any request with our system info
            # Update uptime
            self.system_info['1.3.6.1.2.1.1.3.0'] = str(int(time.time()))
            
            # Create a simple SNMP response (GET response)
            # This is a minimal implementation for testing only
            response = self._create_get_response(self.system_info['1.3.6.1.2.1.1.1.0'])
            return response
            
        except Exception as e:
            print(f"⚠️  Error parsing SNMP request: {e}")
            return None
    
    def _create_get_response(self, value):
        """Create a simple SNMP GET response."""
        # This is a very simplified SNMP response
        # Real SNMP would need proper ASN.1 encoding/decoding
        
        # For testing ASHD, we just need to send some response
        # so the SNMP check doesn't timeout completely
        
        # Simple response header (very basic)
        response = b'\x30\x26'  # SEQUENCE, length
        response += b'\x02\x01\x01'  # INTEGER (version 1)
        response += b'\x04\x06public'  # OCTET STRING (community)
        response += b'\xa0\x19'  # GET RESPONSE
        response += b'\x02\x01\x00'  # request ID
        response += b'\x02\x01\x00'  # error status
        response += b'\x02\x01\x00'  # error index
        
        # Add the value (sysDescr)
        oid_bytes = b'\x06\x08\x2b\x06\x01\x02\x01\x01\x01\x00'  # 1.3.6.1.2.1.1.1.0
        value_bytes = value.encode('ascii')
        response += b'\x30' + struct.pack('B', len(oid_bytes) + len(value_bytes) + 4)  # SEQUENCE
        response += oid_bytes
        response += b'\x04' + struct.pack('B', len(value_bytes))  # OCTET STRING
        response += value_bytes
        
        return response

def main():
    print("🔧 ASHD SNMP Simulator")
    print("=" * 30)
    
    # Try to start on port 161 (requires root)
    simulator = SNMPSimulator()
    
    if not simulator.start():
        print(f"\n🔄 Trying alternative port 1161...")
        simulator = SNMPSimulator(port=1161)
        if simulator.start():
            print(f"\n✅ SNMP Simulator running on port 1161")
            print(f"   Update ASHD configuration:")
            print(f"   SNMP_PORT=1161")
        else:
            print(f"❌ Failed to start SNMP simulator")
            return
    
    print(f"\n📝 Test the simulator:")
    print(f"   snmpwalk -v2c -c public localhost:161 1.3.6.1.2.1.1.1.0")
    if simulator.port == 1161:
        print(f"   snmpwalk -v2c -c public localhost:1161 1.3.6.1.2.1.1.1.0")
    
    print(f"\n⚙️  Configure ASHD:")
    print(f"   SNMP_HOST=localhost")
    print(f"   SNMP_PORT={simulator.port}")
    print(f"   SNMP_COMMUNITY=public")
    print(f"   SNMP_TIMEOUT_SECONDS=2")
    
    print(f"\n🔄 Restart ASHD server after configuration")
    print(f"\n🛑 Press Ctrl+C to stop simulator")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        simulator.stop()

if __name__ == "__main__":
    main()
