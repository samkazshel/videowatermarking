#!/bin/bash
# Cleanup script for processed videos older than 3 days
find /home/samkenkaj/Desktop/videowatermarking/watermark_service/processed -mtime +3 -delete 2>/dev/null
