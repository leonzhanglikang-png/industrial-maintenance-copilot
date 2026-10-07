"""Exercise a running container using only the Python standard library."""

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000"
TOKEN = os.environ["API_ACCESS_TOKEN"]


def request(
    path: str,
    *,
    data: bytes | None = None,
    content_type: str = "application/json",
    method: str | None = None,
):
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": content_type}
    with urlopen(
        Request(BASE + path, data=data, headers=headers, method=method), timeout=10
    ) as response:
        return json.load(response)


def main() -> None:
    if "--verify-restart" not in sys.argv:
        with urlopen(BASE, timeout=10) as response:
            assert "工业运维工作台" in response.read().decode()
        try:
            urlopen(BASE + "/api/v1/documents", timeout=10)
        except HTTPError as error:
            assert error.code == 401
        else:
            raise AssertionError("Production API must require a token")
        boundary = "maintenance-smoke-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="ci-compressor.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            "Inspect the compressor oil filter before startup.\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        uploaded = request(
            "/api/v1/documents/upload",
            data=body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        assert uploaded["indexed_chunk_count"] == 1
        fault = request(
            "/api/v1/faults",
            data=json.dumps(
                {
                    "equipment_id": "ci-persistent-pump",
                    "occurred_at": "2026-10-07",
                    "symptom": "CI synthetic low pressure",
                    "cause": "CI synthetic filter",
                    "corrective_action": "CI synthetic cleaning",
                    "resolved": True,
                }
            ).encode(),
        )
        assert fault["is_demo"] is False
        retired = request(
            "/api/v1/documents/upload",
            data=body.replace(b"ci-compressor.txt", b"ci-expired.txt"),
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        request("/api/v1/documents/" + retired["document_id"], method="DELETE")
    history = request("/api/v1/faults?equipment_id=ci-persistent-pump")
    assert len(history) == 1 and history[0]["symptom"] == "CI synthetic low pressure"
    documents = request("/api/v1/documents")["documents"]
    assert not any(document["source"] == "ci-expired.txt" for document in documents)
    result = request(
        "/api/v1/search",
        data=json.dumps({"query": "compressor oil filter before startup", "limit": 1}).encode(),
    )
    assert result["results"][0]["source"] == "ci-compressor.txt"
    print("Container smoke check passed", "after restart" if "--verify-restart" in sys.argv else "")


if __name__ == "__main__":
    main()
