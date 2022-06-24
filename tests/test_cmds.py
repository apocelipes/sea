import os
import shutil
import sys
from unittest import mock

import pytest

from sea import cli


def test_cmd_server(app):
    sys.argv = "sea s".split()
    with mock.patch("sea.server.threading.Server", autospec=True) as mocked:
        assert cli.main() == 0
        mocked.return_value.run.assert_called_with()

    sys.argv = "sea s -M multiprocessing".split()
    with mock.patch("sea.server.multiprocessing.Server", autospec=True) as mocked:
        assert cli.main() == 0
        mocked.return_value.run.assert_called_with()


def test_cmd_console(app):
    sys.argv = "sea c".split()
    mocked = mock.MagicMock()
    with mock.patch.dict("sys.modules", {"IPython": mocked}):
        assert cli.main() == 0
        assert mocked.embed.called


def test_cmd_generate():
    sys.argv = (
        "sea g -I /path/to/protos -I /another/path/to/protos "
        "hello.proto test.proto"
    ).split()

    with mock.patch("grpc_tools.protoc.main", return_value=0) as mocked:
        assert cli.main() == 0
        import grpc_tools

        well_known_path = os.path.join(
            os.path.dirname(grpc_tools.__file__), "_proto"
        )
        proto_out = os.path.join(os.getcwd(), "protos")
        cmd = [
            "grpc_tools.protoc",
            "--proto_path",
            "/path/to/protos",
            "--proto_path",
            "/another/path/to/protos",
            "--proto_path",
            well_known_path,
            "--python_out",
            proto_out,
            "--grpc_python_out",
            proto_out,
            "hello.proto",
            "test.proto",
        ]
        mocked.assert_called_with(cmd)


def test_cmd_new():
    shutil.rmtree("tests/myproject", ignore_errors=True)
    sys.argv = ("sea new tests/myproject" " --skip-git --skip-peewee").split()
    assert cli.main() == 0
    correct_code = """\
    # import myproject_pb2
    # import myproject_pb2_grpc

    # from sea.servicer import ServicerMeta


    # class MyprojectServicer(myproject_pb2_grpc.MyprojectServicer, metaclass=ServicerMeta):

    #     pass
    """
    with open("./tests/myproject/app/servicers.py", "r") as f:
        content = f.read()

    from textwrap import dedent

    assert content == dedent(correct_code).rstrip()
    assert not os.path.exists("./tests/myproject/condfigs/default/peewee.py")
    assert os.path.exists("./tests/myproject/app/async_tasks.py")
    assert os.path.exists("./tests/myproject/app/buses.py")

    correct_code = """\
    sea
    cachext
    celery
    sentry-sdk
    """
    with open("./tests/myproject/requirements.txt", "r") as f:
        content = f.read()
    assert content == dedent(correct_code)

    shutil.rmtree("tests/myproject")


def test_cmd_job(app):
    with mock.patch("os.getcwd", return_value=app.root_path):
        sys.argv = "sea plusone -n 100".split()
        assert cli.main() is None
        assert app.config.get("NUMBER") == 101
        sys.argv = "sea config_hello".split()
        assert isinstance(cli.main(), cli.JobException)

    class EntryPoint:
        def load(self):
            @cli.jobm.job("xyz")
            def f2():
                app.config["XYZ"] = "hello"

            return f2

    class FailedEntryPoint:
        def load(self):
            raise Exception("Failed entry point")

    def new_entry_iter(name):
        return [EntryPoint(), FailedEntryPoint()]

    mock_logger = mock.Mock()
    with mock.patch(
        "pkg_resources.iter_entry_points", new=new_entry_iter
    ), mock.patch("logging.getLogger", return_value=mock_logger):
        sys.argv = "sea xyz".split()
        assert cli.main() is None
        assert app.config.get("XYZ") == "hello"
        mock_logger.error.assert_called_with(
            "error has occurred during pkg loading: Failed entry point"
        )


def test_main():
    sys.argv = "sea -h".split()
    with pytest.raises(SystemExit):
        cli.main()
    # no arguments scenes
    sys.argv = ["sea"]
    with pytest.raises(SystemExit):
        cli.main()
