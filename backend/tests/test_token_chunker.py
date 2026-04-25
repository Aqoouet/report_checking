from __future__ import annotations

import sys
import types
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

fake_tiktoken = types.ModuleType("tiktoken")
fake_tiktoken.get_encoding = lambda _name: types.SimpleNamespace(encode=lambda text: text.split())  # type: ignore[attr-defined]
sys.modules.setdefault("tiktoken", fake_tiktoken)

from doc_models import Section
from token_chunker import chunk_sections


class TokenChunkerTests(unittest.TestCase):
    def test_doc_chunk_size_is_read_at_call_time(self) -> None:
        section = Section(number="1", title="Title", text="one\ntwo\nthree\nfour", level=1)

        with unittest.mock.patch.dict("os.environ", {"DOC_CHUNK_SIZE": "10000"}):
            self.assertEqual(len(chunk_sections([section])), 1)

        with unittest.mock.patch.dict("os.environ", {"DOC_CHUNK_SIZE": "1"}):
            self.assertGreater(len(chunk_sections([section])), 1)

    def test_invalid_env_default_is_used(self) -> None:
        section = Section(number="1", title="Title", text="short", level=1)

        with unittest.mock.patch.dict("os.environ", {"DOC_CHUNK_SIZE": "invalid"}):
            self.assertEqual(chunk_sections([section]), [section])

    def test_explicit_non_positive_limit_is_rejected(self) -> None:
        section = Section(number="1", title="Title", text="short", level=1)

        with self.assertRaises(ValueError):
            chunk_sections([section], max_tokens=0)


if __name__ == "__main__":
    unittest.main()
