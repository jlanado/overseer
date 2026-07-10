"""
Tests for tester_node's .overseer.yaml-driven test command override
(see nodes/tester.py). Covers the config-loading logic only — no
subprocess/pytest execution needed, so these run against real files via
pytest's tmp_path fixture, no mocking required.
"""
from nodes.tester import DEFAULT_TEST_COMMAND, _load_test_command


def test_defaults_to_pytest_when_no_config_file(tmp_path):
    assert _load_test_command(str(tmp_path)) == DEFAULT_TEST_COMMAND


def test_reads_custom_command_from_overseer_yaml(tmp_path):
    (tmp_path / ".overseer.yaml").write_text("test_command: npm test -- --ci\n")
    assert _load_test_command(str(tmp_path)) == ["npm", "test", "--", "--ci"]


def test_falls_back_to_default_on_malformed_yaml(tmp_path):
    (tmp_path / ".overseer.yaml").write_text(": not valid: yaml: [\n")
    assert _load_test_command(str(tmp_path)) == DEFAULT_TEST_COMMAND


def test_falls_back_to_default_when_test_command_key_missing(tmp_path):
    (tmp_path / ".overseer.yaml").write_text("other_key: value\n")
    assert _load_test_command(str(tmp_path)) == DEFAULT_TEST_COMMAND


def test_falls_back_to_default_when_test_command_is_empty_string(tmp_path):
    (tmp_path / ".overseer.yaml").write_text("test_command: ''\n")
    assert _load_test_command(str(tmp_path)) == DEFAULT_TEST_COMMAND
