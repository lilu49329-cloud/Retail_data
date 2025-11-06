## Ứng dụng Web App BI với Streamlit

Hệ thống kho dữ liệu được tích hợp thành một ứng dụng web (Streamlit) giúp người dùng (quản lý, nhà phân tích, giảng viên...) xem báo cáo, biểu đồ, bảng số liệu trực quan mà không cần biết SQL/Python.

### Mục đích
- Biến mô hình phân tích thành công cụ hỗ trợ ra quyết định (BI tool)
- Người dùng chỉ cần mở web app, chọn bộ lọc, xem kết quả trực quan
- Tương tác, lọc theo năm, tháng, sản phẩm, khu vực, khách hàng...

### Cách chạy app
1. Cài đặt Streamlit (nếu chưa có):
   ```bash
   pip install streamlit
   ```
2. Chạy ứng dụng:
   ```bash
   streamlit run scripts/dashboard_streamlit.py
   ```
3. Mở trình duyệt tại địa chỉ http://localhost:8501 để sử dụng dashboard BI

### Các chức năng chính của app
- Bộ lọc năm/tháng ở sidebar
- Biểu đồ doanh thu theo tháng, sản phẩm, khu vực, nhóm sản phẩm, phân khúc, khách hàng, năm/quý
- Bảng số liệu chi tiết, top sản phẩm, top khách hàng
- Giao diện trực quan, dễ sử dụng cho mọi đối tượng

# Retail Data Warehouse (PostgreSQL) - Student Project

## Mục đích dự án
Dự án xây dựng kho dữ liệu bán lẻ dạng star schema trên PostgreSQL, nạp dữ liệu giao dịch mẫu, thực hiện phân tích OLAP và trực quan hóa kết quả bằng các biểu đồ để phục vụ mục tiêu phân tích xu hướng mua sắm, sản phẩm bán chạy, sức mua từng khu vực, phân khúc khách hàng, v.v.

## Các bước thực hiện
1. **Thu thập dữ liệu**: Sử dụng file mẫu `data/train.csv` chứa dữ liệu giao dịch bán lẻ (ngày, sản phẩm, khách hàng, khu vực, doanh số...)
2. **Thiết kế lược đồ hình sao**: Script tự động tạo các bảng fact và dimension (thời gian, sản phẩm, khu vực, khách hàng...)
3. **Triển khai kho dữ liệu**: Tạo database, schema và nạp dữ liệu vào PostgreSQL bằng script `create_dw_postgres.py`
4. **Phân tích OLAP**: Chạy script `analyze_dw_postgres.py` để thực hiện các truy vấn phân tích và vẽ biểu đồ
5. **Trình bày kết quả**: Chụp hình các biểu đồ, đưa vào báo cáo Word/PDF kèm giải thích ý nghĩa kinh doanh

## Cách chạy dự án
1. Tạo môi trường Python và cài đặt thư viện:
   ```bash
   python -m venv venv
   venv\Scripts\activate   # trên Windows
   pip install -r requirements.txt
   ```
2. Cập nhật thông tin kết nối PostgreSQL trong `docs/config_template.json`
3. Khởi tạo kho dữ liệu và nạp dữ liệu:
   ```bash
   python scripts/create_dw_postgres.py --config docs/config_template.json
   ```
4. Phân tích và vẽ biểu đồ:
   ```bash
   python scripts/analyze_dw_postgres.py --config docs/config_template.json
   ```

## Các biểu đồ và cách giải thích
1. **Doanh thu theo tháng**
   - Biểu đồ đường (line chart) thể hiện tổng doanh số bán hàng từng tháng
   - Giúp phân tích xu hướng mua sắm theo thời gian, nhận biết mùa cao điểm/thấp điểm
   - Đưa vào báo cáo: chụp hình biểu đồ, nhận xét xu hướng tăng/giảm, lý do biến động

2. **Top sản phẩm bán chạy**
   - Biểu đồ cột ngang (barh) thể hiện top 10 sản phẩm có số lượng bán lớn nhất
   - Phân tích sản phẩm được ưa chuộng, đề xuất nhập hàng hoặc marketing
   - Có thể điều chỉnh số lượng top sản phẩm hiển thị

3. **Doanh thu theo khu vực**
   - Biểu đồ cột và biểu đồ tròn (pie chart) thể hiện sức mua từng vùng, top N vùng mạnh nhất
   - So sánh sức mua giữa các khu vực, nhận diện vùng tiềm năng
   - Có thể điều chỉnh số lượng vùng hiển thị

4. **Doanh thu theo nhóm sản phẩm (Category)**
   - Biểu đồ cột thể hiện tổng doanh số từng nhóm sản phẩm
   - Giúp nhận biết nhóm sản phẩm chủ lực

5. **Doanh thu theo phân khúc khách hàng (Segment)**
   - Biểu đồ cột thể hiện doanh số theo phân khúc (Consumer, Corporate, Home Office...)
   - Phân tích đối tượng khách hàng tiềm năng

6. **Doanh thu theo khách hàng (Top 10)**
   - Biểu đồ cột ngang cho top khách hàng có doanh số lớn nhất
   - Hỗ trợ nhận diện khách hàng VIP, đề xuất chăm sóc đặc biệt

7. **Doanh thu theo năm/quý**
   - Biểu đồ đường thể hiện tổng doanh số từng năm/quý
   - Phân tích xu hướng dài hạn, so sánh các năm

## Cách đưa biểu đồ vào báo cáo
- Chạy script phân tích, chụp lại hình các biểu đồ
- Đưa hình vào báo cáo Word/PDF, kèm chú thích và nhận xét ý nghĩa kinh doanh
- Nên giải thích rõ xu hướng, lý do biến động, đề xuất cải tiến hoặc chiến lược


## Giải thích mục đích từng file trong dự án
- `data/train.csv`: Dữ liệu giao dịch bán lẻ mẫu, dùng để nạp vào kho dữ liệu và phân tích.
- `requirements.txt`: Danh sách các thư viện Python cần thiết để chạy dự án (pandas, sqlalchemy, matplotlib, psycopg2-binary).
- `docs/config_template.json`: File cấu hình kết nối đến PostgreSQL, điền thông tin host, port, user, password, database.
- `scripts/create_dw_postgres.py`: Script Python tự động tạo database, các bảng theo star schema và nạp dữ liệu từ file CSV vào PostgreSQL.
- `scripts/analyze_dw_postgres.py`: Script Python thực hiện các truy vấn OLAP, phân tích dữ liệu và vẽ các biểu đồ trực quan hóa kết quả.
- `README.md`: Tài liệu hướng dẫn, mô tả mục tiêu, cách chạy, giải thích các bước và các file trong dự án.