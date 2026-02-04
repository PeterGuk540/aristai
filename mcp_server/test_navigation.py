#!/usr/bin/env python3

import sys
import os

# Change to the correct directory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))

from tools.navigation import navigate_to_page

# Test the navigation tool
result = navigate_to_page('forum')
print("Navigation tool test result:", result)