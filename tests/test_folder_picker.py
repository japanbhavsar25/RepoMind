"""Automated tests for native Windows folder picker endpoint and subprocess runner."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.folder_picker import (
    _build_powershell_script,
    _build_python_script,
    _pick_folder_powershell,
    _pick_folder_python_subprocess,
    pick_folder_native,
)


def test_browse_folder_selected():
    client = TestClient(app)
    with patch(
        "backend.routers.repos.pick_folder_native",
        new_callable=AsyncMock,
        return_value=("selected", "D:\\Projects\\alpha", None),
    ):
        res = client.post("/api/repos/browse", json={"initial_path": None})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "selected"
    assert data["path"] == "D:\\Projects\\alpha"
    assert data["cancelled"] is False
    assert data["error"] is None


def test_browse_folder_cancelled():
    client = TestClient(app)
    with patch(
        "backend.routers.repos.pick_folder_native",
        new_callable=AsyncMock,
        return_value=("cancelled", None, None),
    ):
        res = client.post("/api/repos/browse", json={"initial_path": None})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "cancelled"
    assert data["path"] is None
    assert data["cancelled"] is True
    assert data["error"] is None


def test_browse_folder_timed_out():
    client = TestClient(app)
    with patch(
        "backend.routers.repos.pick_folder_native",
        new_callable=AsyncMock,
        return_value=("cancelled", None, "Folder selection timed out after 120 seconds"),
    ):
        res = client.post("/api/repos/browse", json={"initial_path": None})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "cancelled"
    assert data["path"] is None
    assert data["cancelled"] is True
    assert "timed out" in data["error"]


def test_browse_folder_dialog_exception():
    client = TestClient(app)
    with patch(
        "backend.routers.repos.pick_folder_native",
        new_callable=AsyncMock,
        return_value=("error", None, "Unable to initialize dialog window"),
    ):
        res = client.post("/api/repos/browse", json={"initial_path": None})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "error"
    assert data["path"] is None
    assert data["cancelled"] is False
    assert "Unable to initialize dialog window" in data["error"]


def test_browse_folder_null_byte_rejected():
    client = TestClient(app)
    res = client.post("/api/repos/browse", json={"initial_path": "C:\\foo\0bar"})
    assert res.status_code == 400
    assert "null bytes" in res.json()["detail"].lower()


def test_browse_folder_non_local_client_rejected():
    # Simulate a remote client IP
    client = TestClient(app, client=("198.51.100.5", 54321))
    res = client.post("/api/repos/browse", json={"initial_path": None})
    assert res.status_code == 403
    assert "restricted to local machine" in res.json()["detail"].lower()


def test_browse_folder_cross_origin_rejected():
    client = TestClient(app)
    res = client.post(
        "/api/repos/browse",
        json={"initial_path": None},
        headers={"Origin": "https://malicious-external-site.com"},
    )
    assert res.status_code == 403
    assert "cross-origin request rejected" in res.json()["detail"].lower()


def test_browse_folder_allowed_origin():
    client = TestClient(app)
    with patch(
        "backend.routers.repos.pick_folder_native",
        new_callable=AsyncMock,
        return_value=("selected", "D:\\Allowed\\Repo", None),
    ):
        res = client.post(
            "/api/repos/browse",
            json={"initial_path": None},
            headers={"Origin": "http://localhost:5173"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "selected"
    assert data["path"] == "D:\\Allowed\\Repo"


# Subprocess unit tests & cleanup tests
def test_build_powershell_script(tmp_path):
    # With valid directory
    script = _build_powershell_script(str(tmp_path))
    assert "FolderBrowserDialog" in script
    assert f"$dialog.SelectedPath = '{str(tmp_path)}'" in script

    # Without directory
    script_none = _build_powershell_script(None)
    assert "FolderBrowserDialog" in script_none
    assert "$dialog.SelectedPath =" not in script_none


def test_powershell_subprocess_selection(tmp_path):
    import asyncio

    async def _run():
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(str(tmp_path).encode("utf-8"), b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            status, path, error = await _pick_folder_powershell("powershell.exe", None, 10.0)

        assert status == "selected"
        assert path == str(tmp_path.resolve())
        assert error is None

    asyncio.run(_run())


def test_powershell_subprocess_cancellation():
    import asyncio

    async def _run():
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            status, path, error = await _pick_folder_powershell("powershell.exe", None, 10.0)

        assert status == "cancelled"
        assert path is None
        assert error is None

    asyncio.run(_run())


def test_powershell_subprocess_timeout_cleanup():
    import asyncio

    async def _run():
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError("Process took too long"))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            status, path, error = await _pick_folder_powershell("powershell.exe", None, 0.01)

        assert status == "cancelled"
        assert path is None
        assert "timed out" in error.lower()
        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_awaited_once()

    asyncio.run(_run())


def test_build_python_script(tmp_path):
    script = _build_python_script(str(tmp_path))
    assert "askdirectory" in script
    assert "overrideredirect(True)" in script
    assert "attributes('-topmost', True)" in script
    assert tmp_path.name in script

    script_none = _build_python_script(None)
    assert "init_dir = None" in script_none


def test_python_subprocess_selection(tmp_path):
    import asyncio

    async def _run():
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(str(tmp_path).encode("utf-8"), b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            status, path, error = await _pick_folder_python_subprocess(None, 10.0)

        assert status == "selected"
        assert path == str(tmp_path.resolve())
        assert error is None

    asyncio.run(_run())


def test_python_subprocess_cancellation():
    import asyncio

    async def _run():
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            status, path, error = await _pick_folder_python_subprocess(None, 10.0)

        assert status == "cancelled"
        assert path is None
        assert error is None

    asyncio.run(_run())


def test_python_subprocess_timeout_cleanup():
    import asyncio

    async def _run():
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError("Process took too long"))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_proc):
            status, path, error = await _pick_folder_python_subprocess(None, 0.01)

        assert status == "cancelled"
        assert path is None
        assert "timed out" in error.lower()
        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_awaited_once()

    asyncio.run(_run())


def test_pick_folder_native_fallback_to_powershell(tmp_path):
    import asyncio

    async def _run():
        with (
            patch(
                "backend.services.folder_picker._pick_folder_python_subprocess",
                new_callable=AsyncMock,
                return_value=("error", None, "Tkinter missing"),
            ),
            patch(
                "backend.services.folder_picker._pick_folder_powershell",
                new_callable=AsyncMock,
                return_value=("selected", str(tmp_path.resolve()), None),
            ) as mock_ps,
            patch("platform.system", return_value="Windows"),
            patch("shutil.which", return_value="C:\\Windows\\System32\\powershell.exe"),
        ):
            status, path, error = await pick_folder_native(None, 10.0)

        assert status == "selected"
        assert path == str(tmp_path.resolve())
        assert error is None
        mock_ps.assert_awaited_once()

    asyncio.run(_run())

