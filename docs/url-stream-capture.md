---

---

## Url để web thực hiện live stream và capture image từ camera nhiệt

### Flow thực hiện:
- Gateway thực hiện publish URL ngay khi khởi động hoặc khi URL thay đổi.
- Gateway thực hiện publish URL khi được phía web gửi request get_url.

- Web gửi 1 message request:
 - Topic: camera/get_url
- Gateway reply:
 - Topic: camera/url


### Payload mẫu
 - Request:
    ```json
    {
    "req_id": "12345",
    "type": "get_url",
    "camera_id": "cam01"
    }
    ```
- Response:
    ```json
    {
    "req_id": "12345",
    "camera_id": "cam01",
    "status": "ok",
    "stream_url": "rtsp://192.168.1.10:554/live",
    "snapshot_url": "http://192.168.1.10/capture.jpg",
    "expires_at": "2025-09-29T10:30:00Z"
    }
    ```
- Response lỗi (camera offline):
    ```json
    {
    "req_id": "12345",
    "camera_id": "cam01",
    "status": "error",
    "message": "Camera offline or not reachable"
    }
    ```
