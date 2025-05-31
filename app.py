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

# ====== Khởi tạo session_state mặc định ======
def_states = {
    "post_date_once": date.today(),
    "post_time_once": time(9, 0),
    "start_date_loop": date.today(),
    "end_date_loop": date.today(),
    "post_time_loop": time(9, 0),
    "posts": []
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

# ====== UI chính ======
st.title("🧠 Trợ lý nội dung Facebook & Instagram")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 Tạo nội dung", "🔮 Dự báo", "📊 Hiệu quả", "🎯 Gợi ý chiến lược", "📥 Bài chờ duyệt"
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
        st.date_input("📅 Ngày đăng", value=st.session_state["post_date_once"], key="post_date_once")
        st.time_input("⏰ Giờ đăng", value=st.session_state["post_time_once"], key="post_time_once", step=timedelta(minutes=1))
        # Chọn ảnh từ máy tính (drag & drop + Browse files)
        uploaded_image = st.file_uploader("Chọn ảnh từ máy tính", type=["jpg", "jpeg", "png"], accept_multiple_files=False)
        if uploaded_image:
            img_bytes = uploaded_image.read()
            try:
                gdrive_link = upload_image_to_gdrive(img_bytes, uploaded_image.name)
                st.session_state.gdrive_url = gdrive_link
                # st.success(f"Ảnh đã upload lên Google Drive!")
                # Không hiển thị gì sau khi upload thành công
            except Exception as e:
                st.error(f"Tải ảnh lên không thành công: {e}")
    elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
        st.date_input("📅 Ngày bắt đầu", value=st.session_state["start_date_loop"], key="start_date_loop")
        st.date_input("📅 Ngày kết thúc", value=st.session_state["end_date_loop"], key="end_date_loop")
        st.time_input("⏰ Giờ đăng mỗi ngày", value=st.session_state["post_time_loop"], key="post_time_loop", step=timedelta(minutes=1))
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
        if not product_name or not keywords:
            st.warning("⚠️ Vui lòng nhập đủ thông tin.")
        else:
            caption = generate_caption(product_name, keywords, platform)
            if mode == "📅 Tự động đúng giờ":
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
                    # image_path để trống, scheduler sẽ tự lấy ảnh từ Drive
                    with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            product_name, keywords, platform, st.session_state["post_time_loop"].strftime("%H:%M"),
                            FB_PAGE_TOKEN, FB_PAGE_ID, "daily", current_day.strftime("%Y-%m-%d"),
                            auto_caption, ""
                        ])
                    current_day += timedelta(days=1)
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
                st.success("✅ Đã lưu bài viết để duyệt thủ công.")


with tab2:
    st.header("🔮 Dự báo hiệu quả bài viết")

    caption_forecast = st.text_area("✍️ Nhập caption dự kiến")
    platform_forecast = st.selectbox("📱 Nền tảng đăng", ["Facebook", "Instagram", "Threads"], key="forecast_platform")
    date_forecast = st.date_input("📅 Ngày dự kiến đăng", datetime.today(), key="forecast_date")
    time_forecast = st.time_input("⏰ Giờ dự kiến đăng", datetime.now().time(), key="forecast_time")
    post_time_forecast = datetime.combine(date_forecast, time_forecast)

    if st.button("🔍 Phân tích & Dự báo"):
        df = pd.DataFrame(st.session_state.posts)
        time_stats = df.groupby(df['time'])[['likes', 'comments', 'shares', 'reach', 'reactions']].mean().to_dict() if not df.empty else {}

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
            st.markdown(response.choices[0].message.content.strip())
        except OpenAIError as e:
            st.error(f"⚠️ Không gọi được GPT: {e}")




with tab3:
    st.header("📊 Hiệu quả bài viết thực")
    if st.session_state.posts:
        df = pd.DataFrame(st.session_state.posts)
        for i, row in df.iterrows():
            with st.expander(f"{row['platform']} | {row['caption'][:30]}..."):
                df.at[i, 'likes'] = st.number_input(f"❤️ Likes #{i}", value=int(row['likes']), key=f"likes_{i}")
                df.at[i, 'comments'] = st.number_input(f"💬 Comments #{i}", value=int(row['comments']), key=f"comments_{i}")
                df.at[i, 'shares'] = st.number_input(f"🔁 Shares #{i}", value=int(row['shares']), key=f"shares_{i}")
                df.at[i, 'reach'] = st.number_input(f"📣 Reach #{i}", value=int(row['reach']), key=f"reach_{i}")
                df.at[i, 'reactions'] = st.number_input(f"👍 Thả cảm xúc #{i}", value=int(row.get('reactions', 0)), key=f"reactions_{i}")

        st.metric("Tổng Reach", df["reach"].sum())
        st.metric("Tổng Likes", df["likes"].sum())
        st.metric("Tổng Comments", df["comments"].sum())
        st.metric("Tổng Shares", df["shares"].sum())
        st.metric("Tổng Reactions", df["reactions"].sum())

        fig, ax = plt.subplots()
        df.groupby("platform")[["likes", "comments", "shares", "reactions"]].sum().plot(kind="bar", ax=ax)
        st.pyplot(fig)
    else:
        st.info("Chưa có dữ liệu bài viết.")



with tab4:
    st.header("🎯 Gợi ý chiến lược cải thiện")
    if st.session_state.posts:
        df = pd.DataFrame(st.session_state.posts)

        expected_cols = ['platform','caption','likes','comments','shares','reach','reactions']
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0

        prompt = f"""Dưới đây là dữ liệu hiệu quả các bài viết:

{df[expected_cols].to_string(index=False)}

Hãy:
- So sánh hiệu quả thực tế với kỳ vọng thông thường
- Gợi ý 3 chiến lược cải thiện nội dung, thời gian hoặc nền tảng phù hợp hơn
- Ưu tiên đề xuất hành động cụ thể
"""  # <<< đừng quên dấu kết thúc chuỗi này!

        if st.button("🧠 Gợi ý từ AI"):
            try:
                response = client.chat.completions.create(
                    model="openai/gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                st.markdown(response.choices[0].message.content.strip())
            except OpenAIError as e:
                st.error(f"⚠️ Lỗi AI: {e}")
    else:
        st.info("Chưa có dữ liệu để phân tích chiến lược.")





with tab5:

  # 📥 Tab 5: Bài chờ duyệt — thêm nút duyệt và lên lịch đăng

    import csv
    from datetime import datetime, timedelta

with tab5:
    st.header("📥 Bài chờ duyệt")
    if st.session_state.posts:
        df = pd.DataFrame(st.session_state.posts)

        for i, row in df.iterrows():
            with st.expander(f"{row['platform']} | {row['caption'][:30]}..."):
                st.write(row['caption'])
                if st.button(f"✅ Duyệt và đăng ngay #{i}"):
                    now = datetime.now() # Lấy thời gian hiện tại để đăng ngay
                    with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            row['product'], "", row['platform'], now.strftime("%H:%M"),
                            FB_PAGE_TOKEN, FB_PAGE_ID, "once", now.strftime("%Y-%m-%d"),
                            row['caption'], ""
                        ])
                    st.success(f"📅 Đã duyệt và lên lịch đăng vào {now.strftime('%d/%m/%Y %H:%M')}")

        st.dataframe(df)
    else:
        st.info("Chưa có bài viết nào chờ duyệt.")
