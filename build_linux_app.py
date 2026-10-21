import os
import shutil
import subprocess
import sys
import zipapp

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
STAGING = os.path.join(REPO_DIR, "build", "zipapp_staging")
DIST = os.path.join(REPO_DIR, "dist")
os.makedirs(DIST, exist_ok=True)
if os.path.exists(STAGING):
    shutil.rmtree(STAGING)
os.makedirs(STAGING, exist_ok=True)

# Copy onec_debug directory
shutil.copytree(os.path.join(REPO_DIR, "onec_debug"), os.path.join(STAGING, "onec_debug"))

# Create top-level __main__.py
with open(os.path.join(STAGING, "__main__.py"), "w", encoding="utf-8") as f:
    f.write("""# -*- coding: utf-8 -*-
from onec_debug.cli import main

if __name__ == '__main__':
    main()
""")

output_bin = os.path.join(DIST, "onec-debug-linux")
print("Packaging into", output_bin)
zipapp.create_archive(
    source=STAGING,
    target=output_bin,
    interpreter="/usr/bin/env python3"
)

print("Created executable:", output_bin, "Size:", os.path.getsize(output_bin), "bytes")
