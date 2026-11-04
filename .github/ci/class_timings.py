"""Measure how long each test class took, from an Odoo test log.

Each "Starting Class.test_method" line opens a test; the time until the next
such line (or the end of the post_install phase) is charged to that test's
class. setUpClass of the next class lands on the previous one, which is close
enough for balancing shards.

Usage: class_timings.py LOG [LOG ...] > timings.json
"""
import datetime
import json
import re
import sys

LINE = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) ')
START = re.compile(r' odoo\.addons\.(\w+)\.tests\.[\w.]+: Starting (\w+)\.\w+')
END = re.compile(r' post-tests in ')
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def timings(path):
    result, current, since = {}, None, None
    with open(path, errors='replace') as f:
        for line in f:
            line = ANSI.sub('', line)
            stamp = LINE.match(line)
            if not stamp:
                continue
            start, end = START.search(line), END.search(line)
            if not (start or end):
                continue
            now = datetime.datetime.strptime(stamp.group(1), '%Y-%m-%d %H:%M:%S,%f')
            if current:
                result[current] = result.get(current, 0.0) + (now - since).total_seconds()
            current = f'{start.group(1)}:{start.group(2)}' if start else None
            since = now
    return result


if __name__ == '__main__':
    merged = {}
    for path in sys.argv[1:]:
        for key, seconds in timings(path).items():
            merged[key] = merged.get(key, 0.0) + seconds
    json.dump({key: round(seconds, 1) for key, seconds in sorted(merged.items())}, sys.stdout, indent=0)
