#!/usr/bin/env python3
"""Entry point without PYTHONPATH installation (stdlib runtime)."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agentflow_runtime.cli import main
if __name__=='__main__':raise SystemExit(main())
