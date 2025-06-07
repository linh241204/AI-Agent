import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, date, time
import uuid
import csv
import requests
from openai import OpenAI, OpenAIError
import base64
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
import streamlit as st
import toml

// Hàm khởi tạo state
def_states = {
    "posts": load_posts()  # Đọc từ file thay vì []
}
for key, val in def_states.items():
    if key not in st.session_state:
        st.session_state[key] = val
        
DATA_FILE = "posts_data.json"
# ====== Hàm lưu danh sách bài viết ======Add commentMore actions
# Chức năng: Lưu danh sách bài viết vào file JSON.
# - Ghi đè toàn bộ danh sách vào file.
# - Dùng khi thêm/xóa/sửa bài chờ duyệt.
def save_posts(posts, filename=DATA_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

# ====== Hàm đọc danh sách bài viết ======
# Chức năng: Đọc danh sách bài viết từ file JSON.
# - Nếu file chưa tồn tại, trả về list rỗng.
def load_posts(filename=DATA_FILE):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return []
    
#Cấu hình thư viện để up ảnh đăng lên ig
#Mục đích: Giống gg drive, lấy ảnh từ đây để đăng lên ig
cloudinary.config(
    cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
    api_key=st.secrets["CLOUDINARY_API_KEY"],
    api_secret=st.secrets["CLOUDINARY_API_SECRET"],
    secure=True)

#Id của sheet và đặt tên cho sheet
SPREADSHEET_ID = "1HUWXhKwglpJtp6yRuUfo2oy76uNKxDRx5n0RUG2q0hM"
SHEET_NAME = "xuongbinhgom"

#Tạo dòng đầu tiên của sheet
HEADER = [
    "product", "keywords", "platform", "time_str", "token",
    "page_id", "mode", "date_str", "caption", "image_path"
]
#Hàm để lấy quyền truy cập vào gg sheet
def get_gsheet_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(
        st.secrets["gdrive_service_account"], scopes=scopes)
    return gspread.authorize(creds)

#Streamlit app tạo ra dữ liệu và fill vào file excel sau đó dùng cronjob (chạy bằng python) để lấy dữ liệu từ file excel để đăng lên fb/ig. 
#Streamlit k hỗ trợ cronjob nên phải dùng python ở máy
#K dùng data base để lưu dữ liệu nên phải dùng cách này
#Sử dụng để xóa dòng sau khi upload dữ liệu lên fb hoặc ig. Nếu đúng thì file excel sẽ k còn dữ liệu gì sau khi chạy, nhưng lỗi nên còn sót lại header
def ensure_sheet_header(worksheet, header):
    first_row = worksheet.row_values(1)
    if not first_row or first_row != header:
        worksheet.clear()
        worksheet.append_row(header)

# ====== Đọc token và ID từ secrets ======
FB_PAGE_TOKEN = st.secrets["FB_PAGE_TOKEN"]
FB_PAGE_ID = st.secrets["FB_PAGE_ID"]
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# ====== Tạo OpenAI client ======
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

# ====== Đọc IG_TOKEN và IG_ID từ secrets
IG_TOKEN = st.secrets.get("IG_TOKEN", "")
IG_ID = st.secrets.get("IG_ID", "")

# ====== Hàm sinh caption từ GPT ======
# Chức năng: Sinh caption marketing cho sản phẩm, nền tảng, từ khóa bằng AI GPT.
# - Gửi prompt tới OpenAI, nhận về caption.
# - Nếu lỗi API, trả về thông báo lỗi.
def generate_caption(product_name, keywords, platform):
    prompt = f"""
Bạn là chuyên gia nội dung sáng tạo cho thương hiệu gốm thủ công cao cấp.
Hãy viết một bài marketing truyền cảm hứng (~150–200 từ), phù hợp đăng trên {platform}, cho sản phẩm "{product_name}", dùng từ khóa: {keywords}.
Giọng văn mộc mạc, sâu lắng, yêu nét đẹp giản dị. Kết thúc có hashtag #xuongbinhgom và 3-5 hashtag khác.
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

# Hàm upload ảnh lên Google Drive và trả về link ảnh
# Chức năng: Upload ảnh lên Google Drive bằng service account, trả về link ảnh.
# - Tạo file ảnh trên Drive.
# - Set quyền chia sẻ công khai.
# - Trả về link ảnh.
# - Nếu lỗi xác thực hoặc upload, sẽ trả về lỗi.
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
    # Lấy direct link (Google Drive direct link cho ảnh)
    direct_link = f'https://drive.google.com/uc?id={file_id}'
    return direct_link

# ====== Hàm tạo content lên Instagram ======
# Chức năng: Đăng bài lên Instagram qua API Graph.
# - Tạo media object (ảnh + caption).
# - Publish media object lên Instagram.
# - Trả về kết quả API (thành công/lỗi).
def post_content_to_instagram(ig_user_id, access_token, image_url, caption):
    # Bước 1: Tạo media object
    create_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    create_params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token
    }
    create_resp = requests.post(create_url, data=create_params)
    result = create_resp.json()
    if "id" not in result:
        return {"error": result}
    creation_id = result["id"]

    # Bước 2: Publish media object
    publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    publish_params = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    publish_resp = requests.post(publish_url, data=publish_params)
    return publish_resp.json()

# IG k nhận link từ drive về nên phải upload lên đây
# ====== Hàm upload ảnh lên Cloudinary ======
# Chức năng: Upload ảnh lên Cloudinary, trả về link public.
# - Upload bằng preset.
# - Trả về link public.
def upload_image_to_cloudinary(image_bytes, preset="ml_default"):
    upload_result = cloudinary.uploader.upload(
        image_bytes,
        upload_preset=preset,
        resource_type="image"
    )
    return upload_result.get("secure_url")

# ====== Tabs giao diện chính ======
# Chức năng: Tạo các tab giao diện cho app quản lý nội dung MXH.
# - tab1: Tạo nội dung bài đăng mới, sinh caption AI, upload ảnh, lên lịch đăng, lưu bài chờ duyệt.
# - tab3: Thống kê hiệu quả bài viết Facebook, hiển thị bảng, biểu đồ tương tác.
# - tab2: Dự báo hiệu quả bài viết mới dựa trên caption, thời gian, dữ liệu lịch sử, AI phân tích.
# - tab4: Gợi ý chiến lược cải thiện nội dung, thời gian, nền tảng dựa trên dữ liệu thực tế, AI sinh gợi ý.
# - tab5: Quản lý, duyệt/xóa các bài viết chờ duyệt, thao tác với file posts_data.json.
tab1, tab3, tab2, tab4, tab5 = st.tabs([
    "📝 Tạo nội dung", "📊 Hiệu quả", "🔮 Dự báo", "🎯 Gợi ý chiến lược", "📥 Bài chờ duyệt"
])

# ====== Xử lý tab1: Tạo nội dung ======
# Chức năng: Cho phép người dùng nhập thông tin sản phẩm, từ khóa, chọn nền tảng, chế độ đăng, upload ảnh, sinh caption AI, lên lịch đăng hoặc lưu bài chờ duyệt.
# - Nếu "Tự động đúng giờ": upload ảnh lên Cloudinary, lên lịch đăng Facebook/Instagram.
# - Nếu "Tự động đăng đa dạng mỗi ngày": sinh caption cho từng ngày, lên lịch đăng nhiều ngày.
# - Nếu "Chờ duyệt thủ công": upload ảnh lên Google Drive, lưu vào danh sách chờ duyệt.
# - Kiểm tra điều kiện đầu vào, báo lỗi rõ ràng nếu thiếu thông tin hoặc lỗi upload/caption.
with tab1:
    st.header("📝 Tạo nội dung bài đăng")
    # --- Nhập liệu từ người dùng ---
    # Người dùng nhập tên sản phẩm, từ khóa, chọn nền tảng, chế độ đăng
    product_name = st.text_input("Tên sản phẩm")
    keywords = st.text_input("Từ khóa", "gốm, thủ công, mộc mạc, decor")
    platform = st.selectbox("Nền tảng", ["Facebook", "Instagram"])
    mode = st.radio("Chế độ đăng", ["📅 Tự động đúng giờ", "🤖 Tự động đăng đa dạng mỗi ngày", "👀 Chờ duyệt thủ công"])

    # --- Tùy chọn thời gian và upload ảnh ---
    # Xử lý theo từng chế độ đăng và từng nền tảng
    if mode == "📅 Tự động đúng giờ":
        st.date_input("📅 Ngày đăng", value=date.today(), key="post_date_once")
        st.time_input("⏰ Giờ đăng", value=time(9, 0), key="post_time_once", step=timedelta(minutes=1))
        uploaded_image = st.file_uploader("Chọn ảnh từ máy tính", type=["jpg", "jpeg", "png"], accept_multiple_files=False)
        if uploaded_image:
            img_bytes = uploaded_image.read()
            if platform == "Instagram":
                # Upload lên Cloudinary cho Instagram
                cloudinary_url = upload_image_to_cloudinary(img_bytes, "ml_default")
                if cloudinary_url:
                    st.session_state.cloudinary_url = cloudinary_url
                else:
                    st.error("Tải ảnh lên Cloudinary không thành công!")
            else:  # Facebook
                # Upload lên Google Drive cho Facebook
                try:
                    gdrive_link = upload_image_to_gdrive(img_bytes, uploaded_image.name)
                    st.session_state.gdrive_url = gdrive_link
                except Exception as e:
                    st.error(f"Tải ảnh lên Google Drive không thành công: {e}")
    elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
        # Người dùng chọn ngày bắt đầu, ngày kết thúc, giờ đăng mỗi ngày
        st.date_input("📅 Ngày bắt đầu", value=date.today(), key="start_date_loop")
        st.date_input("📅 Ngày kết thúc", value=date.today(), key="end_date_loop")
        st.time_input("⏰ Giờ đăng mỗi ngày", value=time(9, 0), key="post_time_loop", step=timedelta(minutes=1))
        # Không upload ảnh, chỉ đăng caption (scheduler sẽ tự lấy ảnh từ Drive nếu cần)
    else:  # 👀 Chờ duyệt thủ công
        uploaded_image = st.file_uploader("Chọn ảnh từ máy tính", type=["jpg", "jpeg", "png"], accept_multiple_files=False, key="manual_file_uploader")
        if uploaded_image:
            img_bytes = uploaded_image.read()
            if platform == "Instagram":
                cloudinary_url = upload_image_to_cloudinary(img_bytes, "ml_default")
                if cloudinary_url:
                    st.session_state.cloudinary_url_manual = cloudinary_url
                else:
                    st.error("Tải ảnh lên Cloudinary không thành công!")
            else:
                try:
                    gdrive_link = upload_image_to_gdrive(img_bytes, uploaded_image.name)
                    st.session_state.gdrive_url_manual = gdrive_link
                except Exception as e:
                    st.error(f"Tải ảnh lên Google Drive không thành công: {e}")
    #Bắt đầu từ đây mới là luồng xử lí chạy (còn bên trên chỉ là dữ liệu)
    # --- Xử lý khi bấm nút "✨ Xử lý bài đăng" ---
    if st.button("✨ Xử lý bài đăng"):
        with st.spinner("Đang xử lý bài đăng..."):
            # Kiểm tra đầu vào
            if not product_name or not keywords:
                st.warning("⚠️ Vui lòng nhập đủ thông tin.")
            else:
                # Gọi AI sinh caption (Gọi thì mới nhảy vào hàm sinh caption bên trên để xử lí)
                caption = generate_caption(product_name, keywords, platform)
                if caption.startswith("⚠️") or "Không gọi được GPT" in caption:
                    st.error(caption)
                else:
                    # Xử lý theo từng mode và platform
                    if mode == "📅 Tự động đúng giờ":
                        if platform == "Instagram":
                            cloudinary_url = st.session_state.get("cloudinary_url", "")
                            post_datetime = datetime.combine(st.session_state["post_date_once"], st.session_state["post_time_once"])
                            gc = get_gsheet_client()
                            sh = gc.open_by_key(SPREADSHEET_ID)
                            worksheet = sh.worksheet(SHEET_NAME)
                            ensure_sheet_header(worksheet, HEADER)
                            worksheet.append_row([
                                product_name, keywords, platform, st.session_state["post_time_once"].strftime("%H:%M"),
                                IG_TOKEN, IG_ID, "once", post_datetime.strftime("%Y-%m-%d"),
                                caption, cloudinary_url
                            ])
                            st.text_area("📋 Nội dung đề xuất", caption, height=150)
                            st.success(f"📅 Đã lên lịch đăng Instagram vào {post_datetime.strftime('%d/%m/%Y %H:%M')}")
                        else:  # Facebook
                            image_path = st.session_state.get("gdrive_url", "")
                            post_datetime = datetime.combine(st.session_state["post_date_once"], st.session_state["post_time_once"])
                            gc = get_gsheet_client()
                            sh = gc.open_by_key(SPREADSHEET_ID)
                            worksheet = sh.worksheet(SHEET_NAME)
                            ensure_sheet_header(worksheet, HEADER)
                            worksheet.append_row([
                                product_name, keywords, platform, st.session_state["post_time_once"].strftime("%H:%M"),
                                FB_PAGE_TOKEN, FB_PAGE_ID, "once", post_datetime.strftime("%Y-%m-%d"),
                                caption, image_path
                            ])
                            st.text_area("📋 Nội dung đề xuất", caption, height=150)
                            st.success(f"📅 Đã lên lịch đăng Facebook vào {post_datetime.strftime('%d/%m/%Y %H:%M')}")
                    elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
                        current_day = st.session_state["start_date_loop"]
                        while current_day <= st.session_state["end_date_loop"]:
                            auto_caption = generate_caption(product_name, keywords, platform)
                            if auto_caption.startswith("⚠️") or "Không gọi được GPT" in auto_caption:
                                st.error(auto_caption)
                                break
                            if platform == "Instagram":
                                # Lên lịch đăng IG: ghi vào file CSV với link Cloudinary (nếu muốn scheduler IG)
                                cloudinary_url = st.session_state.get("cloudinary_url", "")
                                gc = get_gsheet_client()
                                sh = gc.open_by_key(SPREADSHEET_ID)
                                worksheet = sh.worksheet(SHEET_NAME)
                                ensure_sheet_header(worksheet, HEADER)
                                worksheet.append_row([
                                    product_name, keywords, platform, st.session_state["post_time_loop"].strftime("%H:%M"),
                                    IG_TOKEN, IG_ID, "daily", current_day.strftime("%Y-%m-%d"),
                                    auto_caption, cloudinary_url
                                ])
                            else:
                                # Lên lịch đăng FB: ghi vào file CSV với link Drive
                                gc = get_gsheet_client()
                                sh = gc.open_by_key(SPREADSHEET_ID)
                                worksheet = sh.worksheet(SHEET_NAME)
                                ensure_sheet_header(worksheet, HEADER)
                                worksheet.append_row([
                                    product_name, keywords, platform, st.session_state["post_time_loop"].strftime("%H:%M"),
                                    FB_PAGE_TOKEN, FB_PAGE_ID, "daily", current_day.strftime("%Y-%m-%d"),
                                    auto_caption, ""
                                ])
                            current_day += timedelta(days=1)
                        else:
                            st.success(f"Đã lên lịch đăng từ {st.session_state['start_date_loop']} đến {st.session_state['end_date_loop']}")
                    else:  # 👀 Chờ duyệt thủ công
                        if platform == "Instagram":
                            image_path = st.session_state.get("cloudinary_url_manual", "")
                            if not image_path:
                                st.error("Bạn phải upload ảnh lên Cloudinary cho Instagram!")
                                st.stop()
                        else:
                            image_path = st.session_state.get("gdrive_url_manual", "")
                            if not image_path:
                                st.error("Bạn phải upload ảnh lên Google Drive cho Facebook!")
                                st.stop()
                        st.text_area("📋 Nội dung đề xuất", caption, height=150)
                        st.session_state.posts.append({
                            "id": str(uuid.uuid4())[:8],
                            "product": product_name,
                            "platform": platform,
                            "caption": caption,
                            "time": "chờ duyệt",
                            "image": image_path,
                            "likes": 0, "comments": 0, "shares": 0, "reach": 0
                        })
                        save_posts(st.session_state.posts)
                        st.session_state.manual_post_success = True
                        st.rerun()

    # --- Đặt thông báo thành công ở cuối tab1 ---
    if st.session_state.get("manual_post_success"):
        st.success("✅ Đã lưu bài viết để duyệt thủ công.")
        st.session_state.manual_post_success = False

# ====== Xử lý tab3: Thống kê hiệu quả ======
# Chức năng: Lấy dữ liệu bài viết Facebook, thống kê tổng hợp, hiển thị bảng chi tiết và biểu đồ tương tác.
# - Gọi API Facebook lấy danh sách bài viết, lấy chi tiết từng bài (likes, comments, shares, reactions).
# - Hiển thị bảng chi tiết các bài viết.
# - Thống kê tổng hợp các chỉ số tương tác.
# - Vẽ biểu đồ tương tác theo ngày/tuần/tháng, cho phép chọn loại biểu đồ (line, bar, area).
with tab3:
    st.header("📊 Hiệu quả bài viết thực")
    # --- Lấy dữ liệu Facebook ---
    # Nếu chưa lấy dữ liệu, gọi API Facebook lấy danh sách bài viết và chi tiết từng bài
    if "fb_data_fetched" not in st.session_state:
        with st.spinner("Đang lấy dữ liệu ..."):
            def fetch_facebook_posts(page_id, access_token, limit=20):
                # Gọi API lấy danh sách bài viết
                url = f"https://graph.facebook.com/v19.0/{page_id}/posts"
                params = {
                    "fields": "id,message,created_time",
                    "limit": limit,
                    "access_token": access_token
                }
                resp = requests.get(url, params=params)
                data = resp.json()
                return data.get("data", [])
            def fetch_post_stats(post_id, access_token):
                # Gọi API lấy chi tiết từng bài viết
                url = f"https://graph.facebook.com/v19.0/{post_id}"
                params = {
                    "fields": "message,likes.summary(true),comments.summary(true),shares,reactions.summary(true)",
                    "access_token": access_token
                }
                resp = requests.get(url, params=params)
                return resp.json()
            fb_posts = fetch_facebook_posts(FB_PAGE_ID, FB_PAGE_TOKEN, limit=20)
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
    # --- Hiển thị bảng chi tiết ---
    # Hiển thị bảng các bài viết, caption, số likes, comments, shares, reactions
    if st.session_state.get("fb_posts"):
        df_fb = pd.DataFrame(st.session_state.fb_posts)
        for col in ["likes", "comments", "shares", "reactions"]:
            if col not in df_fb.columns:
                df_fb[col] = 0
            df_fb[col] = pd.to_numeric(df_fb[col], errors="coerce").fillna(0).astype(int)
        detail_cols = ["caption", "likes", "comments", "shares", "reactions"]
        detail_df = df_fb[detail_cols].copy()
        detail_df = detail_df.rename(columns={
            "caption": "Nội dung",
            "likes": "❤️ Likes",
            "comments": "💬 Comments",
            "shares": "🔁 Shares",
            "reactions": "👍 Reactions"
        })
        st.markdown("<b>Chi tiết từng bài viết:</b>", unsafe_allow_html=True)
        st.dataframe(detail_df, use_container_width=True)
    # --- Thống kê tổng hợp và biểu đồ ---
    # Thống kê tổng hợp các chỉ số tương tác và vẽ biểu đồ
    all_posts = []
    if st.session_state.get("fb_posts"):
        all_posts += st.session_state.fb_posts
    if all_posts:
        df = pd.DataFrame(all_posts)
        for col in ["likes", "comments", "shares", "reactions"]:
            if col not in df.columns:
                df[col] = 0
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        # Thống kê tổng hợp
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
        # Biểu đồ
        df['created_time'] = pd.to_datetime(df['created_time'], errors='coerce')
        st.markdown("""
        <div style='padding-top:2em;'>
            <b>Biểu đồ thống kê tương tác theo thời gian:</b>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div style='padding-top:1em;'></div>", unsafe_allow_html=True)
        group_type = st.selectbox("Thống kê theo", ["Ngày", "Tuần", "Tháng"])
        if group_type == "Ngày":
            df['period'] = df['created_time'].dt.date
        elif group_type == "Tuần":
            df['period'] = df['created_time'].dt.to_period('W').apply(lambda r: r.start_time.date())
        else:
            df['period'] = df['created_time'].dt.to_period('M').astype(str)
        chart_type = st.selectbox("Chọn loại biểu đồ", ["Line", "Bar", "Area"])
        agg_df = df.groupby('period')[['likes', 'comments', 'shares', 'reactions']].sum().reset_index()
        fig, ax = plt.subplots(figsize=(8,4))
        if chart_type == "Line":
            sns.lineplot(data=agg_df, x='period', y='likes', label='Likes', marker='o', ax=ax)
            sns.lineplot(data=agg_df, x='period', y='comments', label='Comments', marker='o', ax=ax)
            sns.lineplot(data=agg_df, x='period', y='shares', label='Shares', marker='o', ax=ax)
            sns.lineplot(data=agg_df, x='period', y='reactions', label='Reactions', marker='o', ax=ax)
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
    else:
        st.info("Chưa có dữ liệu bài viết.")

#Tab 2,3,4 là lấy từ fb hết, ig hiện tại chưa làm đượcđược
# ====== Xử lý tab2: Dự báo hiệu quả ======
# Chức năng: Dự báo hiệu quả bài viết mới dựa trên caption, thời gian, dữ liệu lịch sử, AI phân tích.
# - Nhập caption, chọn nền tảng, thời gian đăng.
# - Nếu chưa có dữ liệu lịch sử, tự động lấy từ Facebook.
# - Gửi prompt cho AI, nhận về dự báo hiệu quả, ước lượng số liệu, giải thích lý do, gợi ý cải thiện.
# - Hiển thị kết quả đẹp, chia rõ các mục: mức độ hiệu quả, ước lượng, lý do, gợi ý.
with tab2:
    st.header("🔮 Dự báo hiệu quả bài viết")
    # --- Nhập caption, chọn nền tảng, thời gian đăng ---
    caption_forecast = st.text_area("✍️ Nhập caption dự kiến")
    platform_forecast = st.selectbox("📱 Nền tảng đăng", ["Facebook", "Instagram", "Threads"], key="forecast_platform")
    date_forecast = st.date_input("📅 Ngày dự kiến đăng", datetime.today(), key="forecast_date")
    time_forecast = st.time_input("⏰ Giờ dự kiến đăng", datetime.now().time(), key="forecast_time")
    post_time_forecast = datetime.combine(date_forecast, time_forecast)
    df = pd.DataFrame(st.session_state.posts)
    for col in ["likes", "comments", "shares", "reach", "reactions"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    if "time" not in df.columns:
        df["time"] = "unknown"
    # --- Phân tích & Dự báo khi bấm nút ---
    if st.button("🔍 Phân tích & Dự báo", disabled=(not caption_forecast.strip())):
        with st.spinner("Đang phân tích & dự báo bằng AI..."):
            # Nếu không có dữ liệu lịch sử thì tự động lấy từ Facebook
            if df.empty:
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
                def fetch_post_stats(post_id, access_token):
                    url = f"https://graph.facebook.com/v19.0/{post_id}"
                    params = {
                        "fields": "message,likes.summary(true),comments.summary(true),shares,reactions.summary(true)",
                        "access_token": access_token
                    }
                    resp = requests.get(url, params=params)
                    return resp.json()
                fb_posts = fetch_facebook_posts(FB_PAGE_ID, FB_PAGE_TOKEN, limit=20)
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
                st.session_state.posts = new_posts
                df = pd.DataFrame(st.session_state.posts)
                for col in ["likes", "comments", "shares", "reach", "reactions"]:
                    if col not in df.columns:
                        df[col] = 0
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
                if "time" not in df.columns:
                    df["time"] = "unknown"
            if df.empty:
                st.warning("⚠️ Chưa có dữ liệu lịch sử để dự báo. Hãy nhập hiệu quả các bài viết thực ở tab 'Hiệu quả'.")
            else:
                # Gửi prompt cho AI, nhận về dự báo hiệu quả, ước lượng số liệu, giải thích lý do, gợi ý cải thiện
                time_stats = df.groupby(df['time'])[["likes", "comments", "shares", "reach", "reactions"]].mean().to_dict() if not df.empty else {}
                prompt = f"""
Bạn là chuyên gia digital marketing.
Dựa trên dữ liệu lịch sử các bài đăng và nội dung sau, hãy dự đoán hiệu quả bài viết.

- Nền tảng: {platform_forecast}
- Thời gian đăng: {post_time_forecast.strftime('%H:%M %d/%m/%Y')}
- Nội dung:
{caption_forecast}

- Thống kê hiệu quả trung bình các bài đăng cũ: {time_stats}

Trả lời:
1. 🎯 Mức độ hiệu quả dự kiến (cao / trung bình / thấp)
2. 📊 Ước lượng lượt tiếp cận, thả cảm xúc, tương tác (likes), bình luận, chia sẻ
3. 🧠 Giải thích ngắn gọn lý do
4. 💡 Gợi ý cải thiện nội dung (nếu có)
                """
                try:
                    response = client.chat.completions.create(
                        model="openai/gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.9
                    )
                    result = response.choices[0].message.content.strip()

                    # Tách các phần dự báo (do ban đầu viết thành 1 đoạn văn khó nhìn, nên chia ra cho đẹp)
                    lines = result.split('\n')
                    summary = ""
                    estimate = []
                    reason = ""
                    suggest = ""
                    estimate_started = False
                    for idx, line in enumerate(lines):
                        line_strip = line.strip()
                        if line_strip.startswith("1."):
                            summary = line_strip.replace("1.", "").strip()
                        elif line_strip.startswith("2."):
                            after_2 = line_strip[2:].strip(': .-')
                            if after_2:
                                estimate.append(after_2)
                            estimate_started = True
                        elif line_strip.startswith("3."):
                            reason = line_strip.replace("3.", "").strip()
                            estimate_started = False
                        elif line_strip.startswith("4."):
                            suggest = line_strip.replace("4.", "").strip()
                            estimate_started = False
                        elif line_strip.startswith("-"):
                            estimate.append(line_strip.replace("-", "").strip())
                            estimate_started = True
                        elif estimate_started and line_strip and not line_strip.startswith("1.") and not line_strip.startswith("3.") and not line_strip.startswith("4."):
                            estimate.append(line_strip)
                        else:
                            estimate_started = False
                    if not estimate:
                        for line in lines:
                            if 'Ước lượng' in line:
                                content = line.split(':',1)[-1].strip()
                                if content:
                                    estimate.append(content)
                                break
                    estimate = [e for e in estimate if e.strip().lower() not in ["ước lượng", "ước lượng:"]]
                    def fix_number_range(text):
                        return re.sub(r'(\d+)\s+(\d+)', r'\1 - \2', text)
                    estimate = [fix_number_range(e) for e in estimate]
                    st.markdown(f"""
<div style='padding:1em;border-radius:8px;background:#f6f6fa;margin-bottom:1em;'>
    <span style='font-size:1.2em;'>🎯 <b>Mức độ hiệu quả dự kiến:</b> <span style='color:#1976d2'>{summary}</span></span>
</div>
<div style='padding:1em;border-radius:8px;background:#e3f2fd;margin-bottom:1em;'>
    <span style='font-size:1.1em;'><b>📊 Ước lượng:</b></span>
    <ul>
        {''.join([f'<li style=\"margin-bottom:0.3em;\">{e}</li>' for e in estimate])}
    </ul>
</div>
<div style='padding:1em;border-radius:8px;background:#fffde7;margin-bottom:1em;'>
    <span style='font-size:1.1em;'><b>🧠 Lý do:</b></span>
    <blockquote style='margin:0 0 0 1em;color:#666;'>{reason}</blockquote>
</div>
<div style='padding:1em;border-radius:8px;background:#e8f5e9;'>
    <span style='font-size:1.1em;'><b>💡 Gợi ý cải thiện:</b></span>
    <blockquote style='margin:0 0 0 1em;color:#388e3c;'>{suggest}</blockquote>
</div>
""", unsafe_allow_html=True)
                except OpenAIError as e:
                    st.error(f"⚠️ Không gọi được GPT: {e}")

# ====== Xử lý tab4: Gợi ý chiến lược ======
# Chức năng: Gợi ý cải thiện nội dung, thời gian, nền tảng dựa trên dữ liệu thực tế, AI sinh gợi ý.
# - Lấy dữ liệu Facebook nếu chưa có.
# - Gửi bảng dữ liệu hiệu quả các bài viết cho AI, yêu cầu so sánh với kỳ vọng, gợi ý 3 chiến lược cải thiện.
# - Hiển thị gợi ý định dạng đẹp, có icon, phân mục rõ ràng.
with tab4:
    st.header("🎯 Gợi ý chiến lược cải thiện")
    # --- Lấy dữ liệu Facebook nếu cần (nếu dùng tab 2 r thì k cần lấy dữ liệu lại nữa, nếu reload lại mà bấm tab 4 luôn thì cần lấy lại dữ liệu) ---
    posts_data = st.session_state.get("fb_posts", [])
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
    def fetch_post_stats(post_id, access_token):
        url = f"https://graph.facebook.com/v19.0/{post_id}"
        params = {
            "fields": "message,likes.summary(true),comments.summary(true),shares,reactions.summary(true)",
            "access_token": access_token
        }
        resp = requests.get(url, params=params)
        return resp.json()
    expected_cols = ['platform','caption','likes','comments','shares','reach','reactions']
    def beautify_ai_output(content):
        import re
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
    if st.button("🧠 Gợi ý từ AI"):
        if not st.session_state.get("fb_posts"):
            with st.spinner("Đang lấy dữ liệu Facebook..."):
                fb_posts = fetch_facebook_posts(FB_PAGE_ID, FB_PAGE_TOKEN, limit=20)
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
        posts_data = st.session_state.get("fb_posts", [])
        if posts_data:
            df = pd.DataFrame(posts_data)
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = 0
            prompt = f"""Dưới đây là dữ liệu hiệu quả các bài viết:\n\n{df[expected_cols].to_string(index=False)}\n\nHãy:\n- So sánh hiệu quả thực tế với kỳ vọng thông thường\n- Gợi ý 3 chiến lược cải thiện nội dung, thời gian hoặc nền tảng phù hợp hơn\n- Ưu tiên đề xuất hành động cụ thể\n"""
            with st.spinner("Đang phân tích và sinh gợi ý từ AI..."):
                try:
                    response = client.chat.completions.create(
                        model="openai/gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7
                    )
                    content = response.choices[0].message.content.strip().replace(chr(10),'<br>')
                    st.markdown(f"""
<div style='background:#f6f8fc;padding:1.5em 1.2em 1.2em 1.2em;border-radius:12px;margin-top:1em;'>
    <div style='font-size:1.15em;margin-bottom:1em;color:#1976d2;'><b>✨ Gợi ý từ AI:</b></div>
    <div style='font-size:1.08em;line-height:1.7;color:#222;'>
        {beautify_ai_output(content)}
    </div>
</div>
""", unsafe_allow_html=True)
                except OpenAIError as e:
                    st.error(f"⚠️ Lỗi AI: {e}")
        else:
            st.info("Chưa có dữ liệu bài viết Facebook để phân tích.")

# ====== Xử lý tab5: Quản lý bài chờ duyệt ======
# Chức năng: Quản lý, duyệt/xóa các bài viết chờ duyệt, thao tác với file posts_data.json.
# - Đọc file posts_data.json để lấy danh sách bài chờ duyệt.
# - Hiển thị danh sách, cho phép duyệt/xóa từng bài.
# - Khi duyệt: ghi vào file scheduled_posts.csv, xóa khỏi danh sách chờ duyệt.
# - Khi xóa: xóa khỏi danh sách, lưu lại file.
with tab5:
    st.header("📥 Bài chờ duyệt")
    # --- Đọc file posts_data.json để lấy danh sách bài chờ duyệt ---
    with st.spinner("Đang tải dữ liệu ..."):
        posts = load_posts()  # Luôn đọc file mới nhất
        if posts:
            df = pd.DataFrame(posts)
        else:
            df = pd.DataFrame([])
    # --- Hiển thị danh sách bài chờ duyệt ---
    if not df.empty:
        st.markdown("<b>Danh sách bài viết chờ duyệt:</b>", unsafe_allow_html=True)
        for idx in range(len(df), 0, -1):  # Duyệt từ cuối lên đầu
            row = df.iloc[idx-1]
            with st.expander(f"{row['platform']} | {row['caption'][:30]}..."):
                st.write(row['caption'])
                # Nếu có link ảnh, chỉ hiển thị link dạng clickable
                if row.get('image'):
                    st.markdown(f'<a href="{row["image"]}" target="_blank">🔗 Ảnh đính kèm</a>', unsafe_allow_html=True)
                cols = st.columns([2,2,2])
                with cols[0]:
                    # Duyệt và đăng ngay bài viết
                    if st.button(f"✅ Duyệt và đăng ngay #{idx}"):
                        with st.spinner("Đang xử lý..."):
                            now = datetime.now()
                            if row['platform'].lower() == "instagram":
                                token = IG_TOKEN
                                page_id = IG_ID
                            else:
                                token = FB_PAGE_TOKEN
                                page_id = FB_PAGE_ID
                            gc = get_gsheet_client()
                            sh = gc.open_by_key(SPREADSHEET_ID)
                            worksheet = sh.worksheet(SHEET_NAME)
                            ensure_sheet_header(worksheet, HEADER)
                            worksheet.append_row([
                                row['product'], "", row['platform'], now.strftime("%H:%M"),
                                token, page_id, "once", now.strftime("%Y-%m-%d"),
                                row['caption'], row.get('image', "")
                            ])
                            st.session_state.posts.pop(idx-1)
                            save_posts(st.session_state.posts)
                            st.rerun()
                with cols[2]:
                    # Từ chối & Hủy bỏ bài viết
                    if st.button(f"❌ Từ chối & Hủy bỏ #{idx}"):
                        with st.spinner("Đang xóa bài viết..."):
                            st.session_state.posts.pop(idx-1)
                            save_posts(st.session_state.posts)
                            st.rerun()
        st.markdown("<b>Dữ liệu bài chờ duyệt:</b>", unsafe_allow_html=True)
        st.dataframe(df)
    else:
        st.info("Chưa có bài viết nào chờ duyệt.")
