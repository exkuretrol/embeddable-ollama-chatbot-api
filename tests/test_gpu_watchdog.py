"""Tests for scripts/gpu_watchdog.py logging and control flow."""

import logging
import logging.handlers
from unittest.mock import MagicMock, patch

import pytest

from scripts import gpu_watchdog


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

class TestLoggingSetup:
    """Verify the logging infrastructure is wired correctly."""

    def test_logger_exists_with_correct_name(self):
        assert gpu_watchdog.log.name == "gpu-watchdog"

    def test_logger_level_is_info(self):
        assert gpu_watchdog.log.level == logging.INFO

    def test_file_handler_is_timed_rotating(self):
        file_handlers = [
            h
            for h in gpu_watchdog.log.handlers
            if isinstance(h, logging.handlers.TimedRotatingFileHandler)
        ]
        assert len(file_handlers) == 1

    def test_file_handler_rotates_at_midnight_utc(self):
        handler = next(
            h
            for h in gpu_watchdog.log.handlers
            if isinstance(h, logging.handlers.TimedRotatingFileHandler)
        )
        assert handler.when == "MIDNIGHT"
        assert handler.utc is True

    def test_file_handler_keeps_30_backups(self):
        handler = next(
            h
            for h in gpu_watchdog.log.handlers
            if isinstance(h, logging.handlers.TimedRotatingFileHandler)
        )
        assert handler.backupCount == 30

    def test_console_handler_present(self):
        stream_handlers = [
            h
            for h in gpu_watchdog.log.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.handlers.TimedRotatingFileHandler)
        ]
        assert len(stream_handlers) == 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_ssh_run(responses: list[tuple[int, str, str]]):
    """Return a side_effect function that pops responses in order."""
    it = iter(responses)
    def _side_effect(_client, _cmd):
        return next(it)
    return _side_effect


# ---------------------------------------------------------------------------
# main() control flow
# ---------------------------------------------------------------------------

class TestMain:
    """Test main() logic with mocked SSH."""

    @patch.object(gpu_watchdog, "SSH_HOST", "")
    def test_missing_ssh_host_logs_error_and_returns_1(self, caplog):
        with caplog.at_level(logging.ERROR, logger="gpu-watchdog"):
            assert gpu_watchdog.main() == 1
        assert "GPU_WATCHDOG_SSH_HOST is not set" in caplog.text

    @patch.object(gpu_watchdog, "DEPLOYMENT", "")
    @patch.object(gpu_watchdog, "SSH_HOST", "host")
    def test_missing_deployment_logs_error_and_returns_1(self, caplog):
        with caplog.at_level(logging.ERROR, logger="gpu-watchdog"):
            assert gpu_watchdog.main() == 1
        assert "GPU_WATCHDOG_K8S_DEPLOYMENT is not set" in caplog.text

    @patch.object(gpu_watchdog, "DEPLOYMENT", "my-deploy")
    @patch.object(gpu_watchdog, "SSH_HOST", "host")
    @patch.object(gpu_watchdog, "create_ssh_client", side_effect=OSError("conn refused"))
    def test_ssh_failure_logs_exception_and_returns_1(self, _mock, caplog):
        with caplog.at_level(logging.ERROR, logger="gpu-watchdog"):
            assert gpu_watchdog.main() == 1
        assert "SSH connection to host failed" in caplog.text

    @patch.object(gpu_watchdog, "DEPLOYMENT", "my-deploy")
    @patch.object(gpu_watchdog, "SSH_HOST", "host")
    @patch.object(gpu_watchdog, "create_ssh_client")
    @patch.object(gpu_watchdog, "get_pod_name", return_value=None)
    def test_no_pod_logs_error_and_returns_1(self, _gp, _ssh, caplog):
        _ssh.return_value = MagicMock()
        with caplog.at_level(logging.ERROR, logger="gpu-watchdog"):
            assert gpu_watchdog.main() == 1
        assert "Could not find pod" in caplog.text

    @patch.object(gpu_watchdog, "DEPLOYMENT", "my-deploy")
    @patch.object(gpu_watchdog, "SSH_HOST", "host")
    @patch.object(gpu_watchdog, "create_ssh_client")
    @patch.object(gpu_watchdog, "get_pod_name", return_value="pod-abc")
    @patch.object(gpu_watchdog, "check_gpu", return_value=True)
    def test_gpu_ok_logs_passed_and_returns_0(self, _cg, _gp, _ssh, caplog):
        _ssh.return_value = MagicMock()
        with caplog.at_level(logging.INFO, logger="gpu-watchdog"):
            assert gpu_watchdog.main() == 0
        assert "GPU check passed" in caplog.text

    @patch.object(gpu_watchdog, "SCALE_DOWN_WAIT", 0)
    @patch.object(gpu_watchdog, "DEPLOYMENT", "my-deploy")
    @patch.object(gpu_watchdog, "SSH_HOST", "host")
    @patch.object(gpu_watchdog, "create_ssh_client")
    @patch.object(gpu_watchdog, "get_pod_name", return_value="pod-abc")
    @patch.object(gpu_watchdog, "check_gpu", return_value=False)
    @patch.object(gpu_watchdog, "restart_deployment")
    def test_gpu_fail_logs_warning_and_restarts(self, _rd, _cg, _gp, _ssh, caplog):
        _ssh.return_value = MagicMock()
        with caplog.at_level(logging.WARNING, logger="gpu-watchdog"):
            assert gpu_watchdog.main() == 0
        assert "GPU check FAILED" in caplog.text
        _rd.assert_called_once()

    @patch.object(gpu_watchdog, "DEPLOYMENT", "my-deploy")
    @patch.object(gpu_watchdog, "SSH_HOST", "host")
    @patch.object(gpu_watchdog, "create_ssh_client")
    @patch.object(gpu_watchdog, "get_pod_name", side_effect=RuntimeError("boom"))
    def test_unexpected_error_logs_exception_and_returns_1(self, _gp, _ssh, caplog):
        _ssh.return_value = MagicMock()
        with caplog.at_level(logging.ERROR, logger="gpu-watchdog"):
            assert gpu_watchdog.main() == 1
        assert "Unexpected error" in caplog.text


# ---------------------------------------------------------------------------
# wait_for_pod_ready
# ---------------------------------------------------------------------------

class TestWaitForPodReady:
    @patch.object(gpu_watchdog, "POD_READY_TIMEOUT", 5)
    @patch.object(gpu_watchdog, "POD_READY_POLL_INTERVAL", 0)
    @patch.object(gpu_watchdog, "ssh_run", return_value=(0, "True", ""))
    def test_returns_true_when_pod_ready(self, _ssh):
        assert gpu_watchdog.wait_for_pod_ready(MagicMock()) is True

    @patch.object(gpu_watchdog, "POD_READY_TIMEOUT", 0)
    @patch.object(gpu_watchdog, "POD_READY_POLL_INTERVAL", 0)
    @patch.object(gpu_watchdog, "ssh_run", return_value=(0, "False", ""))
    def test_returns_false_on_timeout(self, _ssh):
        assert gpu_watchdog.wait_for_pod_ready(MagicMock()) is False

    @patch.object(gpu_watchdog, "POD_READY_TIMEOUT", 5)
    @patch.object(gpu_watchdog, "POD_READY_POLL_INTERVAL", 0)
    def test_polls_until_ready(self):
        responses = iter([(0, "False", ""), (1, "", "no pod"), (0, "True", "")])
        with patch.object(
            gpu_watchdog, "ssh_run", side_effect=lambda _c, _cmd: next(responses)
        ):
            assert gpu_watchdog.wait_for_pod_ready(MagicMock()) is True


# ---------------------------------------------------------------------------
# run_post_restart_cmd
# ---------------------------------------------------------------------------

class TestRunPostRestartCmd:
    @patch.object(
        gpu_watchdog, "POST_RESTART_CMD", "/home/shared/ollama/connect_models.sh"
    )
    @patch.object(gpu_watchdog, "ssh_run", return_value=(0, "ok", ""))
    def test_success_returns_true_and_logs_command(self, _ssh, caplog):
        with caplog.at_level(logging.INFO, logger="gpu-watchdog"):
            assert gpu_watchdog.run_post_restart_cmd(MagicMock()) is True
        assert "/home/shared/ollama/connect_models.sh" in caplog.text

    @patch.object(gpu_watchdog, "POST_RESTART_CMD", "/some/cmd")
    @patch.object(gpu_watchdog, "ssh_run", return_value=(1, "", "boom"))
    def test_failure_logs_error_and_returns_false(self, _ssh, caplog):
        with caplog.at_level(logging.ERROR, logger="gpu-watchdog"):
            assert gpu_watchdog.run_post_restart_cmd(MagicMock()) is False
        assert "post-restart command failed" in caplog.text.lower()

    @patch.object(gpu_watchdog, "POST_RESTART_CMD", "")
    @patch.object(gpu_watchdog, "ssh_run")
    def test_empty_command_is_skipped(self, mock_ssh, caplog):
        with caplog.at_level(logging.INFO, logger="gpu-watchdog"):
            assert gpu_watchdog.run_post_restart_cmd(MagicMock()) is True
        mock_ssh.assert_not_called()


# ---------------------------------------------------------------------------
# restart_deployment logging
# ---------------------------------------------------------------------------

class TestRestartDeployment:
    @patch.object(gpu_watchdog, "SCALE_DOWN_WAIT", 0)
    @patch.object(gpu_watchdog, "wait_for_pod_ready", return_value=True)
    @patch.object(gpu_watchdog, "run_post_restart_cmd", return_value=True)
    @patch.object(gpu_watchdog, "ssh_run", return_value=(0, "", ""))
    def test_restart_logs_scale_events(self, _ssh, _rpc, _wpr, caplog):
        client = MagicMock()
        with caplog.at_level(logging.INFO, logger="gpu-watchdog"):
            gpu_watchdog.restart_deployment(client)
        assert "Scaling deployment to 0" in caplog.text
        assert "Scaling deployment to 1" in caplog.text
        assert "Deployment restarted successfully" in caplog.text

    @patch.object(gpu_watchdog, "SCALE_DOWN_WAIT", 0)
    @patch.object(gpu_watchdog, "wait_for_pod_ready", return_value=True)
    @patch.object(gpu_watchdog, "run_post_restart_cmd", return_value=True)
    @patch.object(gpu_watchdog, "ssh_run", return_value=(0, "", ""))
    def test_restart_runs_post_restart_cmd_after_pod_ready(
        self, _ssh, mock_rpc, mock_wpr, caplog
    ):
        client = MagicMock()
        gpu_watchdog.restart_deployment(client)
        mock_wpr.assert_called_once_with(client)
        mock_rpc.assert_called_once_with(client)

    @patch.object(gpu_watchdog, "SCALE_DOWN_WAIT", 0)
    @patch.object(gpu_watchdog, "wait_for_pod_ready", return_value=False)
    @patch.object(gpu_watchdog, "run_post_restart_cmd")
    @patch.object(gpu_watchdog, "ssh_run", return_value=(0, "", ""))
    def test_restart_skips_post_restart_cmd_when_pod_not_ready(
        self, _ssh, mock_rpc, _wpr, caplog
    ):
        client = MagicMock()
        with caplog.at_level(logging.ERROR, logger="gpu-watchdog"):
            gpu_watchdog.restart_deployment(client)
        assert "did not become Ready" in caplog.text
        mock_rpc.assert_not_called()
