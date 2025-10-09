"""文件管理模块集成测试（LOCAL 存储）。"""

import io
import os
import shutil
import tempfile

from fastapi.testclient import TestClient


def _get_token(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["data"]["access_token"]


def _auth_headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_token(client)}"}


def test_storage_config_and_local_file_flow(client: TestClient):
    headers = _auth_headers(client)

    # 1) 创建临时目录作为 LOCAL 根目录
    tmp_root = tempfile.mkdtemp(prefix="asm_files_")
    try:
        # 2) 新增存储源（LOCAL）
        create_resp = client.post(
            "/api/v1/storage-configs",
            json={
                "name": "测试本地存储",
                "type": "LOCAL",
                "local_root_path": tmp_root,
            },
            headers=headers,
        )
        assert create_resp.status_code == 200
        cfg = create_resp.json()["data"]
        storage_id = cfg["id"]

        # 3) 列表与连通性
        list_resp = client.get("/api/v1/storage-configs", headers=headers)
        assert list_resp.status_code == 200
        items = list_resp.json()["data"]
        assert any(i["id"] == storage_id for i in items)

        # 4) 文件列表（根目录为空）
        files_resp = client.get("/api/v1/files", params={"storageId": storage_id, "path": "/"}, headers=headers)
        assert files_resp.status_code == 200
        data = files_resp.json()["data"]
        assert data["currentPath"].endswith("/")
        assert isinstance(data["items"], list)

        # 5) 新建文件夹
        mk_resp = client.post(
            "/api/v1/folders",
            params={"storageId": storage_id, "path": "/"},
            json={"name": "docs"},
            headers=headers,
        )
        assert mk_resp.status_code == 200

        # 6) 上传文件到 /docs
        file_content = b"hello world"
        up_resp = client.post(
            "/api/v1/files",
            params={"storageId": storage_id, "path": "/docs"},
            files=[("files", ("a.txt", io.BytesIO(file_content), "text/plain"))],
            headers=headers,
        )
        assert up_resp.status_code == 200
        up_result = up_resp.json()["data"][0]
        assert up_result["status"] == "success"

        # 7) 预览与下载
        prev = client.get("/api/v1/files/preview", params={"storageId": storage_id, "path": "/docs/a.txt"}, headers=headers)
        assert prev.status_code == 200

        down = client.get("/api/v1/files/download", params={"storageId": storage_id, "path": "/docs/a.txt"}, headers=headers)
        assert down.status_code == 200
        assert down.content == file_content

        # 8) 重命名
        rn = client.patch(
            "/api/v1/files",
            params={"storageId": storage_id},
            json={"oldPath": "/docs/a.txt", "newPath": "/docs/a1.txt"},
            headers=headers,
        )
        assert rn.status_code == 200

        # 9) 移动到 /archive
        mv = client.post(
            "/api/v1/files/move",
            params={"storageId": storage_id},
            json={"sourcePaths": ["/docs/a1.txt"], "destinationPath": "/archive"},
            headers=headers,
        )
        assert mv.status_code == 200

        # 10) 复制回 /docs
        cp = client.post(
            "/api/v1/files/copy",
            params={"storageId": storage_id},
            json={"sourcePaths": ["/archive/a1.txt"], "destinationPath": "/docs"},
            headers=headers,
        )
        assert cp.status_code == 200

        # 11) 删除文件与目录
        dl = client.request(
            "DELETE",
            "/api/v1/files",
            params={"storageId": storage_id},
            json={"paths": ["/docs/a1.txt", "/archive"]},
            headers=headers,
        )
        assert dl.status_code == 200

        # 12) 删除存储源配置
        del_cfg = client.delete(f"/api/v1/storage-configs/{storage_id}", headers=headers)
        assert del_cfg.status_code == 200
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

