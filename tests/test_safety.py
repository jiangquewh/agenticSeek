import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sources.tools.safety import is_unsafe


@unittest.skipIf(sys.platform.startswith("win"), "unix command list")
class TestIsUnsafeUnix(unittest.TestCase):
    """is_unsafe used substring matching, so legitimate commands containing
    an unsafe word as a substring were incorrectly flagged."""

    def test_blocks_rm(self):
        self.assertTrue(is_unsafe("rm -rf /tmp/foo"))

    def test_blocks_git(self):
        self.assertTrue(is_unsafe("git push --force"))

    def test_blocks_force_flag(self):
        self.assertTrue(is_unsafe("mv a b --force"))

    def test_blocks_kill(self):
        self.assertTrue(is_unsafe("kill -9 1234"))

    def test_allows_word_containing_git(self):
        self.assertFalse(is_unsafe("echo digital"))

    def test_allows_word_containing_tee(self):
        self.assertFalse(is_unsafe("echo committee"))

    def test_allows_word_containing_kill(self):
        self.assertFalse(is_unsafe("echo skillful"))

    def test_allows_word_containing_rm(self):
        self.assertFalse(is_unsafe("echo farm"))

    def test_allows_word_containing_dd(self):
        self.assertFalse(is_unsafe("echo address"))

    def test_handles_unparseable_quotes(self):
        self.assertTrue(is_unsafe('rm "unclosed'))

    def test_blocks_absolute_path_rm(self):
        self.assertTrue(is_unsafe("/bin/rm -rf /tmp/foo"))

    def test_blocks_relative_path_rm(self):
        self.assertTrue(is_unsafe("./rm important"))

    def test_blocks_absolute_path_git(self):
        self.assertTrue(is_unsafe("sudo /usr/bin/git push"))

    def test_blocks_absolute_path_dd(self):
        self.assertTrue(is_unsafe("/usr/local/bin/dd if=/dev/zero of=/dev/sda"))


if __name__ == "__main__":
    unittest.main()
