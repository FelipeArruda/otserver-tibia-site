from unittest.mock import patch

import pytest

from accounts.tasks import run_otserver_health_check


@pytest.mark.django_db
def test_run_otserver_health_check_task_calls_service() -> None:
    with patch(
        "accounts.tasks.run_scheduled_otserver_health_checks",
        return_value=[{"server": "a"}, {"server": "b"}],
    ) as service_mock:
        result = run_otserver_health_check.apply().result

    service_mock.assert_called_once_with()
    assert result == {"checked_count": 2}
