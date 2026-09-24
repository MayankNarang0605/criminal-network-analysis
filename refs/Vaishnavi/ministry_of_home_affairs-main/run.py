"""
AI-Powered Criminal Network Analysis System
Single-Command Launcher
"""

import sys
import os
import uvicorn

if __name__ == "__main__":
    # Ensure current directory is in sys.path
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)

    print("=" * 70)
    print("AI-POWERED CRIMINAL NETWORK ANALYSIS SYSTEM")
    print("Themed on Ministry of Home Affairs (MHA) Specifications")
    print("=" * 70)
    print("Starting ASGI Application Server on http://127.0.0.1:8000 ...")
    print("Press Ctrl+C to stop.")
    print("=" * 70)

    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )
