# Thay đổi tên: node_thermals → preset_thermals & name → preset_name

## ✅ Hoàn thành

### Thay đổi 1: `node_thermals` → `preset_thermals`
Đã đổi tên `node_thermals` thành `preset_thermals` trong toàn bộ dự án.

### Thay đổi 2: `"name"` → `"preset_name"` (trong preset_thermals)
Đã đổi tên field `"name"` thành `"preset_name"` trong mỗi preset thermal.

## Các file đã thay đổi:

### Thay đổi 1 (node_thermals → preset_thermals):
- ✅ `src/worker_manager.py`
- ✅ `src/workers/read_thermal_poller.py`  
- ✅ `src/workers/ptz_controller.py`
- ✅ `src/config.json`
- ✅ `docs/architecture.md`
- ✅ `REFACTORING_COMPARISON.md`

### Thay đổi 2 (name → preset_name):
- ✅ `src/workers/read_thermal_poller.py` - Cập nhật `.get("preset_name")`
- ✅ `src/config.json` - 6 preset nodes
- ✅ `docs/architecture.md` - 2 ví dụ

## Kiểm tra:
- ✅ Không có lỗi linting
- ✅ Tất cả file Python biên dịch thành công
- ✅ JSON config hợp lệ
- ✅ Không còn tham chiếu `node_thermals` trong src/
- ✅ 9 tham chiếu mới đến `preset_name`
- ✅ 13 tham chiếu đến `preset_thermals`

## Lưu ý:
⚠️ **Breaking changes**: 
1. Cần cập nhật config.json với key mới `preset_thermals`
2. Cần đổi field `"name"` thành `"preset_name"` trong mỗi preset thermal

## Ví dụ cấu hình mới:
```json
{
  "camera_name": "0001000100082",
  "preset_thermals": [
    {
      "preset_name": "node1",
      "url_presetID": "http://...",
      "url_areaTemperature": "http://..."
    }
  ]
}
```

Đã hoàn tất!

