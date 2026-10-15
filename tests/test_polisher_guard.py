"""Safety regression tests; fixtures exist only in temporary directories."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/polisher/scripts/polisher_guard.py'
SPEC = importlib.util.spec_from_file_location('guard', SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.html = self.root / 'index.html'
        self.html.write_text('<html><head><title>Tool</title></head><body>App</body></html>')
        (self.root / 'app.js').write_text('const stable = true;')
        (self.root / 'README.md').write_text('Do not read on follow-up.')
        self.baseline = {'version': 1, 'root': str(self.root),
                         'files': guard.inventory(self.root)}

    def test_noop(self):
        self.assertEqual(guard.verify(self.root, self.baseline, [], []), [])

    def test_readme_is_not_opened(self):
        original = Path.open

        def refusing_open(path, *args, **kwargs):
            if path.parent == self.root and path.name.casefold() == 'readme.md':
                raise AssertionError('README accessed')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'open', refusing_open):
            inventory = guard.inventory(self.root)
            self.assertNotIn('README.md', inventory)
            guard.verify(self.root, self.baseline, [], [])

    def test_out_of_scope_write_even_with_html_allowed(self):
        (self.root / 'app.js').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Out-of-scope'):
            guard.verify(self.root, self.baseline, ['index.html'], [])

    def test_deletion_is_forbidden(self):
        self.html.unlink()
        with self.assertRaisesRegex(ValueError, 'Deletion'):
            guard.verify(self.root, self.baseline, ['index.html'], [])

    def test_user_dirty_content_preserved_as_baseline(self):
        (self.root / 'app.js').write_text('user work')
        baseline = {'version': 1, 'root': str(self.root), 'files': guard.inventory(self.root)}
        self.assertEqual(guard.verify(self.root, baseline, [], []), [])
        (self.root / 'app.js').write_text('overwritten user work')
        with self.assertRaises(ValueError):
            guard.verify(self.root, baseline, [], [])

    def test_existing_asset_cannot_be_overwritten(self):
        image = self.root / 'original.png'
        image.write_bytes(b'\x89PNG\r\n\x1a\nold')
        baseline = {'version': 1, 'root': str(self.root), 'files': guard.inventory(self.root)}
        image.write_bytes(b'\x89PNG\r\n\x1a\nnew')
        with self.assertRaisesRegex(ValueError, 'overwrite forbidden'):
            guard.verify(self.root, baseline, [], ['original.png'])

    def test_new_preview_and_repeat_noop(self):
        (self.root / 'social.png').write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        self.assertEqual(guard.verify(self.root, self.baseline, [], ['social.png']), ['social.png'])
        updated = {'version': 1, 'root': str(self.root), 'files': guard.inventory(self.root)}
        self.assertEqual(guard.verify(self.root, updated, [], ['social.png']), [])

    def test_invalid_raster_rejected(self):
        (self.root / 'social.png').write_text('<svg></svg>')
        with self.assertRaisesRegex(ValueError, 'signature'):
            guard.verify(self.root, self.baseline, [], ['social.png'])

    def test_symlink_target_never_followed(self):
        self.html.unlink()
        self.html.symlink_to(self.root / 'README.md')
        with self.assertRaisesRegex(ValueError, 'Symlinked'):
            guard.verify(self.root, self.baseline, ['index.html'], [])

    def test_symlink_parent_in_allowlist_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / 'linked-assets').symlink_to(outside, target_is_directory=True)
            baseline = {'version': 1, 'root': str(self.root), 'files': guard.inventory(self.root)}
            with self.assertRaisesRegex(ValueError, 'Symlinked'):
                guard.verify(self.root, baseline, [], ['linked-assets/social.png'])

    def test_traversal_and_readme_allowlist_rejected(self):
        for path in ['../outside.html', '/tmp/x.html', '.git/config', 'README.md']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                guard.safe_relative(path)

    def test_scratch_cannot_be_in_repo(self):
        with self.assertRaises(ValueError):
            guard.external(self.root, self.root / 'baseline.json')

    def test_metadata_only_and_idempotence(self):
        before = self.html.read_bytes()
        after = before.replace(b'</head>', b'<meta property="og:title" content="A &amp; B"></head>')
        self.assertIn('og:title', guard.check_head(before, after))
        self.assertEqual(guard.check_head(after, after), ['og:title'])

    def test_duplicate_cleanup(self):
        a = b'<meta property="og:title" content="A">'
        before = b'<head>' + a + a + b'</head><body>x</body>'
        after = b'<head>' + a + b'</head><body>x</body>'
        guard.check_head(before, after)
        with self.assertRaisesRegex(ValueError, 'Duplicate metadata'):
            guard.check_head(after, before)

    def test_body_scripts_title_and_other_head_bytes_protected(self):
        base = b'<head><title>T</title><script>const a=1;</script></head><body>X</body>'
        for old, new in [(b'>X<', b'>Y<'), (b'>T<', b'>U<'), (b'a=1', b'a=2'),
                         (b'</head>', b'<link rel="canonical" href="x"></head>')]:
            with self.subTest(old=old), self.assertRaisesRegex(ValueError, 'outside'):
                guard.check_head(base, base.replace(old, new))

    def test_script_text_is_not_metadata(self):
        before = b'<head><script>const s=\'<meta property="og:title" content="A">\';</script></head>'
        with self.assertRaisesRegex(ValueError, 'outside'):
            guard.check_head(before, before.replace(b'content="A"', b'content="B"'))

    def test_outside_head_metadata_edit_rejected(self):
        before = b'<head></head><body><meta property="og:title" content="A"></body>'
        with self.assertRaisesRegex(ValueError, 'outside'):
            guard.check_head(before, before.replace(b'content="A"', b'content="B"'))

    def test_missing_head_and_ambiguous_attributes(self):
        for after in [b'<div>no head</div>',
                      b'<head><meta property="og:title" content="a" content="b"></head>',
                      b'<head><meta name="og:title" content="a"></head>']:
            with self.subTest(after=after), self.assertRaises(ValueError):
                guard.check_head(b'<head></head>', after)


if __name__ == '__main__':
    unittest.main()
