from pathlib import Path
import os
import streamlit as st
import streamlit.components.v1 as components
from streamlit_option_menu import option_menu
import json
from sqlalchemy import create_engine
import pandas as pd
import altair as alt

st.set_page_config(page_title="Retail Data Warehouse Dashboard", layout="wide")

# Custom CSS for modern look
st.markdown("""
    <style>
    .main-title {font-size:2.5rem;font-weight:700;color:#2E86C1;margin-bottom:0.5em;}
    .sub-title {font-size:1.2rem;color:#566573;margin-bottom:1em;}
    .sidebar .sidebar-content {background: #F4F6F7;}
    .stButton>button {background-color: #2E86C1; color: white;}
    .stSelectbox>div {background-color: #D6EAF8;}
    .stDataFrame {background-color: #FBFCFC;}
    </style>
""", unsafe_allow_html=True)

# Khởi tạo engine trước khi dùng sidebar
config_path_default = "docs/config_template.json"
config_path = config_path_default
if not Path(config_path).exists():
    st.error(f"Không tìm thấy file cấu hình: {config_path}")
    st.stop()
with open(config_path, encoding='utf-8') as f:
    cfg = json.load(f)

# Cho phép override cấu hình bằng biến môi trường (tiện cho devcontainer/.env)
cfg['host'] = os.environ.get('PGHOST', cfg.get('host'))
cfg['port'] = int(os.environ.get('PGPORT', cfg.get('port')))
cfg['user'] = os.environ.get('PGUSER', cfg.get('user'))
cfg['password'] = os.environ.get('PGPASSWORD', cfg.get('password'))
cfg['database'] = os.environ.get('PGDATABASE', cfg.get('database'))

def _make_engine_from_cfg(c):
    return create_engine(f"postgresql+psycopg2://{c['user']}:{c['password']}@{c['host']}:{c['port']}/{c['database']}")

engine = _make_engine_from_cfg(cfg)

# Thử kết nối sớm để bắt lỗi rõ ràng và (nếu phù hợp) tự động thử fallback sang host.docker.internal
from sqlalchemy.exc import OperationalError
tried_hosts = [cfg['host']]
try:
    conn = engine.connect()
    conn.close()
except OperationalError as e:
    # Nếu host là localhost/127.0.0.1 có thể DB chạy trên máy host; thử host.docker.internal
    alt_host = None
    if str(cfg.get('host')).lower() in ('localhost', '127.0.0.1'):
        alt_host = 'host.docker.internal'
    if alt_host:
        # silent: try alternative host (e.g., host.docker.internal) without printing diagnostics
        # thử với host.docker.internal
        cfg_alt = cfg.copy()
        cfg_alt['host'] = alt_host
        tried_hosts.append(alt_host)
        try:
            engine = _make_engine_from_cfg(cfg_alt)
            conn = engine.connect()
            conn.close()
            # use alt host silently
            cfg = cfg_alt
        except OperationalError:
            # couldn't connect to either host; fall back to CSV/SQLite if available (silent)
            # Thử fallback: nếu có file data/train.csv, sinh SQLite DB từ CSV và dùng làm engine thay thế
            csv_path = Path('data/train.csv')
            if csv_path.exists():
                try:
                    df_raw = pd.read_csv(csv_path)
                    # Chuẩn hoá cột ngày
                    if 'Order Date' in df_raw.columns:
                        df_raw['Order Date'] = pd.to_datetime(df_raw['Order Date'], errors='coerce', dayfirst=False)
                    # Tạo date_key dạng YYYYMMDD integer cho join
                    df_raw['date_key'] = df_raw['Order Date'].dt.strftime('%Y%m%d').astype('Int64')
                    # dim_date
                    dim_date = df_raw[['date_key', 'Order Date']].drop_duplicates().copy()
                    dim_date['year'] = dim_date['Order Date'].dt.year
                    dim_date['month'] = dim_date['Order Date'].dt.month
                    dim_date['month_name'] = dim_date['Order Date'].dt.month_name()
                    dim_date['quarter'] = dim_date['Order Date'].dt.quarter
                    dim_date = dim_date[['date_key', 'year', 'month', 'month_name', 'quarter']]
                    # dim_product
                    prod_cols = {}
                    if 'Product ID' in df_raw.columns:
                        prod_cols['product_id'] = 'Product ID'
                    if 'Category' in df_raw.columns:
                        prod_cols['category'] = 'Category'
                    if 'Product Name' in df_raw.columns:
                        prod_cols['product_name'] = 'Product Name'
                    dim_product = df_raw[list(prod_cols.values())].drop_duplicates().rename(columns={v: k for k,v in prod_cols.items()})
                    # dim_region
                    if 'Region' in df_raw.columns:
                        regions = df_raw[['Region']].drop_duplicates().reset_index(drop=True)
                        regions['region_id'] = regions.index + 1
                        regions = regions.rename(columns={'Region':'region_name'})
                        dim_region = regions[['region_id','region_name']]
                        # map region_id into fact
                        df_raw = df_raw.merge(dim_region, left_on='Region', right_on='region_name', how='left')
                    else:
                        dim_region = pd.DataFrame(columns=['region_id','region_name'])
                    # dim_customer
                    cust_cols = {}
                    if 'Customer ID' in df_raw.columns:
                        cust_cols['customer_id'] = 'Customer ID'
                    if 'Customer Name' in df_raw.columns:
                        cust_cols['customer_name'] = 'Customer Name'
                    if 'Segment' in df_raw.columns:
                        cust_cols['segment'] = 'Segment'
                    dim_customer = df_raw[list(cust_cols.values())].drop_duplicates().rename(columns={v: k for k,v in cust_cols.items()})
                    # fact_sales: amount from Sales column
                    sales_col = None
                    for candidate in ['Sales','Amount','amount','sales']:
                        if candidate in df_raw.columns:
                            sales_col = candidate
                            break
                    fact_sales = pd.DataFrame()
                    fact_sales['date_key'] = df_raw['date_key']
                    # detect quantity column in source CSV (common names); default to 1 when absent
                    quantity_col = None
                    for q_candidate in ['Quantity', 'quantity', 'Qty', 'qty', 'Units', 'Units Sold', 'Order Quantity']:
                        if q_candidate in df_raw.columns:
                            quantity_col = q_candidate
                            break
                    if quantity_col:
                        fact_sales['quantity'] = df_raw[quantity_col]
                    else:
                        fact_sales['quantity'] = 1
                    # product id
                    if 'Product ID' in df_raw.columns:
                        fact_sales['product_id'] = df_raw['Product ID']
                    # customer
                    if 'Customer ID' in df_raw.columns:
                        fact_sales['customer_id'] = df_raw['Customer ID']
                    # region_id
                    if 'region_id' in df_raw.columns:
                        fact_sales['region_id'] = df_raw['region_id']
                    # amount
                    if sales_col:
                        fact_sales['amount'] = df_raw[sales_col]
                    else:
                        fact_sales['amount'] = 0

                    # Ghi các bảng vào SQLite file DB
                    sqlite_path = Path('data/dev_fallback.db')
                    sqlite_url = f"sqlite:///{sqlite_path.resolve()}"
                    sqlite_engine = create_engine(sqlite_url)
                    dim_date.to_sql('dim_date', sqlite_engine, if_exists='replace', index=False)
                    dim_product.to_sql('dim_product', sqlite_engine, if_exists='replace', index=False)
                    dim_region.to_sql('dim_region', sqlite_engine, if_exists='replace', index=False)
                    dim_customer.to_sql('dim_customer', sqlite_engine, if_exists='replace', index=False)
                    fact_sales.to_sql('fact_sales', sqlite_engine, if_exists='replace', index=False)
                    engine = sqlite_engine
                except Exception:
                    # unable to parse CSV fallback; stop silently
                    st.stop()
            else:
                # no CSV fallback available; stop silently
                st.stop()
    else:
        # no alternative host to try; attempt CSV fallback silently
        csv_path = Path('data/train.csv')
        if csv_path.exists():
            try:
                df_raw = pd.read_csv(csv_path)
                if 'Order Date' in df_raw.columns:
                    df_raw['Order Date'] = pd.to_datetime(df_raw['Order Date'], errors='coerce', dayfirst=False)
                df_raw['date_key'] = df_raw['Order Date'].dt.strftime('%Y%m%d').astype('Int64')
                dim_date = df_raw[['date_key', 'Order Date']].drop_duplicates().copy()
                dim_date['year'] = dim_date['Order Date'].dt.year
                dim_date['month'] = dim_date['Order Date'].dt.month
                dim_date['month_name'] = dim_date['Order Date'].dt.month_name()
                dim_date['quarter'] = dim_date['Order Date'].dt.quarter
                dim_date = dim_date[['date_key', 'year', 'month', 'month_name', 'quarter']]
                prod_cols = {}
                if 'Product ID' in df_raw.columns:
                    prod_cols['product_id'] = 'Product ID'
                if 'Category' in df_raw.columns:
                    prod_cols['category'] = 'Category'
                if 'Product Name' in df_raw.columns:
                    prod_cols['product_name'] = 'Product Name'
                dim_product = df_raw[list(prod_cols.values())].drop_duplicates().rename(columns={v: k for k,v in prod_cols.items()})
                if 'Region' in df_raw.columns:
                    regions = df_raw[['Region']].drop_duplicates().reset_index(drop=True)
                    regions['region_id'] = regions.index + 1
                    regions = regions.rename(columns={'Region':'region_name'})
                    dim_region = regions[['region_id','region_name']]
                    df_raw = df_raw.merge(dim_region, left_on='Region', right_on='region_name', how='left')
                else:
                    dim_region = pd.DataFrame(columns=['region_id','region_name'])
                cust_cols = {}
                if 'Customer ID' in df_raw.columns:
                    cust_cols['customer_id'] = 'Customer ID'
                if 'Customer Name' in df_raw.columns:
                    cust_cols['customer_name'] = 'Customer Name'
                if 'Segment' in df_raw.columns:
                    cust_cols['segment'] = 'Segment'
                dim_customer = df_raw[list(cust_cols.values())].drop_duplicates().rename(columns={v: k for k,v in cust_cols.items()})
                sales_col = None
                for candidate in ['Sales','Amount','amount','sales']:
                    if candidate in df_raw.columns:
                        sales_col = candidate
                        break
                fact_sales = pd.DataFrame()
                fact_sales['date_key'] = df_raw['date_key']
                # detect quantity column in source CSV (common names); default to 1 when absent
                quantity_col = None
                for q_candidate in ['Quantity', 'quantity', 'Qty', 'qty', 'Units', 'Units Sold', 'Order Quantity']:
                    if q_candidate in df_raw.columns:
                        quantity_col = q_candidate
                        break
                if quantity_col:
                    fact_sales['quantity'] = df_raw[quantity_col]
                else:
                    fact_sales['quantity'] = 1
                if 'Product ID' in df_raw.columns:
                    fact_sales['product_id'] = df_raw['Product ID']
                if 'Customer ID' in df_raw.columns:
                    fact_sales['customer_id'] = df_raw['Customer ID']
                if 'region_id' in df_raw.columns:
                    fact_sales['region_id'] = df_raw['region_id']
                if sales_col:
                    fact_sales['amount'] = df_raw[sales_col]
                else:
                    fact_sales['amount'] = 0
                sqlite_path = Path('data/dev_fallback.db')
                sqlite_url = f"sqlite:///{sqlite_path.resolve()}"
                sqlite_engine = create_engine(sqlite_url)
                dim_date.to_sql('dim_date', sqlite_engine, if_exists='replace', index=False)
                dim_product.to_sql('dim_product', sqlite_engine, if_exists='replace', index=False)
                dim_region.to_sql('dim_region', sqlite_engine, if_exists='replace', index=False)
                dim_customer.to_sql('dim_customer', sqlite_engine, if_exists='replace', index=False)
                fact_sales.to_sql('fact_sales', sqlite_engine, if_exists='replace', index=False)
                engine = sqlite_engine
            except Exception:
                # CSV fallback failed; stop silently
                st.stop()
        else:
            # no CSV fallback available; stop silently
            st.stop()

# Sidebar navigation with icons, logo, info, and filters
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2920/2920212.png", width=80)
    st.markdown("""
    ### Retail Data Warehouse BI
    - Xem báo cáo, biểu đồ, bảng số liệu
    - Tương tác, lọc dữ liệu, hỗ trợ ra quyết định
    """)
    selected = option_menu(
        "Menu", ["Tổng quan", "Sản phẩm", "Khu vực", "Phân khúc", "Khách hàng"],
        icons=["bar-chart", "box-seam", "geo-alt", "people", "person-badge"],
        menu_icon="cast", default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "#F4F6F7"},
            "icon": {"color": "#2E86C1", "font-size": "1.2rem"},
            "nav-link": {"font-size": "1.1rem", "text-align": "left", "margin":"0px", "color":"#566573"},
            "nav-link-selected": {"background-color": "#D6EAF8"},
        }
    )
    # Bộ lọc nâng cao
    st.header("Bộ lọc dữ liệu")
    with st.form(key="filter_form"):
        y_axis_scale = st.selectbox("Kiểu trục Y (doanh thu)", ["Tự động", "Cố định", "Giá trị nhỏ"], key="yaxis_scale")
        hide_outlier = st.checkbox("Ẩn tháng/quý đột biến doanh thu (outlier)", value=False, key="hide_outlier")
        year_list = pd.read_sql_query('SELECT DISTINCT year FROM dim_date ORDER BY year', engine)['year'].tolist()
        year_list = ["Tất cả"] + year_list
        year = st.selectbox("Năm", year_list, key="year_filter")
        if year == "Tất cả":
            month_list = pd.read_sql_query('SELECT DISTINCT month FROM dim_date ORDER BY month', engine)['month'].tolist()
        else:
            month_list = pd.read_sql_query(f'SELECT DISTINCT month FROM dim_date WHERE year={year} ORDER BY month', engine)['month'].tolist()
        month_list = ["Tất cả"] + month_list
        month = st.selectbox("Tháng", month_list, key="month_filter")
        # Thêm bộ lọc nâng cao
        category_list = pd.read_sql_query('SELECT DISTINCT category FROM dim_product ORDER BY category', engine)['category'].tolist()
        category = st.selectbox("Nhóm sản phẩm", ["Tất cả"] + category_list, key="category_filter")
        region_list = pd.read_sql_query('SELECT DISTINCT region_name FROM dim_region ORDER BY region_name', engine)['region_name'].tolist()
        region = st.selectbox("Khu vực", ["Tất cả"] + region_list, key="region_filter")
        segment_list = pd.read_sql_query('SELECT DISTINCT segment FROM dim_customer ORDER BY segment', engine)['segment'].tolist()
        segment = st.selectbox("Phân khúc KH", ["Tất cả"] + segment_list, key="segment_filter")
        filter_submit = st.form_submit_button("Áp dụng")

# Tiêu đề tiếng Việt nổi bật
st.markdown('<div class="main-title">Báo cáo Kho Dữ Liệu Bán Lẻ</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Công cụ trực quan hóa, phân tích dữ liệu bán lẻ hỗ trợ ra quyết định</div>', unsafe_allow_html=True)

# Hiển thị nội dung theo menu đã chọn
if selected == "Tổng quan":
    if filter_submit:
        # Sửa lại truy vấn khi lọc: nếu chọn "Tất cả" thì không thêm điều kiện WHERE cho năm/tháng
        where_clause = []
        if year != "Tất cả":
            where_clause.append(f"d.year = {year}")
        if month != "Tất cả":
            where_clause.append(f"d.month = {month}")
        where_sql = ""
        if where_clause:
            where_sql = "WHERE " + " AND ".join(where_clause)
        with st.expander("📈 Doanh thu theo tháng", expanded=True):
            # Lấy danh sách tháng phù hợp với bộ lọc năm
            if year == "Tất cả":
                all_months = pd.read_sql_query('SELECT DISTINCT year, month, month_name FROM dim_date ORDER BY year, month', engine)
            else:
                all_months = pd.read_sql_query(f'SELECT DISTINCT year, month, month_name FROM dim_date WHERE year={year} ORDER BY year, month', engine)
            monthly_sales = pd.read_sql_query(f'''
            SELECT d.year, d.month, d.month_name, SUM(f.amount) AS total_sales
            FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
            {where_sql}
            GROUP BY d.year, d.month, d.month_name
            ORDER BY d.year, d.month;
            ''', engine)
            # Merge để đảm bảo đủ các tháng
            merged = pd.merge(all_months, monthly_sales, on=['year', 'month', 'month_name'], how='left')
            merged['total_sales'] = merged['total_sales'].fillna(0)
            merged['year_month'] = merged['year'].astype(str) + '-' + merged['month'].astype(str).str.zfill(2)
            if len(merged) == 1:
                st.metric(label=f"Doanh thu tháng {merged['month_name'][0]} {merged['year'][0]}", value=f"{merged['total_sales'][0]:,.0f}")
            else:
                plot_data = merged.copy()
                if hide_outlier:
                    # Xác định outlier bằng IQR (hoặc 1.5*IQR)
                    q1 = plot_data['total_sales'].quantile(0.25)
                    q3 = plot_data['total_sales'].quantile(0.75)
                    iqr = q3 - q1
                    upper = q3 + 1.5 * iqr
                    plot_data = plot_data[plot_data['total_sales'] <= upper]
                if y_axis_scale == "Cố định":
                    y_scale = alt.Scale(domain=[0, 200000])
                elif y_axis_scale == "Giá trị nhỏ":
                    y_scale = alt.Scale(type="log", domain=[max(1, plot_data['total_sales'].min()), plot_data['total_sales'].max() * 1.1])
                else:
                    y_scale = alt.Scale(domain=[0, plot_data['total_sales'].max() * 1.1])
                chart = alt.Chart(plot_data).mark_line(point=True).encode(
                    x=alt.X('year_month', title='Thời gian', sort=list(plot_data['year_month'])),
                    y=alt.Y('total_sales', title='Doanh thu', scale=y_scale)
                ).properties(width=700, height=350)
                st.altair_chart(chart, use_container_width=True)
            st.write("**Kiểm tra dữ liệu doanh thu theo tháng:**")
            st.dataframe(merged, use_container_width=True)
        with st.expander("📊 Doanh thu theo năm/quý", expanded=False):
            if year == "Tất cả":
                year_quarter_query = '''
                SELECT d.year, d.quarter, SUM(f.amount) AS total_sales
                FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
                GROUP BY d.year, d.quarter
                ORDER BY d.year, d.quarter;
                '''
            else:
                year_quarter_query = f'''
                SELECT d.year, d.quarter, SUM(f.amount) AS total_sales
                FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
                WHERE d.year = {year}
                GROUP BY d.year, d.quarter
                ORDER BY d.year, d.quarter;
                '''
            year_quarter_sales = pd.read_sql_query(year_quarter_query, engine)
            year_quarter_sales['year_quarter'] = year_quarter_sales['year'].astype(str) + ' Q' + year_quarter_sales['quarter'].astype(str)
            plot_data = year_quarter_sales.copy()
            if hide_outlier:
                q1 = plot_data['total_sales'].quantile(0.25)
                q3 = plot_data['total_sales'].quantile(0.75)
                iqr = q3 - q1
                upper = q3 + 1.5 * iqr
                plot_data = plot_data[plot_data['total_sales'] <= upper]
            if y_axis_scale == "Cố định":
                y_scale = alt.Scale(domain=[0, 200000])
            elif y_axis_scale == "Giá trị nhỏ (log)":
                y_scale = alt.Scale(type="log", domain=[max(1, plot_data['total_sales'].min()), plot_data['total_sales'].max() * 1.1])
            else:
                y_scale = alt.Scale(domain=[0, plot_data['total_sales'].max() * 1.1])
            chart = alt.Chart(plot_data).mark_line(point=True).encode(
                x=alt.X('year_quarter', title='Năm/Quý'),
                y=alt.Y('total_sales', title='Doanh thu', scale=y_scale)
            ).properties(width=700, height=350)
            st.altair_chart(chart, use_container_width=True)
            st.dataframe(year_quarter_sales, use_container_width=True)
    else:
        # Hiển thị toàn bộ dữ liệu khi chưa lọc
        with st.expander("📈 Doanh thu theo tháng", expanded=True):
            all_months = pd.read_sql_query('SELECT DISTINCT year, month, month_name FROM dim_date ORDER BY year, month', engine)
            monthly_sales = pd.read_sql_query('''
            SELECT d.year, d.month, d.month_name, SUM(f.amount) AS total_sales
            FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
            GROUP BY d.year, d.month, d.month_name
            ORDER BY d.year, d.month;
            ''', engine)
            merged = pd.merge(all_months, monthly_sales, on=['year', 'month', 'month_name'], how='left')
            merged['total_sales'] = merged['total_sales'].fillna(0)
            merged['year_month'] = merged['year'].astype(str) + '-' + merged['month'].astype(str).str.zfill(2)
            if y_axis_scale == "Cố định":
                y_scale = alt.Scale(domain=[0, 200000])
            elif y_axis_scale == "Giá trị nhỏ (log)":
                y_scale = alt.Scale(type="log", domain=[max(1, merged['total_sales'].min()), merged['total_sales'].max() * 1.1])
            else:
                y_scale = alt.Scale(domain=[0, merged['total_sales'].max() * 1.1])
            chart = alt.Chart(merged).mark_line(point=True).encode(
                x=alt.X('year_month', title='Thời gian', sort=list(merged['year_month'])),
                y=alt.Y('total_sales', title='Doanh thu', scale=y_scale)
            ).properties(width=700, height=350)
            st.altair_chart(chart, use_container_width=True)
            st.write("**Kiểm tra dữ liệu doanh thu theo tháng:**")
            st.dataframe(merged, use_container_width=True)
        with st.expander("📊 Doanh thu theo năm/quý", expanded=False):
            year_quarter_sales = pd.read_sql_query('''
            SELECT d.year, d.quarter, SUM(f.amount) AS total_sales
            FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
            GROUP BY d.year, d.quarter
            ORDER BY d.year, d.quarter;
            ''', engine)
            year_quarter_sales['year_quarter'] = year_quarter_sales['year'].astype(str) + ' Q' + year_quarter_sales['quarter'].astype(str)
            if y_axis_scale == "Cố định":
                y_scale = alt.Scale(domain=[0, 200000])
            elif y_axis_scale == "Giá trị nhỏ (log)":
                y_scale = alt.Scale(type="log", domain=[max(1, year_quarter_sales['total_sales'].min()), year_quarter_sales['total_sales'].max() * 1.1])
            else:
                y_scale = alt.Scale(domain=[0, year_quarter_sales['total_sales'].max() * 1.1])
            chart = alt.Chart(year_quarter_sales).mark_line(point=True).encode(
                x=alt.X('year_quarter', title='Năm/Quý'),
                y=alt.Y('total_sales', title='Doanh thu', scale=y_scale)
            ).properties(width=700, height=350)
            st.altair_chart(chart, use_container_width=True)
            st.dataframe(year_quarter_sales, use_container_width=True)
if selected == "Sản phẩm":
    if filter_submit:
        filter_clauses = []
        if year != "Tất cả":
            filter_clauses.append(f"d.year = {year}")
        if month != "Tất cả":
            filter_clauses.append(f"d.month = {month}")
        if category != "Tất cả":
            filter_clauses.append(f"p.category = '{category}'")
        filter_sql = ""
        if filter_clauses:
            filter_sql = "WHERE " + " AND ".join(filter_clauses)
        query = f'''
        SELECT p.product_name, SUM(f.quantity) AS total_quantity, SUM(f.amount) AS total_sales
        FROM fact_sales f JOIN dim_product p ON f.product_id = p.product_id
        JOIN dim_date d ON f.date_key = d.date_key
        {filter_sql}
        GROUP BY p.product_name
        ORDER BY total_sales DESC
        LIMIT 10;
        '''
    else:
        query = '''
        SELECT p.product_name, SUM(f.quantity) AS total_quantity, SUM(f.amount) AS total_sales
        FROM fact_sales f JOIN dim_product p ON f.product_id = p.product_id
        JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY p.product_name
        ORDER BY total_sales DESC
        LIMIT 10;
        '''
    with st.expander("🏆 Top sản phẩm bán chạy", expanded=True):
        top_products = pd.read_sql_query(query, engine)
        if top_products.empty:
            st.info("Không có dữ liệu để hiển thị.")
        else:
            try:
                df = top_products.copy()
                df['product_name'] = df['product_name'].astype(str)
                max_show = min(len(df), 20)
                chart = alt.Chart(df.head(max_show)).mark_bar().encode(
                    x=alt.X('product_name', sort='-y', title='Sản phẩm'),
                    y=alt.Y('total_sales', title='Doanh thu', scale=alt.Scale(domain=[0, max(20000, df['total_sales'].max()*1.1)]))
                ).properties(width=40*max_show+100, height=350)
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.warning(f"Không thể hiển thị biểu đồ: {e}")
            st.dataframe(top_products, use_container_width=True)
if selected == "Khu vực":
    if filter_submit:
        filter_clauses = []
        if year != "Tất cả":
            filter_clauses.append(f"d.year = {year}")
        if month != "Tất cả":
            filter_clauses.append(f"d.month = {month}")
        if region != "Tất cả":
            filter_clauses.append(f"r.region_name = '{region}'")
        filter_sql = ""
        if filter_clauses:
            filter_sql = "WHERE " + " AND ".join(filter_clauses)
        query = f'''
        SELECT r.region_name, SUM(f.amount) AS total_sales
        FROM fact_sales f JOIN dim_region r ON f.region_id = r.region_id
        JOIN dim_date d ON f.date_key = d.date_key
        {filter_sql}
        GROUP BY r.region_name
        ORDER BY total_sales DESC;
        '''
    else:
        query = '''
        SELECT r.region_name, SUM(f.amount) AS total_sales
        FROM fact_sales f JOIN dim_region r ON f.region_id = r.region_id
        JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY r.region_name
        ORDER BY total_sales DESC;
        '''
    with st.expander("🌍 Doanh thu theo khu vực", expanded=True):
        region_sales = pd.read_sql_query(query, engine)
        if region_sales.empty:
            st.info("Không có dữ liệu để hiển thị.")
        else:
            try:
                # Gom nhóm Other nếu số vùng > TOP_N_REGION
                TOP_N_REGION = 10
                region_sales_sorted = region_sales.sort_values('total_sales', ascending=False)
                region_sales_sorted['region_name'] = region_sales_sorted['region_name'].fillna('Không xác định').astype(str)
                # Tạo tập top_regions: top N cộng 'Other' nếu có
                if len(region_sales_sorted) > TOP_N_REGION:
                    top_regions = region_sales_sorted.head(TOP_N_REGION).copy()
                    other_sales = region_sales_sorted.iloc[TOP_N_REGION:]['total_sales'].sum()
                    # đảm bảo cột total_sales có tên đúng và cùng kiểu
                    other_row = pd.DataFrame([{'region_name': 'Other', 'total_sales': other_sales}])
                    top_regions = pd.concat([top_regions, other_row], ignore_index=True)
                else:
                    top_regions = region_sales_sorted.copy()
                # Hiển thị số lượng thực tế trong tiêu đề (ví dụ Top 4 nếu chỉ có 4 vùng)
                displayed_n = min(TOP_N_REGION, len(region_sales_sorted))
                # Biểu đồ cột dựa trên top_regions (không hiển thị toàn bộ dataset khi muốn Top N)
                plot_df = top_regions.copy()
                max_show = min(len(plot_df), 20)
                y_max = max(20000, plot_df['total_sales'].max()*1.1) if not plot_df.empty else 20000
                chart = alt.Chart(plot_df.head(max_show)).mark_bar().encode(
                    x=alt.X('region_name', sort='-y', title='Khu vực', type='nominal'),
                    y=alt.Y('total_sales', title='Doanh thu', scale=alt.Scale(domain=[0, y_max]))
                ).properties(width=40*max_show+100, height=350)
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.warning(f"Không thể hiển thị biểu đồ: {e}")
            # Biểu đồ tròn (pie chart)
            import plotly.express as px
            if not top_regions.empty and top_regions['total_sales'].sum() > 0:
                st.markdown(f"**Top {displayed_n} khu vực theo doanh thu (các vùng còn lại gộp 'Other')**")
                pie_fig = px.pie(top_regions, names='region_name', values='total_sales',
                                color_discrete_sequence=px.colors.sequential.Oranges)
                st.plotly_chart(pie_fig, use_container_width=True)
            else:
                st.info("Không có dữ liệu để hiển thị biểu đồ tròn khu vực.")
            st.dataframe(region_sales, use_container_width=True)
if selected == "Phân khúc":
    if filter_submit:
        filter_clauses = []
        if year != "Tất cả":
            filter_clauses.append(f"d.year = {year}")
        if month != "Tất cả":
            filter_clauses.append(f"d.month = {month}")
        if segment != "Tất cả":
            filter_clauses.append(f"c.segment = '{segment}'")
        filter_sql = ""
        if filter_clauses:
            filter_sql = "WHERE " + " AND ".join(filter_clauses)
        query = f'''
        SELECT c.segment, SUM(f.amount) AS total_sales
        FROM fact_sales f JOIN dim_customer c ON f.customer_id = c.customer_id
        JOIN dim_date d ON f.date_key = d.date_key
        {filter_sql}
        GROUP BY c.segment
        ORDER BY total_sales DESC;
        '''
    else:
        query = '''
        SELECT c.segment, SUM(f.amount) AS total_sales
        FROM fact_sales f JOIN dim_customer c ON f.customer_id = c.customer_id
        JOIN dim_date d ON f.date_key = d.date_key
        GROUP BY c.segment
        ORDER BY total_sales DESC;
        '''
    with st.expander("📊 Doanh thu theo phân khúc khách hàng", expanded=True):
        segment_sales = pd.read_sql_query(query, engine)
        if segment_sales.empty:
            st.info("Không có dữ liệu để hiển thị.")
        else:
            try:
                df = segment_sales.copy()
                df['segment'] = df['segment'].fillna('Không xác định').astype(str)
                max_show = min(len(df), 20)
                chart = alt.Chart(df.head(max_show)).mark_bar().encode(
                    x=alt.X('segment', sort='-y', title='Phân khúc', type='nominal'),
                    y=alt.Y('total_sales', title='Doanh thu', scale=alt.Scale(domain=[0, max(20000, df['total_sales'].max()*1.1)]))
                ).properties(width=40*max_show+100, height=350)
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.warning(f"Không thể hiển thị biểu đồ: {e}")
            st.dataframe(segment_sales, use_container_width=True)
if selected == "Khách hàng":
    filter_clauses = []
    if filter_submit:
        if year != "Tất cả":
            filter_clauses.append(f"d.year = {year}")
        if month != "Tất cả":
            filter_clauses.append(f"d.month = {month}")
    filter_sql = ""
    if filter_clauses:
        filter_sql = "WHERE " + " AND ".join(filter_clauses)
    with st.expander("💎 Top 10 khách hàng có doanh số lớn nhất", expanded=True):
        top_customers = pd.read_sql_query(f'''
        SELECT c.customer_name, SUM(f.amount) AS total_sales
        FROM fact_sales f JOIN dim_customer c ON f.customer_id = c.customer_id
        JOIN dim_date d ON f.date_key = d.date_key
        {filter_sql}
        GROUP BY c.customer_name
        ORDER BY total_sales DESC
        LIMIT 10;
        ''', engine)
        chart = alt.Chart(top_customers).mark_bar().encode(
            x=alt.X('customer_name', sort='-y', title='Khách hàng'),
            y=alt.Y('total_sales', title='Doanh thu', scale=alt.Scale(domain=[0, 20000]))
        ).properties(width=700, height=350)
        st.altair_chart(chart, use_container_width=True)
        st.dataframe(top_customers, use_container_width=True)