TOP_N_REGION = 10  # Số lượng vùng hiển thị trên biểu đồ, có thể chỉnh thành 20, 30...

#!/usr/bin/env python3
"""
analyze_dw_postgres.py
- Kết nối tới kho dữ liệu PostgreSQL và thực hiện các truy vấn OLAP, vẽ biểu đồ kết quả.
Sử dụng:
    python analyze_dw_postgres.py --config docs/config_template.json
"""
import os, argparse, json
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
import matplotlib.pyplot as plt

###########################################################
# =========================
# 🔹 HÀM HỖ TRỢ
# =========================
###########################################################

# Hàm đọc file cấu hình JSON
def load_config(path):
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding='utf-8'))
    return {}

# Hàm lấy thông tin kết nối DB từ biến môi trường hoặc file config
def env_or_config(config):
    return {
        "host": os.getenv("PG_HOST", config.get("host", "localhost")),
        "port": int(os.getenv("PG_PORT", config.get("port", 5432))),
        "user": os.getenv("PG_USER", config.get("user", "postgres")),
        "password": os.getenv("PG_PASSWORD", config.get("password", "postgres")),
        "database": os.getenv("PG_DB", config.get("database", "retail_dw"))
    }


###########################################################
# =========================
# 🔹 HÀM CHÍNH
# =========================
###########################################################
def main():
    # 1️⃣ Đọc config và tạo kết nối DB
    # Đọc tham số dòng lệnh (đường dẫn file config)
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="docs/config_template.json")
    args = p.parse_args()

    # Đọc file cấu hình và lấy thông tin kết nối
    cfg = load_config(args.config)
    c = env_or_config(cfg)
    print("Connecting to:", {k: v for k, v in c.items() if k != 'password'})

    # Tạo engine kết nối tới PostgreSQL bằng SQLAlchemy
    engine_url = f"postgresql+psycopg2://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{c['database']}"
    engine = create_engine(engine_url)

    # =========================
    # 2️⃣ Truy vấn dữ liệu OLAP
    # =========================

    # Truy vấn doanh thu theo category
    category_sales = pd.read_sql_query('''
        SELECT p.product_name, p.category, SUM(f.amount) AS total_sales
        FROM fact_sales f
        JOIN dim_product p ON f.product_id = p.product_id
        GROUP BY p.product_name, p.category
        ORDER BY total_sales DESC;
    ''', engine)

    # Truy vấn doanh thu theo segment khách hàng
    segment_sales = pd.read_sql_query('''
        SELECT c.segment, SUM(f.amount) AS total_sales
        FROM fact_sales f
        JOIN dim_customer c ON f.customer_id = c.customer_id
        GROUP BY c.segment
        ORDER BY total_sales DESC;
    ''', engine)

    # Truy vấn top khách hàng
    top_customers = pd.read_sql_query('''
        SELECT c.customer_name, SUM(f.amount) AS total_sales, SUM(f.quantity) AS total_quantity
        FROM fact_sales f JOIN dim_customer c ON f.customer_id = c.customer_id
        GROUP BY c.customer_name
        ORDER BY total_sales DESC
        LIMIT 20;
    ''', engine)

    # Truy vấn doanh thu theo năm/quý
    year_quarter_sales = pd.read_sql_query('''
        SELECT d.year, d.quarter, SUM(f.amount) AS total_sales
        FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY d.year, d.quarter
        ORDER BY d.year, d.quarter;
    ''', engine)

    # Truy vấn doanh thu theo tháng
    monthly_sales = pd.read_sql_query('''
        SELECT d.year, d.month, d.month_name, SUM(f.amount) AS total_sales, SUM(f.quantity) AS total_quantity
        FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY d.year, d.month, d.month_name
        ORDER BY d.year, d.month;
    ''', engine)
    print("Monthly sales sample:")
    print(monthly_sales.head())

    # Truy vấn top sản phẩm
    top_products = pd.read_sql_query('''
        SELECT p.product_name, SUM(f.quantity) AS total_quantity, SUM(f.amount) AS total_sales
        FROM fact_sales f JOIN dim_product p ON f.product_id = p.product_id
        GROUP BY p.product_name
        ORDER BY total_quantity DESC
        LIMIT 20;
    ''', engine)

    # Truy vấn doanh thu theo vùng/khu vực
    region_sales = pd.read_sql_query('''
        SELECT r.region_name, SUM(f.amount) AS total_sales, SUM(f.quantity) as total_qty
        FROM fact_sales f JOIN dim_region r ON f.region_id = r.region_id
        GROUP BY r.region_name
        ORDER BY total_sales DESC;
    ''', engine)

    # Truy vấn doanh thu theo sản phẩm, vùng, khách hàng
    prc_sales = pd.read_sql_query('''
        SELECT d.year, d.month, p.product_name, r.region_name, c.customer_name, SUM(f.amount) AS total_sales
        FROM fact_sales f
        JOIN dim_date d ON f.date_key = d.date_key
        JOIN dim_product p ON f.product_id = p.product_id
        JOIN dim_region r ON f.region_id = r.region_id
        JOIN dim_customer c ON f.customer_id = c.customer_id
        GROUP BY d.year, d.month, p.product_name, r.region_name, c.customer_name
        ORDER BY total_sales DESC
        LIMIT 20;
    ''', engine)


    # =========================
    # 3️⃣ Vẽ biểu đồ kết quả
    # =========================

    # Vẽ biểu đồ doanh thu theo category
    if not category_sales.empty:
        plt.figure(figsize=(8,6))
        plt.bar(category_sales['category'], category_sales['total_sales'], color='orange')
        plt.title("Total Sales by Category")
        plt.xlabel("Category")
        plt.ylabel("Total Sales")
        plt.tight_layout()
        plt.show()

    # Vẽ biểu đồ doanh thu theo segment khách hàng
    if not segment_sales.empty:
        plt.figure(figsize=(8,6))
        plt.bar(segment_sales['segment'], segment_sales['total_sales'], color='orange')
        plt.title("Total Sales by Segment")
        plt.xlabel("Segment")
        plt.ylabel("Total Sales")
        plt.tight_layout()
        plt.show()

    # Vẽ biểu đồ top khách hàng
    if not top_customers.empty:
        plt.figure(figsize=(10,6))
        plt.barh(top_customers.head(10)['customer_name'][::-1],
                top_customers.head(10)['total_sales'][::-1],
                color='orange')
        plt.title("Top 10 Customers by Total Sales")
        plt.xlabel("Total Sales")
        plt.tight_layout()
        plt.show()

    # Vẽ biểu đồ doanh thu theo năm/quý
    if not year_quarter_sales.empty:
        year_quarter_sales['year_quarter'] = (
            year_quarter_sales['year'].astype(str) + ' Q' + year_quarter_sales['quarter'].astype(str)
        )
        plt.figure(figsize=(10,5))
        plt.plot(year_quarter_sales['year_quarter'], year_quarter_sales['total_sales'],
                marker='o', color='orange')
        plt.title("Total Sales by Year/Quarter")
        plt.xlabel("Year-Quarter")
        plt.ylabel("Total Sales")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.show()

    # Xử lý và vẽ biểu đồ doanh thu theo tháng (loại outlier)
    if not monthly_sales.empty:
        monthly_sales = monthly_sales.dropna(subset=['total_sales'])
        monthly_sales = monthly_sales[monthly_sales['total_sales'] >= 0]
        monthly_sales = monthly_sales.sort_values(['year', 'month'])
        monthly_sales['year_month'] = monthly_sales['year'].astype(str) + '-' + monthly_sales['month'].astype(str).str.zfill(2)
        median_sales = monthly_sales['total_sales'].median()
        outlier_threshold = median_sales * 3
        outliers = monthly_sales[monthly_sales['total_sales'] > outlier_threshold]
        if not outliers.empty:
            print("⚠️ Cảnh báo: Có các tháng doanh số lớn bất thường, sẽ loại khỏi biểu đồ!")
            print(outliers[['year_month','total_sales']])
            monthly_sales = monthly_sales[monthly_sales['total_sales'] <= outlier_threshold]

        plt.figure(figsize=(10,5))
        plt.plot(monthly_sales['year_month'], monthly_sales['total_sales'], marker='o', color='orange')
        plt.xticks(rotation=45, ha='right')
        plt.title("Monthly Total Sales (No Outliers)")
        plt.xlabel("Year-Month")
        plt.ylabel("Total Sales")
        plt.tight_layout()
        plt.show()

    # Vẽ biểu đồ top sản phẩm theo số lượng bán
    if not top_products.empty:
        top10 = top_products.head(10).iloc[::-1]
        plt.figure(figsize=(10,6))
        plt.barh(top10['product_name'], top10['total_quantity'], color='orange')
        plt.title("Top 10 Products by Quantity Sold")
        plt.xlabel("Total Quantity")
        plt.tight_layout()
        plt.show()

    # Vẽ biểu đồ doanh thu theo vùng/khu vực
    if not region_sales.empty:
        top_regions = region_sales.sort_values('total_sales', ascending=False).head(TOP_N_REGION)
        other_sales = region_sales.sort_values('total_sales', ascending=False).iloc[TOP_N_REGION:]['total_sales'].sum()
        top_regions = pd.concat([
            top_regions,
            pd.DataFrame([{'region_name': 'Other', 'total_sales': other_sales}])
        ], ignore_index=True)

        # Biểu đồ cột doanh thu theo vùng
        plt.figure(figsize=(10,6))
        plt.bar(top_regions['region_name'], top_regions['total_sales'], color='orange')
        plt.title(f"Top {TOP_N_REGION} Regions by Total Sales (Others grouped)")
        plt.xlabel("Region")
        plt.ylabel("Total Sales")
        plt.xticks(rotation=30, ha='right')
        plt.tight_layout()
        plt.show()

        # Biểu đồ tròn doanh thu theo vùng, mỗi phần một màu
        plt.figure(figsize=(8,8))
        colors = plt.cm.tab20.colors[:len(top_regions)]
        plt.pie(top_regions['total_sales'], labels=top_regions['region_name'],
                autopct='%1.1f%%', colors=colors)
        plt.title(f"Top {TOP_N_REGION} Regions by Total Sales (Pie Chart)")
        plt.tight_layout()
        plt.show()

# =========================
# 🔹 Chạy script chính
# =========================
if __name__ == "__main__":
    main()
