"""All upgrades in these tests target new temporary fixture installations."""
import json
from pathlib import Path
import sqlite3
import sys
import pytest
from flask_migrate import upgrade
from sqlalchemy.engine import URL
from app import create_app
from app.extensions import db

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import apply_5001_independent_worker_upgrade as apply_helper
import check_5001_independent_worker_upgrade as check_helper
from backup_5001_before_independent_workers import backup_instance


@pytest.fixture()
def installation(tmp_path):
    folder = tmp_path / 'fixture-installation'
    folder.mkdir()
    database = folder / 'task_allocation.db'
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only',
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(database)),
        'SQLALCHEMY_ENGINE_OPTIONS': {}})
    app.instance_path = str(folder)
    with app.app_context():
        try:
            upgrade(directory=str(ROOT / 'migrations'), revision=check_helper.BASE)
        finally:
            db.session.remove()
            db.engine.dispose()
    with sqlite3.connect(database) as con:
        con.execute("INSERT INTO administrators (id,name,email,password_hash) VALUES (1,'Fixture admin','admin@test.invalid','disabled')")
        con.execute("INSERT INTO supervisors (id,name,email,password_hash) VALUES (1,'Fixture supervisor','supervisor@test.invalid','disabled')")
        con.execute("INSERT INTO onboarding_agents (id,name,email,password_hash,availability,account_disabled,workload) VALUES (1,'Fixture worker','netease-57@demo.invalid','disabled',0,1,4)")
        con.execute("INSERT INTO worker_source_bindings (agent_id,source_worker_id) VALUES (1,'57')")
        con.execute("INSERT INTO skills (id,name) VALUES (1,'NetEase capability 53')")
        con.execute("INSERT INTO agent_skills (agent_id,skill_id,proficiency_level) VALUES (1,1,'Observed participation')")
        con.execute("INSERT INTO tasks (id,task_type,supervisor_id,status) VALUES (1,'Fixture task',1,'In progress')")
        con.execute("INSERT INTO task_assignments (task_id,agent_id,supervisor_id,status,started_at) VALUES (1,1,1,'In progress','2026-10-30 07:00:00')")
    for name, value in {
        'netease_agent_bindings.json': {'schema_version': 1, 'status':'ready', 'worker_bindings': {'1':'57'}},
        'onboarding_capability_mapping.json': {'schema_version':1, 'skill_to_capabilities': {'NetEase capability 53':['53']}},
        'setup_complete.json': {'status':'fixture'},
    }.items():
        (folder / name).write_text(json.dumps(value), encoding='utf-8')
    return folder


def test_backup_rehearsal_and_apply_preserve_every_original_record(installation, monkeypatch):
    # Bypass the real port probe only for this disposable installation.
    monkeypatch.setattr(apply_helper, 'require_server_stopped', lambda: None)
    database = installation / 'task_allocation.db'
    before_revision, before_columns, before_rows = check_helper.snapshot(database)
    before_hashes = check_helper.file_hashes(installation)
    apply_helper.apply_to_instance(installation)
    revision, columns, rows = check_helper.snapshot(database)
    assert revision == [(check_helper.TARGET,)]
    assert columns == {**before_columns, check_helper.REGISTRATION_TABLE: check_helper.REGISTRATION_COLUMNS}
    assert rows == {**before_rows, check_helper.REGISTRATION_TABLE: []}
    after_hashes = check_helper.file_hashes(installation)
    assert all(after_hashes[n] == before_hashes[n] for n in check_helper.FILES[1:])
    backups = list((installation / 'backups').iterdir())
    assert len(backups) == 1
    assert check_helper.snapshot(backups[0] / 'task_allocation.db') == (before_revision, before_columns, before_rows)
    apply_helper.apply_to_instance(installation)
    assert check_helper.file_hashes(installation) == after_hashes
    assert list((installation / 'backups').iterdir()) == backups


def test_wrong_revision_is_refused_without_changes(installation, monkeypatch):
    monkeypatch.setattr(apply_helper, 'require_server_stopped', lambda: None)
    with sqlite3.connect(installation / 'task_allocation.db') as con:
        con.execute("UPDATE alembic_version SET version_num='unexpected'")
    before = check_helper.file_hashes(installation)
    with pytest.raises(ValueError, match='Expected migration'):
        apply_helper.apply_to_instance(installation)
    assert check_helper.file_hashes(installation) == before
    assert not (installation / 'backups').exists()


def test_tampered_backup_is_refused_without_changing_source(installation):
    backup = backup_instance(installation)
    before = check_helper.file_hashes(installation)
    (backup / 'setup_complete.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='hashes'):
        check_helper.check_backup(backup, installation / 'task_allocation.db', installation.parent)
    assert check_helper.file_hashes(installation) == before


def test_source_changed_during_rehearsal_is_not_upgraded(installation, monkeypatch):
    monkeypatch.setattr(apply_helper, 'require_server_stopped', lambda: None)
    def change_source(*args):
        (installation / 'setup_complete.json').write_text('{"changed":true}', encoding='utf-8')
    monkeypatch.setattr(apply_helper, 'check_backup', change_source)
    before = check_helper.snapshot(installation / 'task_allocation.db')
    with pytest.raises(ValueError, match='changed during rehearsal'):
        apply_helper.apply_to_instance(installation)
    assert check_helper.snapshot(installation / 'task_allocation.db') == before
