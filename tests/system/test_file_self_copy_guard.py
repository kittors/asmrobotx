"""回归测试：复制/移动目录到其自身或子目录时应返回 400，而不是 500。"""

import os
import tempfile
import shutil

from fastapi.testclient import TestClient


def _get_token(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _auth_headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_token(client)}"}


def test_copy_dir_into_self_returns_400(client: TestClient):
    headers = _auth_headers(client)
    tmp_root = tempfile.mkdtemp(prefix="asm_files_selfcopy_")
    try:
        # 配置 LOCAL 存储
        create_resp = client.post(
            "/api/v1/storage-configs",
            json={"name": "selfcopy", "type": "LOCAL", "local_root_path": tmp_root},
            headers=headers,
        )
        assert create_resp.status_code == 200
        storage_id = create_resp.json()["data"]["id"]

        # 创建目录 /a/b
        r1 = client.post("/api/v1/folders", params={"storageId": storage_id, "path": "/"}, json={"name": "a"}, headers=headers)
        assert r1.status_code == 200
        r2 = client.post(
            "/api/v1/folders", params={"storageId": storage_id, "path": "/a"}, json={"name": "b"}, headers=headers
        )
        assert r2.status_code == 200

        # 直接调用 /files/copy 复制 a -> a/b，应 400
        cp = client.post(
            "/api/v1/files/copy",
            params={"storageId": storage_id},
            json={"sourcePaths": ["/a"], "destinationPath": "/a/b"},
            headers=headers,
        )
        assert cp.status_code == 400
        assert "目录" in (cp.json().get("msg") or "")

        # 通过剪贴板 + 粘贴触发相同逻辑，也应 400
        set_cb = client.post(
            "/api/v1/files/clipboard",
            params={"storageId": storage_id},
            json={"action": "copy", "paths": ["/a"]},
            headers=headers,
        )
        assert set_cb.status_code == 200
        paste = client.post(
            "/api/v1/files/paste",
            params={"storageId": storage_id, "destinationPath": "/a/b", "clearAfter": True},
            headers=headers,
        )
        assert paste.status_code == 400
        assert "目录" in (paste.json().get("msg") or "")

    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

