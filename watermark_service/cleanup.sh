#!/bin/bash
# Cleanup script for processed videos older than 3 days
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
find "$SCRIPT_DIR/processed" -mtime +3 -delete 2>/dev/null
