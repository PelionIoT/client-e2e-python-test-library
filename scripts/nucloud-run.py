#!/usr/bin/env python3
"""Runs a command and masks credentials in its output.

The suite logs request headers and login payloads, so nothing it prints reaches
a terminal or a CI log unfiltered.
"""
import os
import re
import subprocess
import sys

SECRETS = [os.environ[name] for name in ('NUCLOUD_API_KEY', 'NUCLOUD_PASSWORD', 'NUCLOUD_ROOT_PASSWORD')
           if os.environ.get(name)]
TOKENS = re.compile(r'\b(ak|rt)_[A-Za-z0-9+/=_-]{16,}|\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9._-]+')


def mask(line):
    for secret in SECRETS:
        line = line.replace(secret, '<redacted>')
    return TOKENS.sub('<redacted>', line)


process = subprocess.Popen(sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                           errors='replace', bufsize=1)
for text in process.stdout:
    sys.stdout.write(mask(text))
    sys.stdout.flush()
sys.exit(process.wait())
