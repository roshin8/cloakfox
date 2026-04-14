#!/usr/bin/env python3
"""Fix mach logging bug where curly braces in file paths crash str.format()"""

import sys

if len(sys.argv) != 2:
    print("Usage: fix-mach-logging.py <firefox-src-dir>")
    sys.exit(1)

src_dir = sys.argv[1]
logging_path = f"{src_dir}/python/mach/mach/logging.py"

lines = open(logging_path).readlines()
new_lines = []
for line in lines:
    if 'formatted_msg = record.msg.format(**getattr(record, "params", {}))' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(f"{indent}try:\n")
        new_lines.append(f"{indent}    {line.lstrip()}")
        new_lines.append(f"{indent}except (KeyError, ValueError, IndexError):\n")
        new_lines.append(f"{indent}    formatted_msg = record.msg\n")
    else:
        new_lines.append(line)

open(logging_path, 'w').writelines(new_lines)
print("Fixed mach logging bug")
