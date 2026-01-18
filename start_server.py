#!/usr/bin/env python3
"""
Start the FFXI Gear Set Optimizer Web Server

Usage:
    python start_server.py [--port PORT] [--host HOST]
    
Example:
    python start_server.py --port 8080
"""

import argparse
import sys
import os

# Change to the script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wsdist_beta-main'))

def main():
    parser = argparse.ArgumentParser(description='FFXI Gear Set Optimizer Web Server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    args = parser.parse_args()
    
    print("=" * 60)
    print("FFXI Gear Set Optimizer")
    print("=" * 60)
    print()
    print(f"Starting server at http://{args.host}:{args.port}")
    print(f"API Documentation at http://{args.host}:{args.port}/docs")
    print()
    print("Open your browser and navigate to the URL above.")
    print("Press Ctrl+C to stop the server.")
    print("=" * 60)
    
    import uvicorn
    uvicorn.run(
        "api:app", 
        host=args.host, 
        port=args.port, 
        reload=args.reload
    )

if __name__ == "__main__":
    main()
