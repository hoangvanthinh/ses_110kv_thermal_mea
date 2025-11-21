# Thermal Camera Snapshot Test

Chương trình test để chụp ảnh snapshot từ camera nhiệt và lưu vào server IIS.

## Cấu hình

- **Camera URL**: `http://192.168.1.171/cgi-bin/image.cgi?cameraID=1&quality=5`
- **IIS Server**: `192.168.1.163`
- **Target Directory**: `/snapshots/` (trên IIS server)

## Các file test

### 1. `test_snapshot.py` - Test cơ bản
```bash
python test_snapshot.py
```
- Chụp ảnh từ camera
- Lưu vào thư mục local `test_snapshots/`
- Tạo URL dự kiến cho IIS server

### 2. `upload_to_iis.ps1` - Upload bằng PowerShell
```powershell
.\upload_to_iis.ps1 -LocalFile "test_snapshots\thermal_snapshot_20241024T123456.jpg" -IISServer "192.168.1.163"
```
- Copy file qua UNC path
- Phù hợp khi IIS server cho phép truy cập file share

### 3. `upload_to_iis_ftp.py` - Upload bằng FTP
```bash
python upload_to_iis_ftp.py
```
- Upload file qua FTP
- Tự động tìm file mới nhất trong `test_snapshots/`
- Test kết nối FTP trước khi upload

### 4. `test_complete_workflow.py` - Test toàn bộ quy trình
```bash
python test_complete_workflow.py
```
- Chụp ảnh từ camera
- Lưu local
- Upload lên IIS server
- Test HTTP access
- Báo cáo kết quả chi tiết

## Yêu cầu hệ thống

### IIS Server (192.168.1.163)
1. **FTP Service** phải được bật
2. **Directory** `/snapshots/` phải tồn tại và có quyền ghi
3. **Web Server** phải phục vụ file từ `/snapshots/`
4. **Firewall** cho phép kết nối FTP (port 21)

### Local Machine
1. **Python 3.7+**
2. **Modules**: `ftplib`, `urllib` (có sẵn)
3. **Network access** đến camera và IIS server

## Cấu hình IIS Server

### 1. Bật FTP Service
```powershell
# Trên IIS server
Enable-WindowsOptionalFeature -Online -FeatureName IIS-FTPServer
```

### 2. Tạo thư mục snapshots
```powershell
# Tạo thư mục
New-Item -ItemType Directory -Path "C:\inetpub\wwwroot\snapshots" -Force

# Set permissions
icacls "C:\inetpub\wwwroot\snapshots" /grant "IIS_IUSRS:(OI)(CI)F"
```

### 3. Cấu hình FTP Site
1. Mở **IIS Manager**
2. Tạo **FTP Site** mới
3. **Physical Path**: `C:\inetpub\wwwroot\snapshots`
4. **Port**: 21 (default)
5. **Authentication**: Anonymous (hoặc Basic)

### 4. Cấu hình Web Site
1. Tạo **Virtual Directory** `/snapshots/`
2. **Physical Path**: `C:\inetpub\wwwroot\snapshots`
3. **Enable Directory Browsing** (optional)

## Troubleshooting

### Lỗi kết nối camera
```
✗ Cannot connect to camera
```
**Giải pháp**:
- Kiểm tra camera có hoạt động không
- Kiểm tra URL camera có đúng không
- Kiểm tra network connectivity

### Lỗi FTP upload
```
✗ FTP upload failed: [Errno 10061] No connection could be made
```
**Giải pháp**:
- Kiểm tra FTP service có chạy không
- Kiểm tra firewall có block port 21 không
- Kiểm tra IIS server có accessible không

### Lỗi HTTP access
```
✗ HTTP access failed: HTTP Error 404
```
**Giải pháp**:
- Kiểm tra file có được upload thành công không
- Kiểm tra IIS có phục vụ file từ `/snapshots/` không
- Kiểm tra permissions của thư mục

## Kết quả mong đợi

Sau khi chạy thành công, bạn sẽ có:

1. **Local file**: `test_snapshots/thermal_snapshot_YYYYMMDDTHHMMSS.jpg`
2. **HTTP URL**: `http://192.168.1.163/snapshots/thermal_snapshot_YYYYMMDDTHHMMSS.jpg`
3. **Browser access**: Có thể mở URL trong browser để xem ảnh

## Tích hợp vào code chính

Để tích hợp vào `read_thermal_poller.py`, sử dụng code tương tự:

```python
# Trong _process_thermal_nodes function
snapshot_url = "http://192.168.1.171/cgi-bin/image.cgi?cameraID=1&quality=5"
iis_server = "192.168.1.163"

# Capture và upload
snapshot_bytes = fetch_binary(snapshot_url, ...)
# Upload logic here
img_url_on_server = f"http://{iis_server}/snapshots/{filename}"
```




