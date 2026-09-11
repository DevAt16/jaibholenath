"""Unit tests for connection configuration and transaction boundaries."""
import pytest
from shiva_discovery.db import Connection, connection_options


def test_mysql_url_decodes_credentials_and_rejects_other_engines(monkeypatch):
    options = connection_options('mysql://u:p%40ss%2Fword@db.example:3307/temples')
    assert options['password'] == 'p@ss/word'
    assert options['port'] == 3307
    assert options['database'] == 'temples'
    assert options['autocommit'] is True
    assert options['charset'] == 'utf8mb4'
    for url in ['postgresql://u:secret@localhost/db', 'mysql://u:secret@host', 'mysql://u:secret@host:bad/db']:
        with pytest.raises(ValueError) as error:
            connection_options(url)
        assert 'secret' not in str(error.value)
    monkeypatch.setenv('MYSQL_PASSWORD', 'literal@password')
    monkeypatch.setenv('MYSQL_SSL_CA', '/secure/ca.pem')
    options = connection_options()
    assert options['password'] == 'literal@password'
    assert options['ssl_verify_identity'] and options['ssl_verify_cert']


class RawConnection:
    def __init__(self): self.events = []
    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql): self.events.append(sql)
    def begin(self): self.events.append('begin')
    def commit(self): self.events.append('commit')
    def rollback(self): self.events.append('rollback')
    def close(self): self.events.append('close')


def test_nested_failure_rolls_back_savepoint_without_committing_outer():
    raw = RawConnection()
    with Connection(raw) as conn:
        with conn.transaction():
            with pytest.raises(ValueError):
                with conn.transaction():
                    raise ValueError('failed record')
            assert 'commit' not in raw.events
    assert raw.events == ['begin', 'SAVEPOINT shiva_savepoint_1',
                          'ROLLBACK TO SAVEPOINT shiva_savepoint_1',
                          'RELEASE SAVEPOINT shiva_savepoint_1', 'commit', 'close']
    assert conn.depth == 0


def test_outer_failure_rolls_back_and_closes():
    raw = RawConnection()
    with pytest.raises(RuntimeError):
        with Connection(raw) as conn:
            with conn.transaction():
                raise RuntimeError('failure')
    assert raw.events == ['begin', 'rollback', 'close']
