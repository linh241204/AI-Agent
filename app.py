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

cloudinary.config(
    cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
    api_key=st.secrets["CLOUDINARY_API_KEY"],
    api_secret=st.secrets["CLOUDINARY_API_SECRET"],
    secure=True
)

DATA_FILE = "posts_data.json"

def save_posts(posts, filename=DATA_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

def load_posts(filename=DATA_FILE):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ====== Khởi tạo session_state mặc định ======
def_states = {
    "posts": load_posts()  # Đọc từ file thay vì []
}
for key, val in def_states.items():
    if key not in st.session_state:
        st.session_state[key] = val

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

# ====== Hàm upload ảnh lên Google Drive và lấy link công khai ======
def upload_image_to_gdrive(image_bytes, filename):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    SERVICE_ACCOUNT_FILE = 'gdrive_service_account.json.json'  # Đặt file này vào cùng thư mục app.py
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
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

# ====== Hàm lấy danh sách ảnh từ thư mục Google Drive ======
def list_gdrive_images_recursive(service, folder_id):
    images = []
    # Lấy file ảnh trong thư mục hiện tại (lấy cả thumbnailLink)
    query_img = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
    results = service.files().list(q=query_img, fields="files(id, name, thumbnailLink)", pageSize=1000).execute()
    images.extend(results.get('files', []))
    # Lấy thư mục con
    query_folder = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    subfolders = service.files().list(q=query_folder, fields="files(id)", pageSize=100).execute().get('files', [])
    for sub in subfolders:
        images.extend(list_gdrive_images_recursive(service, sub['id']))
    return images

def list_gdrive_images(folder_id):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    SERVICE_ACCOUNT_FILE = 'gdrive_service_account.json.json'
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    return list_gdrive_images_recursive(service, folder_id)

FOLDER_ID = '1PsIQuARS3WUerCrMMeW5gQiuTztRErun'  # Thay bằng ID thư mục Google Drive của bạn

# ====== Hàm duyệt thư mục Google Drive dạng cây ======
def list_gdrive_tree(service, folder_id):
    # Lấy thư mục con
    query_folder = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    folders = service.files().list(q=query_folder, fields="files(id, name)", pageSize=100).execute().get('files', [])
    # Lấy file ảnh trong thư mục hiện tại
    query_img = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
    images = service.files().list(q=query_img, fields="files(id, name, thumbnailLink)", pageSize=1000).execute().get('files', [])
    return folders, images

def pick_gdrive_image(folder_id, path=None):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    SERVICE_ACCOUNT_FILE = 'gdrive_service_account.json.json'
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    if path is None:
        path = []
    folders, images = list_gdrive_tree(service, folder_id)
    # Breadcrumb
    st.write(' / '.join([f"{p['name']}" for p in path] + ["..."]))
    # Hiển thị thư mục con
    for f in folders:
        if st.button(f"📁 {f['name']}", key=f"folder_{f['id']}"):
            pick_gdrive_image(f['id'], path + [f])
            st.stop()
    # Hiển thị ảnh trong thư mục
    cols = st.columns(6)
    for idx, img in enumerate(images):
        with cols[idx % 6]:
            thumb = img.get("thumbnailLink")
            if thumb:
                st.image(thumb+"&sz=128", width=80)
            else:
                st.markdown(':frame_with_picture:')
            if st.button("Chọn", key=f"choose_{img['id']}"):
                st.session_state.selected_gdrive_image = img
            st.caption(img["name"])

# ====== Hàm đăng bài lên Instagram ======
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

# ====== Hàm upload ảnh lên Cloudinary ======
def upload_image_to_cloudinary(image_bytes, preset="ml_default"):
    upload_result = cloudinary.uploader.upload(
        image_bytes,
        upload_preset=preset,
        resource_type="image"
    )
    return upload_result.get("secure_url")

# ====== UI chính ======
st.title("🧠 Trợ lý nội dung Facebook & Instagram")

# ====== Tabs giao diện ======
tab1, tab3, tab2, tab4, tab5 = st.tabs([
    "📝 Tạo nội dung", "📊 Hiệu quả", "🔮 Dự báo", "🎯 Gợi ý chiến lược", "📥 Bài chờ duyệt"
])

with tab1:
    st.header("📝 Tạo nội dung bài đăng")

    # Nhập liệu từ người dùng
    product_name = st.text_input("Tên sản phẩm")
    keywords = st.text_input("Từ khóa", "gốm, thủ công, mộc mạc, decor")
    platform = st.selectbox("Nền tảng", ["Facebook", "Instagram"])
    mode = st.radio("Chế độ đăng", ["📅 Tự động đúng giờ", "🤖 Tự động đăng đa dạng mỗi ngày", "👀 Chờ duyệt thủ công"])

    # Tùy chọn thời gian
    if mode == "📅 Tự động đúng giờ":
        st.date_input("📅 Ngày đăng", value=date.today(), key="post_date_once")
        st.time_input("⏰ Giờ đăng", value=time(9, 0), key="post_time_once", step=timedelta(minutes=1))
        # Chọn ảnh từ máy tính (drag & drop + Browse files)
        uploaded_image = st.file_uploader("Chọn ảnh từ máy tính", type=["jpg", "jpeg", "png"], accept_multiple_files=False)
        if uploaded_image:
            img_bytes = uploaded_image.read()
            cloudinary_url = upload_image_to_cloudinary(img_bytes, "ml_default")
            if cloudinary_url:
                st.session_state.cloudinary_url = cloudinary_url
            else:
                st.error("Upload ảnh lên Cloudinary thất bại!")
    elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
        st.date_input("📅 Ngày bắt đầu", value=date.today(), key="start_date_loop")
        st.date_input("📅 Ngày kết thúc", value=date.today(), key="end_date_loop")
        st.time_input("⏰ Giờ đăng mỗi ngày", value=time(9, 0), key="post_time_loop", step=timedelta(minutes=1))
        # Không hiển thị chọn ảnh, chỉ đăng caption
    else:  # 👀 Chờ duyệt thủ công
        # Chọn ảnh từ máy tính (drag & drop + Browse files)
        uploaded_image = st.file_uploader("Chọn ảnh từ máy tính", type=["jpg", "jpeg", "png"], accept_multiple_files=False, key="manual_file_uploader")
        if uploaded_image:
            img_bytes = uploaded_image.read()
            try:
                gdrive_link = upload_image_to_gdrive(img_bytes, uploaded_image.name)
                st.session_state.gdrive_url_manual = gdrive_link
                # st.success(f"Ảnh đã upload lên Google Drive!")
                # Không hiển thị gì sau khi upload thành công
            except Exception as e:
                st.error(f"Tải ảnh lên không thành công: {e}")

    # Xử lý khi bấm nút
    if st.button("✨ Xử lý bài đăng"):
        with st.spinner("Đang xử lý bài đăng..."):
            if not product_name or not keywords:
                st.warning("⚠️ Vui lòng nhập đủ thông tin.")
            else:
                caption = generate_caption(product_name, keywords, platform)
                # Nếu caption là lỗi GPT thì không cho đăng/lưu
                if caption.startswith("⚠️") or "Không gọi được GPT" in caption:
                    st.error(caption)
                else:
                    if platform == "Instagram":
                        if not IG_TOKEN or not IG_ID:
                            st.error("Thiếu IG_TOKEN hoặc IG_ID trong file secrets. Vui lòng cấu hình lại.")
                        elif not uploaded_image:
                            st.error("Bạn cần chọn ảnh để đăng lên Instagram.")
                        else:
                            cloudinary_url = st.session_state.get("cloudinary_url", "")
                            if not cloudinary_url:
                                st.error("Không tìm thấy link ảnh Cloudinary. Hãy upload lại ảnh.")
                            else:
                                result = post_content_to_instagram(IG_ID, IG_TOKEN, cloudinary_url, caption)
                                if "error" in result:
                                    st.error(f"Lỗi đăng Instagram: {result['error']}")
                                else:
                                    st.success("Đã đăng bài lên Instagram thành công!")
                    elif mode == "📅 Tự động đúng giờ":
                        # Lấy ảnh từ upload (nếu có)
                        image_path = st.session_state.get("gdrive_url", "")
                        post_datetime = datetime.combine(st.session_state["post_date_once"], st.session_state["post_time_once"])
                        with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                            writer = csv.writer(f)
                            writer.writerow([
                                product_name, keywords, platform, st.session_state["post_time_once"].strftime("%H:%M"),
                                FB_PAGE_TOKEN, FB_PAGE_ID, "once", post_datetime.strftime("%Y-%m-%d"),
                                caption, image_path
                            ])
                        st.text_area("📋 Nội dung đề xuất", caption, height=150)
                        st.success(f"📅 Đã lên lịch đăng vào {post_datetime.strftime('%d/%m/%Y %H:%M')}")
                    elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
                        current_day = st.session_state["start_date_loop"]
                        while current_day <= st.session_state["end_date_loop"]:
                            auto_caption = generate_caption(product_name, keywords, platform)
                            if auto_caption.startswith("⚠️") or "Không gọi được GPT" in auto_caption:
                                st.error(auto_caption)
                                break
                            # image_path để trống, scheduler sẽ tự lấy ảnh từ Drive
                            with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                                writer = csv.writer(f)
                                writer.writerow([
                                    product_name, keywords, platform, st.session_state["post_time_loop"].strftime("%H:%M"),
                                    FB_PAGE_TOKEN, FB_PAGE_ID, "daily", current_day.strftime("%Y-%m-%d"),
                                    auto_caption, ""
                                ])
                            current_day += timedelta(days=1)
                        else:
                            st.success(f"🤖 Đã lên lịch đăng từ {st.session_state['start_date_loop']} đến {st.session_state['end_date_loop']}")
                    else:  # 👀 Chờ duyệt thủ công
                        # Lấy ảnh từ upload (nếu có)
                        image_path = st.session_state.get("gdrive_url_manual", "")
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
                        st.rerun()
                        st.success("✅ Đã lưu bài viết để duyệt thủ công.")


with tab3:
    st.header("📊 Hiệu quả bài viết thực")
    # --- Lấy dữ liệu Facebook ---
    if "fb_data_fetched" not in st.session_state:
        with st.spinner("Đang lấy dữ liệu ..."):
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
            st.session_state.fb_posts = new_posts
            st.session_state.fb_data_fetched = True
    # --- Hiển thị bảng chi tiết ---
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


with tab2:
    st.header("🔮 Dự báo hiệu quả bài viết")
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

                    # Tách các phần dự báo
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
                            # Nếu dòng này chứa luôn nội dung ước lượng thì lấy luôn
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
                            # Nếu đang ở block ước lượng mà không phải đầu mục mới
                            estimate.append(line_strip)
                        else:
                            estimate_started = False
                    # Nếu không có gạch đầu dòng và estimate vẫn rỗng, thử tìm dòng chứa 'Ước lượng:'
                    if not estimate:
                        for line in lines:
                            if 'Ước lượng' in line:
                                content = line.split(':',1)[-1].strip()
                                if content:
                                    estimate.append(content)
                                break
                    # Loại bỏ các dòng chỉ là tiêu đề "Ước lượng" hoặc "Ước lượng:"
                    estimate = [e for e in estimate if e.strip().lower() not in ["ước lượng", "ước lượng:"]]
                    # Sửa estimate: tự động chèn dấu '-' giữa các số liền nhau nếu thiếu
                    def fix_number_range(text):
                        # Tìm các trường hợp 2 số liền nhau chỉ cách nhau bởi dấu cách
                        return re.sub(r'(\d+)\s+(\d+)', r'\1 - \2', text)
                    estimate = [fix_number_range(e) for e in estimate]
                    # Hiển thị đẹp
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


with tab4:
    st.header("🎯 Gợi ý chiến lược cải thiện")
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
        # Nhận diện tiêu đề nhỏ (dòng kết thúc bằng dấu hai chấm hoặc in đậm)
        lines = content.split("<br>")
        html = []
        in_ul = False
        for line in lines:
            line_strip = line.strip()
            # Tiêu đề nhỏ: kết thúc bằng dấu hai chấm hoặc in đậm
            if re.match(r'^(<b>.*</b>|[A-ZÀ-Ỹa-zà-ỹ0-9 ,\-]+:)$', line_strip):
                if in_ul:
                    html.append('</ul>')
                    in_ul = False
                html.append(f'''<div style="background:#e3f2fd;padding:0.5em 1em;margin:1.1em 0 0.5em 0;border-radius:7px;font-weight:600;font-size:1.08em;color:#1976d2;display:flex;align-items:center;"><span style='font-size:1.2em;margin-right:0.5em;'>💡</span>{line_strip}</div>''')
            # Danh sách gạch đầu dòng
            elif re.match(r'^(\-|•|\d+\.)\s', line_strip):
                if not in_ul:
                    html.append('<ul style="margin-left:1.2em;margin-bottom:0.7em;">')
                    in_ul = True
                html.append(f'<li style="margin-bottom:0.3em;list-style:none;"><span style="color:#43a047;font-size:1.1em;margin-right:0.5em;">✔️</span>{line_strip[2:]}</li>')
            # Đoạn văn thường
            elif line_strip:
                if in_ul:
                    html.append('</ul>')
                    in_ul = False
                html.append(f'<div style="margin-bottom:1em;font-size:1.08em;color:#222;">{line_strip}</div>')
        if in_ul:
            html.append('</ul>')
        return ''.join(html)
    if st.button("🧠 Gợi ý từ AI"):
        # Khi bấm nút mới kiểm tra và lấy dữ liệu nếu cần
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


with tab5:
    st.header("📥 Bài chờ duyệt")
    # Thêm spinner loading khi lấy dữ liệu bài chờ duyệt
    with st.spinner("Đang tải dữ liệu ..."):
        posts = load_posts()  # Luôn đọc file mới nhất
        if posts:
            df = pd.DataFrame(posts)
        else:
            df = pd.DataFrame([])
    if not df.empty:
        st.markdown("<b>Danh sách bài viết chờ duyệt:</b>", unsafe_allow_html=True)
        for i, row in df.iterrows():
            with st.expander(f"{row['platform']} | {row['caption'][:30]}..."):
                st.write(row['caption'])
                # Nếu có link ảnh, chỉ hiển thị link dạng clickable
                if row.get('image'):
                    st.markdown(f'<a href="{row["image"]}" target="_blank">🔗 Ảnh đính kèm</a>', unsafe_allow_html=True)
                cols = st.columns([2,2,2])
                with cols[0]:
                    if st.button(f"✅ Duyệt và đăng ngay #{i}"):
                        with st.spinner("Đang xử lý..."):
                            now = datetime.now()
                            with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                                writer = csv.writer(f)
                                writer.writerow([
                                    row['product'], "", row['platform'], now.strftime("%H:%M"),
                                    FB_PAGE_TOKEN, FB_PAGE_ID, "once", now.strftime("%Y-%m-%d"),
                                    row['caption'], row.get('image', "")
                                ])
                            st.session_state.posts.pop(i)
                            save_posts(st.session_state.posts)
                            st.rerun()
                with cols[2]:
                    if st.button(f"❌ Từ chối & Hủy bỏ #{i}"):
                        with st.spinner("Đang xóa bài viết..."):
                            st.session_state.posts.pop(i)
                            save_posts(st.session_state.posts)
                            st.rerun()
        st.markdown("<b>Dữ liệu bài chờ duyệt:</b>", unsafe_allow_html=True)
        st.dataframe(df)
    else:
        st.info("Chưa có bài viết nào chờ duyệt.")
