from nte_owner.storage import clear_run_screenshots
import pytest


def test_clear_only_generated_screenshots_and_report_freed_size(tmp_path):
    logs=tmp_path/'logs';logs.mkdir()
    for name in ['20261101-160331-963055-error.png','20261101-160137-898560-stopped.png']:
        (logs/name).write_bytes(b'1234')
    (logs/'20261101-160331-963055.jsonl').write_text('log')
    (logs/'reference.png').write_bytes(b'image')
    (tmp_path/'profile.json').write_text('settings')
    templates=tmp_path/'templates';templates.mkdir();(templates/'target.png').write_bytes(b'template')
    (logs/'20261101-160331-963056-error.png').symlink_to(templates/'target.png')
    count,size,failures=clear_run_screenshots(tmp_path)
    assert (count,size,failures)==(2,8,[])
    assert (logs/'reference.png').exists() and (logs/'20261101-160331-963055.jsonl').exists()
    assert (templates/'target.png').read_bytes()==b'template'
    assert (tmp_path/'profile.json').read_text()=='settings'
    assert clear_run_screenshots(tmp_path)==(0,0,[])


def test_clear_refuses_redirected_directory(tmp_path):
    outside=tmp_path/'outside';outside.mkdir();(tmp_path/'logs').symlink_to(outside)
    with pytest.raises(ValueError):clear_run_screenshots(tmp_path)
