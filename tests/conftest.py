"""Shared pytest fixtures and path setup for the ProjectExo test suite.

The suite deliberately targets the pure, dependency-light helper modules
(``utils.security``, ``utils.crypto``, ``storage``) so it can run in any
environment without a live Discord gateway, SSH host, or browser.
"""
import os
import sys

# Make the repository root importable regardless of where pytest is invoked.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
