"""
Display section of "SqLite" DB Connector class.

Contains database connection logic specific to SqLite databases.
"""

# System Imports.

# User Imports.
from py_dbcn.connectors.core.display import BaseDisplay
from py_dbcn.logging import init_logging


# Import logger.
logger = init_logging(__name__)


class SqliteDisplay(BaseDisplay):
    """
    Logic for displaying queries and other project output in prettier format, for SqLite databases.
    """
    def __init__(self, parent, *args, **kwargs):
        # Call parent logic.
        super().__init__(parent, *args, **kwargs)

        logger.debug('Generating related (SqLite) Display class.')