#!/usr/bin/env python3
"""
Moltbot Integration: Status
Get current Brain Rider system status.
"""
import sys
import os
import json
import subprocess
from datetime import datetime

def get_status():
    """Get Brain Rider system status."""
    try:
        status = {}

        # Check if service is running
        service_result = subprocess.run(
            ['systemctl', '--user', 'is-active', 'brain-rider.service'],
            capture_output=True,
            text=True
        )
        status['service_running'] = (service_result.returncode == 0)

        # Get uptime
        if status['service_running']:
            uptime_result = subprocess.run(
                ['systemctl', '--user', 'show', 'brain-rider.service', '--property=ActiveEnterTimestamp'],
                capture_output=True,
                text=True
            )
            timestamp_line = uptime_result.stdout.strip()
            if timestamp_line:
                status['started_at'] = timestamp_line.split('=')[1]

        # Get memory usage
        ps_result = subprocess.run(
            ['pgrep', '-f', 'src/core/main.py'],
            capture_output=True,
            text=True
        )
        if ps_result.returncode == 0:
            pid = ps_result.stdout.strip()
            mem_result = subprocess.run(
                ['ps', '-p', pid, '-o', 'rss='],
                capture_output=True,
                text=True
            )
            if mem_result.returncode == 0:
                rss_kb = int(mem_result.stdout.strip())
                status['memory_mb'] = round(rss_kb / 1024, 1)

        # System info
        status['timestamp'] = datetime.now().isoformat()
        status['hostname'] = subprocess.run(
            ['hostname'],
            capture_output=True,
            text=True
        ).stdout.strip()

        # Output as JSON
        print(json.dumps(status, indent=2))
        return 0

    except Exception as e:
        error_status = {
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
        print(json.dumps(error_status, indent=2), file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(get_status())
