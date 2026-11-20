"""Verify the pytest-to-Node harness boundary."""

import pytest

from .node_harness import run_node_harness


# DHF-TEST: genesis-wp-ha/requirement-1 genesis-wp-ha/ac-125
@pytest.mark.parametrize("stdout", ["", "HARNESS-COMPLETE\nmore output"])
def test_successful_early_exit_fails_harness_check(tmp_path, stdout):
    script = tmp_path / "early_exit.mjs"
    script.write_text(
        f'console.log({stdout!r});\n'
        'console.error("exited before the last assertion");\n'
        'process.exit(0);\n'
        'console.log("HARNESS-COMPLETE");\n',
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="exited before the last assertion"):
        run_node_harness(script)
