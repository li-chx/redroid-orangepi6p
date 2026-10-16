#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fetch the pinned factory archive from a URL held in an environment variable."""
import argparse
import hashlib
import http.client
import os
import urllib.parse
import urllib.request

from common import LOCK, WORK, checked


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ValueError('Only HTTPS redirects are allowed')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, destination, expected):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or not parts.netloc or parts.username or parts.password:
        raise ValueError('Use a direct HTTPS URL without embedded login credentials')
    if destination.exists():
        checked(destination, expected)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + '.partial')
    if partial.exists():
        raise ValueError('A partial download already exists')
    opener = urllib.request.build_opener(HTTPSRedirects())
    digest = hashlib.sha256()
    size = 0
    try:
        with opener.open(url, timeout=120) as response, partial.open('xb') as output:
            while block := response.read(8 * 1024**2):
                size += len(block)
                if size > 2 * 1024**3:
                    raise ValueError('Download exceeds the limit for the pinned archive')
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != expected:
            raise ValueError('Downloaded archive SHA256 mismatch')
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url-env', default='VENDOR_ARCHIVE_URL')
    args = parser.parse_args()
    url = os.environ.get(args.url_env, '').strip()
    if not url:
        parser.error(f'Set {args.url_env} to the factory archive direct HTTPS URL')
    destination = WORK / 'downloads' / LOCK['vendor_archive']
    try:
        download(url, destination, LOCK['archive_sha256'])
    except (OSError, ValueError, RuntimeError, http.client.HTTPException):
        # Signed URLs can contain credentials: do not include the URL or exception text.
        raise SystemExit('Factory download failed. Check the HTTPS source, quota and pinned SHA256.') from None
    print('Verified factory archive:', destination.name)


if __name__ == '__main__':
    main()
