# Kết nối PostgreSQL bằng `psql` (helper scripts)

Tôi đã thêm một vài tiện ích nhỏ để giúp kết nối đến PostgreSQL từ môi trường devcontainer.

Files added

- `scripts/psql_connect.sh` — helper script để kết nối; hỗ trợ URI hoặc biến môi trường hoặc tham số vị trí.
- `scripts/create_pgpass.sh` — tiện ích để tạo `~/.pgpass` với một dòng credentials (và chmod 600).
- `docs/psql_env_example.env` — ví dụ `.env` (cách sử dụng biến môi trường).

Cách dùng nhanh

1) Kết nối bằng URI:

```bash
./scripts/psql_connect.sh -u postgresql://alice:secret@db.example.com:5432/retail_db
```

2) Kết nối dùng biến môi trường (không dùng lịch sử shell để lộ mật khẩu):

```bash
PGHOST=db.example.com PGPORT=5432 PGUSER=alice PGPASSWORD=secret PGDATABASE=retail_db ./scripts/psql_connect.sh
```

3) Kết nối bằng tham số vị trí (host [port [user [db]]]):

```bash
./scripts/psql_connect.sh db.example.com 5432 alice retail_db
```

4) Tạo `~/.pgpass` để psql tự động đăng nhập (an toàn hơn lưu mật khẩu trên lệnh):

```bash
./scripts/create_pgpass.sh db.example.com 5432 retail_db alice s3cr3t
```

Ghi chú an toàn

- Nếu dùng `~/.pgpass`, file phải có quyền `600` (đã được script đặt). Tuyệt đối không commit mật khẩu vào git.
- Bạn có thể tạo file `.env` tại repo root (không commit) với các biến `PGHOST=...` v.v. `scripts/psql_connect.sh` sẽ cố gắng load `.env` nếu có.

Nếu muốn, tôi có thể:
- Tích hợp auto-chmod `scripts/*.sh` để có executable permission (y/n).
- Thêm một bước kiểm tra kết nối (nc hoặc `psql -c '\conninfo'`).
