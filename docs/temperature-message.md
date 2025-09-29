---
title: "Bản tin nhiệt độ (JSON)"
description: "Mô tả cấu trúc bản tin nhiệt độ, thời gian gửi và SID của node đo."
version: "1.0"
---

## Mục đích

Tài liệu này mô tả định dạng bản tin nhiệt độ được truyền dưới dạng JSON từ các node đo về hệ thống, bao gồm thời gian đo/gửi và SID của node.

## Cấu trúc JSON (ví dụ)

```json
{
  "type": "temperature",
  "version": "1.0",
  "sid": "NODE-110KV-A1",
  "measured_at": "2025-09-29T08:15:30.123Z",
  "sent_at": "2025-09-29T08:15:31.456Z",
  "temperature": {
    "value": 68.4,
    "unit": "C"
  },
  "seq": 1024
}
```

## Định nghĩa trường

- **type** (string, bắt buộc): Loại bản tin. Cố định: `temperature`.
- **version** (string, bắt buộc): Phiên bản schema, ví dụ `1.0`.
- **sid** (string, bắt buộc): SID/định danh duy nhất của node đo.
- **measured_at** (string, ISO 8601, khuyến nghị): Thời điểm thiết bị ghi nhận nhiệt độ.
- **sent_at** (string, ISO 8601, bắt buộc): Thời điểm bản tin được gửi đi từ node.
- **temperature** (object, bắt buộc):
  - **value** (number, bắt buộc): Giá trị nhiệt độ.
  - **unit** (string, bắt buộc): Đơn vị đo. Hỗ trợ: `C` (Celsius), `F` (Fahrenheit), `K` (Kelvin).
- **seq** (integer, khuyến nghị): Số thứ tự bản tin tăng dần để phát hiện thất lạc/đảo gói.

## Quy ước và ràng buộc

- **Thời gian**: Chuẩn ISO 8601 theo UTC (ví dụ: `2025-09-29T08:15:31.456Z`).
- **Đơn vị**: Mặc định `C`. Nếu sử dụng `F` hoặc `K`, hệ thống sẽ quy đổi nội bộ khi cần.
- **SID**: Chuỗi 3–64 ký tự, không khoảng trắng; ổn định theo node (ví dụ `NODE-110KV-A1`).
- **Giới hạn giá trị** (khuyến nghị): `temperature.value` trong khoảng −80 đến 300 (điều chỉnh theo cảm biến).
- **Toàn vẹn thời gian**: `sent_at` ≥ `measured_at` (nếu có `measured_at`).
- **Phiên bản**: Tăng `version` khi thay đổi schema để đảm bảo tương thích ngược.

## JSON Schema (Draft 2020-12)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/temperature-message.json",
  "title": "TemperatureMessage",
  "type": "object",
  "required": ["type", "version", "sid", "sent_at", "temperature"],
  "additionalProperties": false,
  "properties": {
    "type": { "const": "temperature" },
    "version": { "type": "string", "minLength": 1, "maxLength": 10 },
    "sid": { "type": "string", "minLength": 3, "maxLength": 64, "pattern": "^[^\\s]+$" },
    "measured_at": { "type": "string", "format": "date-time" },
    "sent_at": { "type": "string", "format": "date-time" },
    "temperature": {
      "type": "object",
      "required": ["value", "unit"],
      "additionalProperties": false,
      "properties": {
        "value": { "type": "number", "minimum": -200, "maximum": 1000 },
        "unit": { "type": "string", "enum": ["C", "F", "K"] }
      }
    },
    "seq": { "type": "integer", "minimum": 0 }
  }
}
```

## Ghi chú triển khai

- Gửi cả `measured_at` và `sent_at` để phân tích độ trễ đầu-cuối.
- Dùng `seq` để phát hiện thiếu gói; reset về 0 khi thiết bị khởi động lại.
- Nếu băng thông hạn chế, có thể cố định `version` ở tầng truyền thông, nhưng khuyến nghị vẫn giữ trong payload.


