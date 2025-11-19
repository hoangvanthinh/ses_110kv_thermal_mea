# Mô tả bản tin điều khiển PTZ camera  

## 1. Điều khiển di chuyển PTZ (Manual)
**Topic:** `camera/[camera_id]/ptz_move`  
**Payload:** `[command]` hoặc `[command]:[speed]`  

### Command list:   
- `up`: Di chuyển lên  
- `down`: Di chuyển xuống  
- `left`: Sang trái  
- `right`: Sang phải  
- `up-left`: Di chuyển chéo trên-trái  
- `up-right`: Di chuyển chéo trên-phải  
- `down-left`: Di chuyển chéo dưới-trái  
- `down-right`: Di chuyển chéo dưới-phải  
- `home`: Về vị trí gốc  
- `stop`: Dừng di chuyển  
- `zoom_in`: Zoom vào  
- `zoom_out`: Zoom ra  

### Ví dụ:
```bash
# Di chuyển lên với tốc độ mặc định (5)
Topic: camera/000100010008/ptz_move
Payload: up

# Di chuyển phải với tốc độ 8
Topic: camera/000100010008/ptz_move
Payload: right:8
```

**Lưu ý:** Khi nhận lệnh `ptz_move`, camera tự động chuyển sang chế độ **MANUAL** trong 5 phút. Trong chế độ này, thermal poller sẽ KHÔNG invoke preset tự động.

---

## 2. Gọi PTZ Preset
**Topic:** `camera/[camera_id]/ptz_preset`  
**Payload:** `[preset_id]` (số nguyên)  

### Ví dụ:
```bash
Topic: camera/000100010008/ptz_preset
Payload: 1
```

---

## 3. Quản lý chế độ Auto/Manual

### 3.1. Chuyển đổi chế độ
**Topic:** `camera/[camera_id]/mode`  

**Payload (Plain text):**
- `auto` - Chuyển về chế độ tự động
- `manual` - Chuyển sang chế độ thủ công

**Payload (JSON):**
```json
{
  "mode": "manual",
  "duration_seconds": 600
}
```

- `mode`: `"auto"` hoặc `"manual"`
- `duration_seconds`: (Optional) Số giây tự động revert về AUTO. 
  - Nếu không có: dùng giá trị mặc định (300s = 5 phút)
  - Nếu = 0: Chế độ MANUAL vĩnh viễn cho đến khi đổi thủ công

### Ví dụ:
```bash
# Chuyển sang Manual mode (5 phút)
Topic: camera/000100010008/mode
Payload: manual

# Chuyển sang Manual mode (10 phút)
Topic: camera/000100010008/mode
Payload: {"mode": "manual", "duration_seconds": 600}

# Chuyển về Auto mode
Topic: camera/000100010008/mode
Payload: auto
```

### 3.2. Query trạng thái mode
**Topic:** `camera/[camera_id]/get_mode`  
**Payload:** (empty hoặc bất kỳ)

**Response Topic:** `camera/[camera_id]/url` (hoặc topic publish chung)  
**Response Payload:**
```json
{
  "camera": "000100010008",
  "type": "mode_status",
  "mode": "manual",
  "expires_at": "2025-11-19T10:30:00",
  "remaining_seconds": 245
}
```

---

## 4. Behavior của các chế độ

| Chế độ | Thermal Poller | PTZ Manual Control | PTZ Preset |
|--------|----------------|-------------------|-----------|
| **AUTO** | ✅ Tự động invoke preset | ✅ Cho phép (→ chuyển MANUAL) | ✅ Cho phép |
| **MANUAL** | ❌ SKIP invoke preset, chỉ đọc nhiệt độ | ✅ Cho phép | ✅ Cho phép |

### Auto-revert:
- Khi nhận lệnh `ptz_move`: Tự động → MANUAL (5 phút)
- Khi hết timeout: MANUAL → AUTO (tự động)
- User có thể force về AUTO bất cứ lúc nào qua topic `/mode`

---

## 5. MQTT Topics Summary

```
camera/[camera_id]/ptz_move       → Điều khiển di chuyển (auto → MANUAL mode)
camera/[camera_id]/ptz_preset     → Gọi preset
camera/[camera_id]/mode           → Set AUTO/MANUAL mode
camera/[camera_id]/get_mode       → Query mode status
camera/[camera_id]/get_url        → Request RTSP URL
```