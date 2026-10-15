#!/usr/bin/env python3
"""Read-only target audit. Snapshot output must be outside the target repository.

Root README is deliberately excluded even from stat/hash operations. This is an
audit helper, not a write sandbox, README monitor, HTML writer or image renderer.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from html.parser import HTMLParser


KEYS = {
    'og:type', 'og:title', 'og:description', 'og:url', 'og:image',
    'og:site_name', 'og:locale', 'og:image:secure_url', 'og:image:type',
    'og:image:width', 'og:image:height', 'og:image:alt',
    'twitter:card', 'twitter:title', 'twitter:description',
    'twitter:image', 'twitter:image:alt', 'description',
}


def safe_relative(value):
    p = PurePosixPath(value)
    if p.is_absolute() or not p.parts or '..' in p.parts or '.git' in p.parts:
        raise ValueError(f'Unsafe allowlist path: {value}')
    if len(p.parts) == 1 and p.name.casefold() == 'readme.md':
        raise ValueError('README is outside this audit; handle only in first pass')
    return p.as_posix()


def inventory(root):
    """Never follow links or inspect root README, including case variants."""
    result = {}

    def visit(directory):
        with os.scandir(directory) as entries:
            for entry in sorted(entries, key=lambda x: x.name):
                if directory == root and entry.name.casefold() == 'readme.md':
                    continue
                if entry.name == '.git':
                    if directory != root:
                        raise ValueError('Nested repository: stop and narrow the target')
                    continue
                path = Path(entry.path)
                key = path.relative_to(root).as_posix()
                info = entry.stat(follow_symlinks=False)
                mode = stat.S_IMODE(info.st_mode)
                if stat.S_ISLNK(info.st_mode):
                    result[key] = {'type': 'link', 'mode': mode,
                                   'target': os.readlink(path)}
                elif stat.S_ISDIR(info.st_mode):
                    visit(path)
                elif stat.S_ISREG(info.st_mode):
                    if info.st_nlink != 1:
                        raise ValueError(f'Hardlinked file cannot be safely audited: {key}')
                    digest = hashlib.sha256()
                    with path.open('rb') as source:
                        for block in iter(lambda: source.read(1024 * 1024), b''):
                            digest.update(block)
                    result[key] = {'type': 'file', 'mode': mode,
                                   'sha256': digest.hexdigest()}
                else:
                    raise ValueError(f'Unsupported filesystem entry: {key}')
    visit(root)
    return result


class HeadMetadata(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.lines = [0]
        for i, c in enumerate(text):
            if c == '\n':
                self.lines.append(i + 1)
        self.in_head = False
        self.heads = 0
        self.closed = 0
        self.spans = []
        self.values = {}
        self.feed(text)
        self.close()
        if self.heads != 1 or self.closed != 1 or self.in_head:
            raise ValueError('Expected exactly one explicit, complete HTML head')

    def handle_starttag(self, tag, attrs):
        if tag == 'head':
            self.heads += 1
            self.in_head = True
        if tag != 'meta' or not self.in_head:
            return
        names = [k for k, _ in attrs]
        values = dict(attrs)
        key = values.get('property', values.get('name', '')).lower()
        if key not in KEYS:
            return
        if len(set(names)) != len(names):
            raise ValueError(f'Duplicate attributes on managed metadata: {key}')
        selector = 'property' if key.startswith('og:') else 'name'
        if set(names) != {selector, 'content'} or values.get(selector, '').lower() != key:
            raise ValueError(f'Ambiguous managed metadata attributes: {key}')
        line, col = self.getpos()
        start = self.lines[line - 1] + col
        self.spans.append((start, start + len(self.get_starttag_text())))
        self.values.setdefault(key, []).append(values['content'])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == 'head':
            if not self.in_head:
                raise ValueError('Unmatched head closing tag')
            self.closed += 1
            self.in_head = False

    def skeleton(self):
        parts, position = [], 0
        for start, end in self.spans:
            parts.append(self.text[position:start])
            position = end
        parts.append(self.text[position:])
        return ''.join(parts)


def check_head(before, after):
    # UTF-8 only; never rewrite another encoding just to pass this check.
    original = HeadMetadata(before.decode('utf-8'))
    proposed = HeadMetadata(after.decode('utf-8'))
    if original.skeleton() != proposed.skeleton():
        raise ValueError('HTML changed outside supported head metadata tags')
    duplicates = [key for key, vals in proposed.values.items() if len(vals) > 1]
    if duplicates:
        raise ValueError('Duplicate metadata: ' + ', '.join(sorted(duplicates)))
    return sorted(proposed.values)


def verify(root, baseline, html_paths, image_paths):
    if baseline.get('version') != 1 or baseline.get('root') != str(root):
        raise ValueError('Baseline does not match the target/version')
    html = {safe_relative(p) for p in html_paths}
    images = {safe_relative(p) for p in image_paths}
    for value in html | images:
        candidate = root
        for part in PurePosixPath(value).parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise ValueError(f'Symlinked allowlist path is forbidden: {value}')
    if html & images:
        raise ValueError('HTML and image allowlists overlap')
    if any(PurePosixPath(p).suffix.lower() not in {'.html', '.htm'} for p in html):
        raise ValueError('HTML allowlist must contain entry HTML files')
    if any(PurePosixPath(p).suffix.lower() not in {'.png', '.jpg', '.jpeg'} for p in images):
        raise ValueError('Image allowlist must contain PNG/JPEG files')
    previous, current = baseline['files'], inventory(root)
    changed = sorted(p for p in previous.keys() | current.keys()
                     if previous.get(p) != current.get(p))
    for path in changed:
        old, new = previous.get(path), current.get(path)
        if new is None:
            raise ValueError(f'Deletion is forbidden: {path}')
        if new['type'] != 'file':
            raise ValueError(f'Only regular file writes are allowed: {path}')
        if path in html:
            if old is None or old['type'] != 'file' or old['mode'] != new['mode']:
                raise ValueError(f'Entry HTML must already exist with unchanged mode: {path}')
        elif path in images:
            if old is not None:
                raise ValueError(f'Existing image overwrite forbidden; create a new image: {path}')
            with (root / path).open('rb') as image:
                magic = image.read(8)
            if not (magic == b'\x89PNG\r\n\x1a\n' or magic.startswith(b'\xff\xd8\xff')):
                raise ValueError(f'Not a PNG/JPEG signature: {path}')
        else:
            raise ValueError(f'Out-of-scope change: {path}')
    return changed


def external(root, path):
    root = root.resolve()
    resolved = Path(path).resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError('Audit scratch files must be outside the target repo')
    return resolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    snap = commands.add_parser('snapshot')
    snap.add_argument('--root', required=True)
    snap.add_argument('--out', required=True)
    check = commands.add_parser('verify')
    check.add_argument('--root', required=True)
    check.add_argument('--baseline', required=True)
    check.add_argument('--html', action='append', default=[])
    check.add_argument('--image', action='append', default=[])
    head = commands.add_parser('head-check')
    head.add_argument('--before', required=True)
    head.add_argument('--after', required=True)
    args = parser.parse_args()
    if args.command == 'head-check':
        keys = check_head(Path(args.before).read_bytes(), Path(args.after).read_bytes())
        print(json.dumps({'head_metadata_only': True, 'managed_keys': keys}))
        return
    root = Path(args.root).resolve(strict=True)
    if args.command == 'snapshot':
        output = external(root, args.out)
        snapshot = {'version': 1, 'root': str(root), 'files': inventory(root)}
        with output.open('x', encoding='utf-8') as stream:
            json.dump(snapshot, stream, sort_keys=True)
        print(json.dumps({'snapshot': str(output), 'readme_excluded': True}))
    else:
        baseline_path = external(root, args.baseline)
        baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
        changed = verify(root, baseline, args.html, args.image)
        print(json.dumps({'allowed_file_changes': changed, 'readme_excluded': True,
                          'html_content_requires_head_check': True}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, UnicodeError, KeyError, TypeError) as error:
        print(f'AUDIT FAILED: {error}', file=sys.stderr)
        sys.exit(1)
