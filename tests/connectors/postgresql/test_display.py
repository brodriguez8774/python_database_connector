"""
Tests for "display" logic of "PostgreSQL" DB Connector class.
"""

# System Imports.

# Internal Imports.
from .constants import (
    DESCRIBE_TABLE_QUERY,
    SHOW_TABLES_QUERY,
    COLUMNS_CLAUSE__BASIC,
    COLUMNS_CLAUSE__MINIMAL,
)
from .expected_display_output import ExpectedOutput
from .test_core import TestPostgresqlDatabaseParent
from tests.connectors.core.test_display import (
    CoreDisplayBaseTestMixin,
    CoreDisplayTablesTestMixin,
    CoreDisplayRecordsMixin,
)


class TestPostgresqlDisplay(TestPostgresqlDatabaseParent, CoreDisplayBaseTestMixin):
    """
    Tests "PostgreSQL" DB Connector class display logic.
    """
    @classmethod
    def setUpClass(cls):
        # Run parent setup logic.
        super().setUpClass()

        # Also call CoreTestMixin setup logic.
        cls.set_up_class()

        # Define database name to use in tests.
        cls.test_db_name = '{0}test_display__core'.format(cls.test_db_name_start)

        # Initialize database for tests.
        cls.connector.database.create(cls.test_db_name)
        cls.connector.database.use(cls.test_db_name)

        # Check that database has no tables.
        results = cls.connector.tables.show()
        if len(results) > 0:
            for result in results:
                cls.connector.tables.drop(result)

        # Define expected output to compare against.
        cls.expected_output = ExpectedOutput
        cls._show_tables_query = SHOW_TABLES_QUERY


class TestPostgresqlDisplayTables(TestPostgresqlDatabaseParent, CoreDisplayTablesTestMixin):
    """
    Tests "Postgresql" DB Connector class display logic.

    Specifically tests logic defined in "tables" display subclass.
    """
    @classmethod
    def setUpClass(cls):
        # Run parent setup logic.
        super().setUpClass()

        # Also call CoreTestMixin setup logic.
        cls.set_up_class()

        # Define database name to use in tests.
        cls.test_db_name = '{0}test_display__tables'.format(cls.test_db_name_start)

        # Initialize database for tests.
        cls.connector.database.create(cls.test_db_name)
        cls.connector.database.use(cls.test_db_name)

        # Check that database has no tables.
        results = cls.connector.tables.show()
        if len(results) > 0:
            for result in results:
                cls.connector.tables.drop(result)

        # Define expected output to compare against.
        cls.expected_output = ExpectedOutput
        cls._show_tables_query = SHOW_TABLES_QUERY
        cls._describe_table_query = DESCRIBE_TABLE_QUERY
        cls._columns_clause__minimal = COLUMNS_CLAUSE__MINIMAL
        cls._columns_clause__basic = COLUMNS_CLAUSE__BASIC


class TestPostgreSQLDisplayRecords(TestPostgresqlDatabaseParent, CoreDisplayRecordsMixin):
    """
    Tests "PostgreSQL" DB Connector class display logic.

    Specifically tests logic defined in "records" display subclass.
    """
    @classmethod
    def setUpClass(cls):
        # Run parent setup logic.
        super().setUpClass()

        # Also call CoreTestMixin setup logic.
        cls.set_up_class()

        # Define database name to use in tests.
        cls.test_db_name = '{0}test_display__records'.format(cls.test_db_name_start)

        # Initialize database for tests.
        cls.connector.database.create(cls.test_db_name)
        cls.connector.database.use(cls.test_db_name)

        # Check that database has no tables.
        results = cls.connector.tables.show()
        if len(results) > 0:
            for result in results:
                cls.connector.tables.drop(result)

        # Define expected output to compare against.
        cls.expected_output = ExpectedOutput
        cls._show_tables_query = SHOW_TABLES_QUERY
        cls._columns_clause__minimal = COLUMNS_CLAUSE__MINIMAL
        cls._columns_clause__basic = COLUMNS_CLAUSE__BASIC
