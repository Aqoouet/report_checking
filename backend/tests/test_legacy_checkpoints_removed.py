from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class LegacyCheckpointsRemovedTests(unittest.TestCase):
    def test_checkpoints_package_is_removed(self) -> None:
        backend_root = Path(__file__).resolve().parents[1]

        self.assertFalse((backend_root / "checkpoints").exists())


if __name__ == "__main__":
    unittest.main()
