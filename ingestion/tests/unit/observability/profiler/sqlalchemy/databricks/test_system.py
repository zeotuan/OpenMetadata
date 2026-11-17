"""
Test Databricks system metrics computer.
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from metadata.generated.schema.entity.data.table import DmlOperationType
from metadata.profiler.metrics.system.databricks.system import DatabricksSystemMetricsComputer
from metadata.profiler.processor.runner import QueryRunner


class TestDatabricksSystemMetricsComputer:
    """Test Databricks system metrics computer behavior."""

    @pytest.fixture
    def session(self):
        session = Mock()
        session.execute.return_value = [
            Mock(database="catalog", schema="schema", table="table", starttime=datetime(2024, 1, 1), rows=3),
            Mock(database="catalog", schema="schema", table="table", starttime=datetime(2024, 1, 2), rows=0),
        ]
        return session

    @pytest.fixture
    def computer(self, session):
        runner = Mock(spec=QueryRunner)
        runner.schema_name = "schema"
        runner.table_name = "table"
        return DatabricksSystemMetricsComputer(session=session, runner=runner, catalog="catalog")

    @pytest.mark.parametrize(
        ("method", "operation", "merge_metric", "metric"),
        [
            ("get_inserts", DmlOperationType.INSERT, "numTargetRowsInserted", "numOutputRows"),
            ("get_updates", DmlOperationType.UPDATE, "numTargetRowsUpdated", "numUpdatedRows"),
            ("get_deletes", DmlOperationType.DELETE, "numTargetRowsDeleted", "numDeletedRows"),
        ],
    )
    def test_merge_commits_count_only_their_own_rows(self, computer, session, method, operation, merge_metric, metric):
        """numOutputRows of a MERGE also counts updated and copied rows: it must not be added to the MERGE counter."""
        result = getattr(computer, method)()

        assert [(profile.operation, profile.rowsAffected) for profile in result] == [(operation, 3)]
        executed_query = str(session.execute.call_args.args[0])
        assert (
            f"COALESCE(CAST(operationMetrics.{merge_metric} AS BIGINT), "
            f"CAST(operationMetrics.{metric} AS BIGINT), 0) AS rows"
        ) in executed_query
        assert "FROM (DESCRIBE HISTORY `catalog`.`schema`.`table`)" in executed_query
