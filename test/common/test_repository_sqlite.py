import pytest

from common.repository import SQLiteRepository
from .test_repository import *


class TestSqliteRepository(make_test_case(SQLiteRepository)):
    pass
#    def test_specific(self, entries):
#        assert len(entries) > 0


if __name__ == "__main__":
    pytest.main(['-v', __file__])
