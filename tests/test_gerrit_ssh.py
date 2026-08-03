import sys
import unittest

from collectors.gerrit_ssh import run_command


class GerritSshTests(unittest.TestCase):
    def test_run_command_replaces_invalid_bytes(self):
        result = run_command(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'\\x81')",
            ],
            timeout=10,
        )

        self.assertEqual(result.stdout, "�")
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
