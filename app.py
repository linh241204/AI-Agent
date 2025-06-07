import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, date, time
import uuid
import requests
from openai import OpenAI, OpenAIError
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
import io
import seaborn as sns
import re
import cloudinary
import cloudinary.uploader
import json
import os
import gspread
from google.oauth2.service_account import Credentials

# ====== CONSTANTS & CONFIGURATION ======
# File lưu trữ dữ liệu bài viết chờ duyệt
DATA_FILE = "posts_data.json"

# ID của Google Sheet dùng để lên lịch đăng bài
SPREADSHEET_ID = "1HUWXhKwglpJtp6yRuUfo2oy76uNKxDRx5n0RUG2q0hM"

# Tên sheet trong Google Sheet để lưu lịch đăng bài
SHEET_NAME = "xuongbinhgom"

# Các cột dữ liệu trong Google Sheet:
# - product: tên sản phẩm
# - keywords: từ khóa liên quan
# - platform: nền tảng đăng (Facebook/Instagram)
# - time_str: thời gian đăng (HH:MM)
# - token: token xác thực API
# - page_id: ID trang/trang cá nhân
# - mode: chế độ đăng (once/daily)
# - date_str: ngày đăng (YYYY-MM-DD)
# - caption: nội dung bài đăng
# - image_path: đường dẫn ảnh đính kèm
HEADER = [
    "product", "keywords", "platform", "time_str", "token",
    "page_id", "mode", "date_str", "caption", "image_path"
]

# Đọc các token và secret từ Streamlit secrets:
# - FB_PAGE_TOKEN: token xác thực Facebook Page API
# - FB_PAGE_ID: ID của Facebook Page
# - OPENROUTER_API_KEY: key để gọi AI qua OpenRouter
# - IG_TOKEN: token xác thực Instagram API (có thể không có)
# - IG_ID: ID tài khoản Instagram (có thể không có)
FB_PAGE_TOKEN = st.secrets["FB_PAGE_TOKEN"]
FB_PAGE_ID = st.secrets["FB_PAGE_ID"]
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
IG_TOKEN = st.secrets.get("IG_TOKEN", "")
IG_ID = st.secrets.get("IG_ID", "")

# Cấu hình Cloudinary
cloudinary.config(
    cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
    api_key=st.secrets["CLOUDINARY_API_KEY"],
    api_secret=st.secrets["CLOUDINARY_API_SECRET"],
    secure=True)

# Tạo OpenAI client
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ====== UTILITY FUNCTIONS ======

# ====== Hàm đọc danh sách bài viết ======
# Chức năng: Đọc danh sách bài viết từ file JSON một cách an toàn.
# - Kiểm tra file có tồn tại không. 
# - Trả về danh sách rỗng nếu có lỗi
def load_posts(filename=DATA_FILE):
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        return []
    except (json.JSONDecodeError, IOError, Exception) as e:
        print(f"Lỗi đọc file {filename}: {e}")
        return []

# ====== Hàm lưu danh sách bài viết ======
# Chức năng: Lưu danh sách bài viết vào file JSON.
# - Ghi đè toàn bộ danh sách vào file.
# - Dùng khi thêm/xóa/sửa bài chờ duyệt.
def save_posts(posts, filename=DATA_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

# ====== Hàm lấy dữ liệu bài viết an toàn ======
# Chức năng: Lấy dữ liệu bài viết từ trạng thái phiên một cách an toàn.
# - Kiểm tra tồn tại và kiểm tra danh sách có hợp lệ không.
# - Trả về danh sách rỗng nếu không hợp lệ.
def get_safe_posts_data():
    posts_data = st.session_state.get("posts", [])
    return posts_data if isinstance(posts_data, list) else []

# ====== Hàm chuẩn bị dữ liệu dạng bảng từ bài viết ======
# Chức năng: Chuẩn bị dữ liệu dạng bảng từ dữ liệu bài viết với các cột bắt buộc.
# - Đảm bảo các cột số tồn tại và có giá trị hợp lệ.
# - Tạo cột mặc định nếu thiếu.
# - Trả về dữ liệu dạng bảng đã được chuẩn bị.
def prepare_dataframe(posts_data, required_cols=None):
    if required_cols is None:
        required_cols = ["likes", "comments", "shares", "reach", "reactions"]
    
    df = pd.DataFrame(posts_data)
    
    # Đảm bảo các cột số tồn tại và có giá trị hợp lệ
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    
    # Đảm bảo cột time tồn tại
    if "time" not in df.columns:
        df["time"] = "unknown"
        
    return df

# ====== FACEBOOK API FUNCTIONS ======

# ====== Hàm lấy bài viết từ Facebook ======
# Chức năng: Lấy danh sách bài viết từ Facebook API.
# - Gọi Graph API để lấy bài viết của page.
# - Trả về danh sách bài viết hoặc danh sách rỗng.
def fetch_facebook_posts(page_id, access_token, limit=20):
    url = f"https://graph.facebook.com/v19.0/{page_id}/posts"
    params = {
        "fields": "id,message,created_time",
        "limit": limit,
        "access_token": access_token
    }
    resp = requests.get(url, params=params)
    data = resp.json()
    return data.get("data", [])

# ====== Hàm lấy thống kê bài viết Facebook ======
# Chức năng: Lấy thống kê chi tiết của một bài viết từ Facebook API.
# - Gọi Graph API lấy likes, comments, shares, reactions.
# - Trả về kiểu dữ liệu từ điển chứa tất cả thông tin.
def fetch_post_stats(post_id, access_token):
    url = f"https://graph.facebook.com/v19.0/{post_id}"
    params = {
        "fields": "message,likes.summary(true),comments.summary(true),shares,reactions.summary(true)",
        "access_token": access_token
    }
    resp = requests.get(url, params=params)
    return resp.json()

# ====== Hàm lấy dữ liệu Facebook và lưu dữ liệu và bộ nhớ tạm ======
# Chức năng: Lấy dữ liệu Facebook và lưu vào trạng thái phiên.
# - Lưu dữ liệu vào bộ nhớ tạm để tránh gọi API nhiều lần.
# - Lấy 50 bài viết mới nhất.
# - Trả về danh sách bài viết đã được xử lý.
def get_facebook_data(force_refresh=False):
    if force_refresh or "fb_posts" not in st.session_state:
        with st.spinner("Đang lấy dữ liệu Facebook..."):
            fb_posts = fetch_facebook_posts(FB_PAGE_ID, FB_PAGE_TOKEN, limit=50)
            new_posts = []
            
            for post in fb_posts:
                stats = fetch_post_stats(post["id"], FB_PAGE_TOKEN)
                comments_count = 0
                if "comments" in stats and isinstance(stats["comments"], dict):
                    comments_count = stats["comments"].get("summary", {}).get("total_count", 0)
                
                new_posts.append({
                    "id": post["id"],
                    "caption": stats.get("message", ""),
                    "likes": stats.get("likes", {}).get("summary", {}).get("total_count", 0),
                    "comments": comments_count,
                    "shares": stats.get("shares", {}).get("count", 0),
                    "reactions": stats.get("reactions", {}).get("summary", {}).get("total_count", 0),
                    "platform": "Facebook",
                    "created_time": post.get("created_time", None)
                })
            
            st.session_state.fb_posts = new_posts
            st.session_state.fb_data_fetched = True
    
    return st.session_state.get("fb_posts", [])

# ====== GOOGLE SHEETS FUNCTIONS ======

# ====== Hàm tạo client để kết nối với Google Sheets ======
# Chức năng: Tạo client để kết nối với Google Sheets.
# - Authenticate với service account.
# - Trả về client đã sẵn sàng sử dụng.
def get_gsheet_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(
        st.secrets["gdrive_service_account"], scopes=scopes)
    return gspread.authorize(creds)

# ====== Hàm đảm bảo header Google Sheet ======
# Chức năng: Đảm bảo Google Sheet có header đúng định dạng.
# - Kiểm tra dòng đầu có đúng header không.
# - Clear và tạo lại nếu sai.
def ensure_sheet_header(worksheet, header):
    first_row = worksheet.row_values(1)
    if not first_row or first_row != header:
        worksheet.clear()
        worksheet.append_row(header)

# ====== Hàm lên lịch đăng bài ======
# Chức năng: Lên lịch đăng bài bằng cách ghi vào Google Sheet.
# - Ghi tất cả thông tin cần thiết vào sheet.
# - Scheduler sẽ đọc và đăng theo lịch.
def schedule_post_to_sheet(product_name, keywords, platform, post_time, token, page_id, mode, date_str, caption, image_path=""):
    gc = get_gsheet_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)
    ensure_sheet_header(worksheet, HEADER)
    
    worksheet.append_row([
        product_name, keywords, platform, post_time,
        token, page_id, mode, date_str,
        caption, image_path
    ])

# ====== AI & CONTENT FUNCTIONS ======

# ====== Hàm sinh caption bằng AI ======
# Chức năng: Sinh caption marketing cho sản phẩm bằng AI.
# - Gọi OpenAI API để tạo nội dung.
# - Style mộc mạc, có emoji, phù hợp platform.
def generate_caption(product_name, keywords, platform):
    prompt = f"""
    
Viết caption cho {platform} về sản phẩm "{product_name}" với từ khóa: {keywords}.
Style: mộc mạc, cảm xúc, có emoji. 
Format: 3-4 đoạn ngắn, hashtag #xuongbinhgom ở cuối và có hashtag dựa theo từ khóa đã nhập.
"""
    try:
        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.95
        )
        caption = response.choices[0].message.content.strip()
        if "#xuongbinhgom" not in caption.lower():
            caption += "\n\n#xuongbinhgom"
        return caption
    except OpenAIError as e:
        return f"⚠️ Không gọi được GPT: {e}"

# ====== Hàm gọi AI phân tích ======
# Chức năng: Gọi AI để phân tích dữ liệu với prompt tùy chỉnh.
# - Dùng cho dự báo hiệu quả và gợi ý chiến lược.
# - Trả về kết quả phân tích hoặc thông báo lỗi.
def call_ai_analysis(prompt, temperature=0.7):
    try:
        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature
        )
        return response.choices[0].message.content.strip()
    except OpenAIError as e:
        return f"⚠️ Lỗi AI: {e}"

# ====== IMAGE UPLOAD FUNCTIONS ======

# ====== Hàm upload ảnh lên Google Drive ======
# Chức năng: Upload ảnh lên Google Drive và trả về link ảnh công khai.
# - Dùng cho bài viết Facebook.
# - Set quyền chia sẻ công khai để có thể truy cập.
def upload_image_to_gdrive(image_bytes, filename):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gdrive_service_account"], scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    
    file_metadata = {
        'name': filename,
        'mimeType': 'image/jpeg'
    }
    media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype='image/jpeg')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file.get('id')
    
    # Set quyền chia sẻ công khai
    service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()
    
    return f'https://drive.google.com/uc?id={file_id}'

# ====== Hàm upload ảnh lên Cloudinary ======
# Chức năng: Upload ảnh lên Cloudinary và trả về link ảnh công khai.
# - Dùng cho bài viết Instagram.
# - Sử dụng cấu hình định sẵn upload preset để tự động xử lý ảnh.
# - Trả về link ảnh công khai.
def upload_image_to_cloudinary(image_bytes, preset="ml_default"):
    upload_result = cloudinary.uploader.upload(
        image_bytes,
        upload_preset=preset,
        resource_type="image"
    )
    return upload_result.get("secure_url")

# ====== Hàm xử lý upload ảnh theo platform ======
# Chức năng: Xử lý upload ảnh theo nền tảng phù hợp.
# - Facebook: Upload lên Google Drive.
# - Instagram: Upload lên Cloudinary.
# - Trả về link ảnh công khai.
# - Trả về None nếu có lỗi và thông báo lỗi.
def handle_image_upload(uploaded_image, platform):
    if not uploaded_image:
        return None
        
    img_bytes = uploaded_image.read()
    
    try:
        if platform == "Instagram":
            return upload_image_to_cloudinary(img_bytes, "ml_default")
        else:  # Facebook
            return upload_image_to_gdrive(img_bytes, uploaded_image.name)
    except Exception as e:
        st.error(f"Lỗi upload ảnh: {e}")
        return None

# ====== UI HELPER FUNCTIONS ======

# ====== Hàm hiển thị thống kê tổng hợp ======
# Chức năng: Hiển thị thống kê tổng hợp.
# - Tính tổng likes, comments, shares, reactions.
# - Hiển thị với emoji và format đẹp.
def display_analytics_stats(df):
    stats = [
        ("❤️", "Likes", df["likes"].sum()),
        ("💬", "Comments", df["comments"].sum()),
        ("🔁", "Shares", df["shares"].sum()),
        ("👍", "Reactions", df["reactions"].sum()),
    ]
    
    st.markdown("<b>Thống kê tổng hợp tương tác:</b>", unsafe_allow_html=True)
    st.markdown("""
    <div style='display:flex;flex-direction:column;align-items:flex-start;gap:0.5em;'>
    """ +
    "\n".join([
        f"<span style='font-size:1.3em;'><span style='font-size:1.2em;'>{icon}</span> <b style='font-size:1.1em;'>{value}</b> <span style='font-size:1em;color:#666;'>{label}</span></span>"
        for icon, label, value in stats
    ]) +
    "</div>", unsafe_allow_html=True)

# ====== Hàm tạo biểu đồ thống kê ======
# Chức năng: Tạo biểu đồ thống kê với các tùy chọn.
# - Nhóm theo ngày/tuần/tháng.
# - Hiển thị biểu đồ Line/Bar/Area.
def create_analytics_chart(df, group_type, chart_type):
    # Chuẩn bị dữ liệu theo thời gian
    df['created_time'] = pd.to_datetime(df['created_time'], errors='coerce')
    
    if group_type == "Ngày":
        df['period'] = df['created_time'].dt.date
    elif group_type == "Tuần":
        df['period'] = df['created_time'].dt.to_period('W').apply(lambda r: r.start_time.date())
    else:
        df['period'] = df['created_time'].dt.to_period('M').astype(str)
    
    # Tạo biểu đồ
    agg_df = df.groupby('period')[['likes', 'comments', 'shares', 'reactions']].sum().reset_index()
    fig, ax = plt.subplots(figsize=(8,4))
    
    if chart_type == "Line":
        for metric in ['likes', 'comments', 'shares', 'reactions']:
            sns.lineplot(data=agg_df, x='period', y=metric, label=metric.title(), marker='o', ax=ax)
    elif chart_type == "Bar":
        agg_df_melt = agg_df.melt(id_vars='period', value_vars=['likes','comments','shares','reactions'],
                                  var_name='Metric', value_name='Total')
        sns.barplot(data=agg_df_melt, x='period', y='Total', hue='Metric', palette='pastel', ax=ax)
    elif chart_type == "Area":
        agg_df.set_index('period')[['likes','comments','shares','reactions']].plot.area(ax=ax, alpha=0.5)
    
    ax.set_title(f"Tương tác theo {group_type.lower()}")
    ax.set_xlabel(group_type)
    ax.set_ylabel("Số lượng")
    plt.xticks(rotation=45)
    plt.legend()
    st.pyplot(fig)

# ====== Hàm làm đẹp output AI ======
# Chức năng: Làm đẹp output của AI thành HTML.
# - Parse nội dung thành các section.
# - Thêm CSS styling và emoji.
def beautify_ai_output(content):
    lines = content.split("<br>")
    html = []
    in_ul = False
    
    for line in lines:
        line_strip = line.strip()
        if re.match(r'^(<b>.*</b>|[A-ZÀ-Ỹa-zà-ỹ0-9 ,\-]+:)$', line_strip):
            if in_ul:
                html.append('</ul>')
                in_ul = False
            html.append(f'''<div style="background:#e3f2fd;padding:0.5em 1em;margin:1.1em 0 0.5em 0;border-radius:7px;font-weight:600;font-size:1.08em;color:#1976d2;display:flex;align-items:center;"><span style='font-size:1.2em;margin-right:0.5em;'>💡</span>{line_strip}</div>''')
        elif re.match(r'^(\-|•|\d+\.)\s', line_strip):
            if not in_ul:
                html.append('<ul style="margin-left:1.2em;margin-bottom:0.7em;">')
                in_ul = True
            html.append(f'<li style="margin-bottom:0.3em;list-style:none;"><span style="color:#43a047;font-size:1.1em;margin-right:0.5em;">✔️</span>{line_strip[2:]}</li>')
        elif line_strip:
            if in_ul:
                html.append('</ul>')
                in_ul = False
            html.append(f'<div style="margin-bottom:1em;font-size:1.08em;color:#222;">{line_strip}</div>')
    
    if in_ul:
        html.append('</ul>')
    
    return ''.join(html)

# ====== Hàm xóa bài viết ======
# Chức năng: Xóa bài viết một cách an toàn từ trạng thái phiên.
# - Kiểm tra tồn tại trước khi xóa.
# - Lưu dữ liệu vào file sau khi xóa.
# - Trả về True nếu xóa thành công.
# - Trả về False nếu không xóa được.
def safe_remove_post(idx):
    if (hasattr(st.session_state, 'posts') and 
        isinstance(st.session_state.posts, list) and 
        len(st.session_state.posts) >= idx):
        st.session_state.posts.pop(idx-1)
        save_posts(st.session_state.posts)

# ====== MAIN APPLICATION INTERFACE ======

# ====== Tạo tabs chính của ứng dụng ======
# Chức năng: Tạo 5 tabs chính cho các chức năng khác nhau.
# - Tab 1: Tạo nội dung bài đăng với AI
# - Tab 3: Thống kê hiệu quả từ Facebook API
# - Tab 2: Dự báo hiệu quả bài viết với AI
# - Tab 4: Gợi ý chiến lược cải thiện
# - Tab 5: Quản lý bài chờ duyệt thủ công
tab1, tab3, tab2, tab4, tab5 = st.tabs([
    "📝 Tạo nội dung", "📊 Hiệu quả", "🔮 Dự báo", "🎯 Gợi ý chiến lược", "📥 Bài chờ duyệt"
])

# ==========================================
# ====== TAB 1: TẠO NỘI DUNG BÀI ĐĂNG ======
# ==========================================
# Chức năng chính:
# - Nhập thông tin sản phẩm và từ khóa
# - Chọn nền tảng đăng (Facebook/Instagram) 
# - Chọn chế độ đăng: Tự động đúng giờ / Tự động hằng ngày / Chờ duyệt thủ công
# - Upload ảnh theo nền tảng (Google Drive cho FB, Cloudinary cho IG)
# - Sinh caption marketing bằng AI
# - Lên lịch đăng hoặc lưu vào danh sách chờ duyệt
# 
# Xử lý chi tiết:
# 1. Form input: product_name, keywords, platform, mode
# 2. Mode "Tự động đúng giờ": Chọn ngày/giờ + upload ảnh → Lên lịch 1 bài
# 3. Mode "Tự động hằng ngày": Chọn khoảng thời gian → Lên lịch nhiều bài
# 4. Mode "Chờ duyệt": Upload ảnh + lưu vào file JSON để duyệt sau
# 5. Gọi AI sinh caption theo prompt mộc mạc, có emoji
# 6. Lưu vào Google Sheets (auto) hoặc posts_data.json (manual)
with tab1:
    st.header("📝 Tạo nội dung bài đăng")
    
    # Input form - Xử lý nhập liệu từ người dùng
    # - Text input cho tên sản phẩm và từ khóa
    # - Selectbox cho nền tảng đăng (FB/IG)
    # - Radio buttons cho chế độ đăng (tự động/chờ duyệt)
    product_name = st.text_input("Tên sản phẩm")
    keywords = st.text_input("Từ khóa", "gốm, thủ công, mộc mạc, decor")
    platform = st.selectbox("Nền tảng", ["Facebook", "Instagram"])
    mode = st.radio("Chế độ đăng", ["📅 Tự động đúng giờ", "🤖 Tự động đăng đa dạng mỗi ngày", "👀 Chờ duyệt thủ công"])

    # Mode-specific inputs - Xử lý input theo từng chế độ
    # - Tự động đúng giờ: Chọn ngày/giờ + upload ảnh
    # - Tự động đa dạng: Chọn khoảng thời gian
    # - Chờ duyệt: Upload ảnh và lưu vào session
    if mode == "📅 Tự động đúng giờ":
        st.date_input("📅 Ngày đăng", value=date.today(), key="post_date_once")
        st.time_input("⏰ Giờ đăng", value=time(9, 0), key="post_time_once", step=timedelta(minutes=1))
        uploaded_image = st.file_uploader("Chọn ảnh từ máy tính", type=["jpg", "jpeg", "png"])
        
        if uploaded_image:
            image_url = handle_image_upload(uploaded_image, platform)
            if image_url:
                st.session_state[f"{platform.lower()}_url"] = image_url
                    
    elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
        st.date_input("📅 Ngày bắt đầu", value=date.today(), key="start_date_loop")
        st.date_input("📅 Ngày kết thúc", value=date.today(), key="end_date_loop")
        st.time_input("⏰ Giờ đăng mỗi ngày", value=time(9, 0), key="post_time_loop", step=timedelta(minutes=1))
        
    else:  # Chờ duyệt thủ công
        uploaded_image = st.file_uploader("Chọn ảnh từ máy tính", type=["jpg", "jpeg", "png"], key="manual_upload")
        
        if uploaded_image:
            image_url = handle_image_upload(uploaded_image, platform)
            if image_url:
                st.session_state[f"{platform.lower()}_url_manual"] = image_url

    # Process button - Xử lý khi người dùng nhấn nút
    # - Kiểm tra thông tin đầu vào
    # - Sinh caption bằng AI
    # - Xử lý theo từng chế độ đăng
    if st.button("✨ Xử lý bài đăng"):
        with st.spinner("Đang xử lý bài đăng..."):
            if not product_name or not keywords:
                st.warning("⚠️ Vui lòng nhập đủ thông tin.")
            else:
                caption = generate_caption(product_name, keywords, platform)
                if caption.startswith("⚠️"):
                    st.error(caption)
                else:
                    if mode == "📅 Tự động đúng giờ":
                        # Xử lý đăng một bài
                        # - Kết hợp ngày và giờ
                        # - Lấy token và page_id theo platform
                        # - Lên lịch đăng vào Google Sheet
                        post_datetime = datetime.combine(st.session_state["post_date_once"], st.session_state["post_time_once"])
                        
                        if platform == "Instagram":
                            image_path = st.session_state.get("instagram_url", "")
                            token, page_id = IG_TOKEN, IG_ID
                        else:
                            image_path = st.session_state.get("facebook_url", "")
                            token, page_id = FB_PAGE_TOKEN, FB_PAGE_ID
                        
                        schedule_post_to_sheet(
                            product_name, keywords, platform,
                            st.session_state["post_time_once"].strftime("%H:%M"),
                            token, page_id, "once",
                            post_datetime.strftime("%Y-%m-%d"),
                            caption, image_path
                        )
                        
                        st.text_area("📋 Nội dung đề xuất", caption, height=150)
                        st.success(f"📅 Đã lên lịch đăng {platform} vào {post_datetime.strftime('%d/%m/%Y %H:%M')}")
                        
                    elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
                        # Xử lý đăng nhiều bài
                        # - Lặp qua từng ngày trong khoảng thời gian
                        # - Sinh caption mới cho mỗi ngày
                        # - Lên lịch vào Google Sheet
                        current_day = st.session_state["start_date_loop"]
                        post_count = 0
                        
                        while current_day <= st.session_state["end_date_loop"]:
                            auto_caption = generate_caption(product_name, keywords, platform)
                            if auto_caption.startswith("⚠️"):
                                st.error(auto_caption)
                                break
                            
                            token, page_id = (IG_TOKEN, IG_ID) if platform == "Instagram" else (FB_PAGE_TOKEN, FB_PAGE_ID)
                            
                            schedule_post_to_sheet(
                                product_name, keywords, platform,
                                st.session_state["post_time_loop"].strftime("%H:%M"),
                                token, page_id, "daily",
                                current_day.strftime("%Y-%m-%d"),
                                auto_caption, ""
                            )
                            
                            current_day += timedelta(days=1)
                            post_count += 1
                        else:
                            st.success(f"Đã lên lịch {post_count} bài đăng từ {st.session_state['start_date_loop']} đến {st.session_state['end_date_loop']}")
                            
                    else:  # Chờ duyệt thủ công
                        # Xử lý lưu bài chờ duyệt
                        # - Kiểm tra ảnh đã upload
                        # - Lưu thông tin vào session state
                        # - Cập nhật file JSON
                        image_path = st.session_state.get(f"{platform.lower()}_url_manual", "")
                        if not image_path:
                            st.error(f"Bạn phải upload ảnh cho {platform}!")
                            st.stop()
                        
                        st.text_area("📋 Nội dung đề xuất", caption, height=150)
                        
                        # Safely add to posts
                        posts = get_safe_posts_data()
                        posts.append({
                            "id": str(uuid.uuid4())[:8],
                            "product": product_name,
                            "platform": platform,
                            "caption": caption,
                            "time": "chờ duyệt",
                            "image": image_path,
                            "likes": 0, "comments": 0, "shares": 0, "reach": 0
                        })
                        st.session_state.posts = posts
                        save_posts(posts)
                        st.session_state.manual_post_success = True
                        st.rerun()

    # Success message - Hiển thị thông báo thành công
    if st.session_state.get("manual_post_success"):
        st.success("✅ Đã lưu bài viết để duyệt thủ công.")
        st.session_state.manual_post_success = False

# ==========================================
# ====== TAB 3: THỐNG KÊ HIỆU QUẢ BÀI VIẾT ======
# ==========================================
# Chức năng chính:
# - Lấy dữ liệu thống kê thực từ Facebook API
# - Hiển thị bảng chi tiết từng bài viết
# - Hiển thị thống kê tổng hợp (likes, comments, shares, reactions)
# - Tạo biểu đồ tương tác theo thời gian với nhiều options
#
# Xử lý chi tiết:
# 1. Gọi get_facebook_data() để lấy posts từ Facebook Graph API
# 2. Prepare DataFrame với các cột: likes, comments, shares, reactions  
# 3. Hiển thị bảng detail_df với format đẹp
# 4. Gọi display_analytics_stats() để hiển thị tổng hợp
# 5. Tạo chart với options: nhóm theo Ngày/Tuần/Tháng, type Line/Bar/Area
# 6. Dùng matplotlib + seaborn để vẽ biểu đồ
with tab3:
    st.header("📊 Hiệu quả bài viết thực")
    
    # Lấy dữ liệu từ Facebook API và lưu vào session state
    fb_posts = get_facebook_data()
    
    if fb_posts:
        # Xử lý dữ liệu thành DataFrame
        # - Chuyển đổi dữ liệu thô thành DataFrame với các cột metrics
        # - Tạo bản sao để hiển thị bảng chi tiết
        # - Đổi tên cột thành tiếng Việt và thêm emoji
        df_fb = prepare_dataframe(fb_posts, ["likes", "comments", "shares", "reactions"])
        detail_df = df_fb[["caption", "likes", "comments", "shares", "reactions"]].copy()
        detail_df.columns = ["Nội dung", "❤️ Likes", "💬 Comments", "🔁 Shares", "👍 Reactions"]
        
        # Hiển thị bảng chi tiết từng bài viết
        # - Sử dụng markdown để tạo tiêu đề
        # - Hiển thị DataFrame với container width full
        st.markdown("<b>Chi tiết từng bài viết:</b>", unsafe_allow_html=True)
        st.dataframe(detail_df, use_container_width=True)
        
        # Hiển thị thống kê tổng hợp
        # - Gọi hàm display_analytics_stats để tính và hiển thị tổng số
        display_analytics_stats(df_fb)
        
        # Phần biểu đồ thống kê
        # - Tạo tiêu đề với padding top
        # - Chia layout thành 2 cột để chọn options
        st.markdown("<div style='padding-top:2em;'><b>Biểu đồ thống kê tương tác theo thời gian:</b></div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            # Option nhóm theo thời gian: Ngày/Tuần/Tháng
            group_type = st.selectbox("Thống kê theo", ["Ngày", "Tuần", "Tháng"])
        with col2:
            # Option loại biểu đồ: Line/Bar/Area
            chart_type = st.selectbox("Chọn loại biểu đồ", ["Line", "Bar", "Area"])
        
        # Tạo và hiển thị biểu đồ theo options đã chọn
        create_analytics_chart(df_fb, group_type, chart_type)
    else:
        # Thông báo khi chưa có dữ liệu
        st.info("Chưa có dữ liệu bài viết.")

# ==========================================
# ====== TAB 2: DỰ BÁO HIỆU QUẢ BÀI VIẾT ======
# ==========================================
# Chức năng chính:
# - Nhập caption dự kiến và dự báo hiệu quả bằng AI
# - So sánh với dữ liệu lịch sử để đưa ra dự báo
# - Hiển thị kết quả với format đẹp
#
# Xử lý chi tiết:
# 1. Form input: caption_forecast only (như logic cũ)
# 2. Lấy dữ liệu lịch sử từ Facebook API
# 3. Tạo prompt cho AI đơn giản
# 4. Gọi call_ai_analysis() 
# 5. Hiển thị kết quả trực tiếp
with tab2:
    st.header("🔮 Dự báo hiệu quả bài viết")
    
    # Input form - Chỉ nhập caption như logic cũ
    caption_forecast = st.text_area("✍️ Nhập caption dự kiến")
    
    # Nút phân tích - chỉ active khi có caption
    if st.button("🔍 Phân tích & Dự báo", disabled=(not caption_forecast.strip())):
        with st.spinner("Đang phân tích & dự báo bằng AI..."):
            # Lấy dữ liệu lịch sử từ Facebook API
            fb_posts = get_facebook_data()
            
            if not fb_posts:
                st.warning("⚠️ Chưa có dữ liệu lịch sử để dự báo.")
            else:
                # Tạo prompt đơn giản cho AI
                prompt = f"""
Bạn là chuyên gia marketing. Dựa trên nội dung bài viết sau, hãy dự báo hiệu quả:

"{caption_forecast}"

Hãy đưa ra dự báo theo format:

🎯 Mức độ hiệu quả dự kiến: (cao/trung bình/thấp)

📊 Ước lượng: 
- Likes: X-Y likes
- Comments: X-Y comments  
- Shares: X-Y shares

🧠 Lý do:
[Giải thích tại sao dự báo như vậy]

💡 Gợi ý cải thiện:
[Đưa ra gợi ý để tăng hiệu quả]
                """
                
                # Gọi AI phân tích
                result = call_ai_analysis(prompt, temperature=0.7)
                
                if result.startswith("⚠️"):
                    st.error(result)
                else:
                    # Hiển thị kết quả trực tiếp với beautify_ai_output
                    content_formatted = result.replace('\n','<br>')
                    st.markdown(f"""
<div style='background:#f6f8fc;padding:1.5em;border-radius:12px;margin-top:1em;'>
    <div style='font-size:1.15em;margin-bottom:1em;color:#1976d2;'><b>🔮 Dự báo hiệu quả:</b></div>
    <div style='font-size:1.08em;line-height:1.7;color:#222;'>
        {beautify_ai_output(content_formatted)}
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# ====== TAB 4: GỢI Ý CHIẾN LƯỢC CẢI THIỆN ======
# ==========================================
# Chức năng chính:
# - Phân tích toàn bộ dữ liệu hiệu quả bài viết
# - So sánh hiệu quả thực tế với kỳ vọng
# - Đưa ra 3 chiến lược cải thiện cụ thể bằng AI
# - Ưu tiên các hành động có thể thực hiện ngay
#
# Xử lý chi tiết:
# 1. Lấy dữ liệu Facebook posts với đầy đủ metrics
# 2. Prepare DataFrame với columns: platform, caption, likes, comments, shares, reactions
# 3. Chuyển đổi DataFrame thành string để gửi cho AI
# 4. Tạo prompt yêu cầu AI phân tích và đưa ra gợi ý
# 5. Gọi call_ai_analysis() với temperature=0.7 để có độ sáng tạo vừa phải
# 6. Dùng beautify_ai_output() để format kết quả thành HTML đẹp
# 7. Hiển thị với background styling và màu sắc
with tab4:
    st.header("🎯 Gợi ý chiến lược cải thiện")
    
    if st.button("🧠 Gợi ý từ AI"):
        # Lấy dữ liệu bài viết từ Facebook API
        fb_posts = get_facebook_data()
        
        if fb_posts:
            # Chuẩn bị DataFrame với các cột metrics cần thiết
            df = prepare_dataframe(fb_posts, ['platform','caption','likes','comments','shares','reactions'])
            
            # Tạo prompt yêu cầu AI phân tích và đưa ra gợi ý
            prompt = f"""
Dưới đây là dữ liệu hiệu quả các bài viết:

{df[['platform','caption','likes','comments','shares','reactions']].to_string(index=False)}

Hãy:
- So sánh hiệu quả thực tế với kỳ vọng
- Gợi ý 3 chiến lược cải thiện cụ thể
- Ưu tiên hành động có thể thực hiện ngay
"""
            
            with st.spinner("Đang phân tích..."):
                # Gọi AI phân tích với temperature=0.7 để có độ sáng tạo vừa phải
                content = call_ai_analysis(prompt, temperature=0.7)
                
                if content.startswith("⚠️"):
                    # Hiển thị lỗi nếu AI trả về thông báo lỗi
                    st.error(content)
                else:
                    # Format nội dung AI trả về thành HTML đẹp
                    content_formatted = content.replace('\n','<br>')
                    st.markdown(f"""
<div style='background:#f6f8fc;padding:1.5em;border-radius:12px;margin-top:1em;'>
    <div style='font-size:1.15em;margin-bottom:1em;color:#1976d2;'><b>✨ Gợi ý từ AI:</b></div>
    <div style='font-size:1.08em;line-height:1.7;color:#222;'>
        {beautify_ai_output(content_formatted)}
    </div>
</div>
""", unsafe_allow_html=True)
        else:
            # Hiển thị thông báo khi chưa có dữ liệu để phân tích
            st.info("Chưa có dữ liệu để phân tích.")

# ==========================================
# ====== TAB 5: QUẢN LÝ BÀI CHỜ DUYỆT THỦ CÔNG ======
# ==========================================
# Chức năng chính:
# - Hiển thị danh sách bài viết chờ duyệt từ file JSON
# - Cho phép duyệt (approve) hoặc xóa từng bài viết
# - Khi duyệt: tự động lên lịch đăng ngay lập tức
# - Hiển thị bảng chi tiết tất cả bài chờ duyệt
#
# Xử lý chi tiết:
# 1. Load posts từ file posts_data.json bằng load_posts()
# 2. Hiển thị từng post trong expander với caption preview
# 3. Mỗi post có 2 buttons: "✅ Duyệt" và "❌ Xóa"
# 4. Khi duyệt: 
#    - Lấy thời gian hiện tại làm thời gian đăng
#    - Gọi schedule_post_to_sheet() để lên lịch đăng ngay
#    - Gọi safe_remove_post() để xóa khỏi danh sách chờ
#    - st.rerun() để refresh UI
# 5. Khi xóa: chỉ gọi safe_remove_post() và st.rerun()
# 6. Hiển thị DataFrame tổng hợp tất cả posts
with tab5:
    st.header("📥 Bài chờ duyệt")
    
    # Load pending posts với spinner
    with st.spinner("🔄 Đang tải danh sách bài viết chờ duyệt..."):
        posts = load_posts() or []
        st.session_state.posts = posts
    
    if posts:
        st.markdown("<b>Danh sách bài viết chờ duyệt:</b>", unsafe_allow_html=True)
        
        # Hiển thị từng bài viết theo thứ tự mới nhất lên đầu
        for idx in range(len(posts), 0, -1):
            post = posts[idx-1]
            
            # Mở rộng để xem chi tiết bài viết
            with st.expander(f"{post['platform']} | {post['caption'][:30]}..."):
                # Hiển thị nội dung caption
                st.write(post['caption'])
                
                # Hiển thị link ảnh nếu có
                if post.get('image'):
                    st.markdown(f'<a href="{post["image"]}" target="_blank">🔗 Ảnh đính kèm</a>', unsafe_allow_html=True)
                
                # Tạo 3 cột cho các nút thao tác
                col1, col2, col3 = st.columns(3)
                
                # Cột 1: Nút duyệt bài viết
                with col1:
                    if st.button(f"✅ Duyệt #{idx}"):
                        with st.spinner("Đang xử lý..."):
                            # Lấy thời gian hiện tại
                            now = datetime.now()
                            
                            # Xác định token và page_id dựa trên platform
                            token, page_id = (IG_TOKEN, IG_ID) if post['platform'].lower() == "instagram" else (FB_PAGE_TOKEN, FB_PAGE_ID)
                            
                            # Lên lịch đăng bài ngay lập tức
                            schedule_post_to_sheet(
                                post.get('product', ''), "", post['platform'],
                                now.strftime("%H:%M"), token, page_id, "once",
                                now.strftime("%Y-%m-%d"), post['caption'],
                                post.get('image', "")
                            )
                            
                            # Xóa bài viết khỏi danh sách chờ
                            safe_remove_post(idx)
                            st.rerun()
                
                # Cột 3: Nút xóa bài viết
                with col3:
                    if st.button(f"❌ Xóa #{idx}"):
                        with st.spinner("Đang xóa..."):
                            # Xóa bài viết khỏi danh sách chờ
                            safe_remove_post(idx)
                            st.rerun()
        
        # Hiển thị bảng dữ liệu chi tiết (chỉ 1 lần duy nhất)
        st.markdown("<b>Dữ liệu chi tiết:</b>", unsafe_allow_html=True)
        df_posts = pd.DataFrame(posts)
        st.dataframe(df_posts)
    else:
        # Thông báo khi không có bài viết nào
        st.info("Chưa có bài viết nào chờ duyệt.")

# ====== SESSION STATE INITIALIZATION ======
# Chức năng: Khởi tạo trạng thái phiên cho ứng dụng Streamlit
# - Định nghĩa các biến trạng thái mặc định
# - Kiểm tra và gán giá trị nếu chưa tồn tại trong session
# - Đảm bảo dữ liệu được duy trì giữa các lần tải lại trang
def_states = {
    "posts": load_posts() or []  # Danh sách bài viết chờ duyệt
}

for key, val in def_states.items():
    if key not in st.session_state:
        st.session_state[key] = val