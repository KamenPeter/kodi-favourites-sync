#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script entry point for the RUN button
When user clicks RUN in addon info, this script is executed
It directly launches the main addon menu
"""
import sys
import os

# Add resources/lib to path for imports
addon_path = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(addon_path, 'resources', 'lib')
sys.path.insert(0, lib_path)

# Import and run the main addon function
from addon import main

if __name__ == "__main__":
    main()
