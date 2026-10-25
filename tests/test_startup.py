import os

import pytest
from memopops.__main__ import load_environment


def test_host_configuration_is_literal_scoped_and_does_not_override_exported_values(tmp_path, monkeypatch):
    config = tmp_path / '.env'
    config.write_text("FALKORDB_HOST=file-host\nMEMOPOPS_AUTH_TOKENS='{}'\nUNRELATED=value\nMEMOPOPS_TEST_LITERAL='$(should-not-execute)'\n", encoding='utf-8')
    monkeypatch.setenv('FALKORDB_HOST', 'exported-host')
    monkeypatch.delenv('MEMOPOPS_AUTH_TOKENS', raising=False)
    monkeypatch.delenv('MEMOPOPS_TEST_LITERAL', raising=False)
    monkeypatch.delenv('UNRELATED', raising=False)
    try:
        load_environment(config)
        assert os.environ['FALKORDB_HOST'] == 'exported-host'
        assert os.environ['MEMOPOPS_AUTH_TOKENS'] == '{}'
        assert os.environ['MEMOPOPS_TEST_LITERAL'] == '$(should-not-execute)'
        assert 'UNRELATED' not in os.environ
    finally:
        os.environ.pop('MEMOPOPS_AUTH_TOKENS', None)
        os.environ.pop('MEMOPOPS_TEST_LITERAL', None)


def test_missing_host_configuration_is_actionable(tmp_path):
    with pytest.raises(ValueError, match='Configuration file not found'):
        load_environment(tmp_path / 'missing.env')
