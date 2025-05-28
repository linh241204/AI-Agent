import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import uuid
import csv
import requests
from openai import OpenAI, OpenAIError

# Tải biến môi trường
load_dotenv()

# Tạo OpenAI client từ OpenRouter
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# Khởi tạo dữ liệu nếu chưa có
if "posts" not in st.session_state:
    st.session_state.posts = []

# Hàm sinh caption bằng GPT
def generate_caption(product_name, keywords, platform):
    prompt = f"""
Bạn là chuyên gia nội dung sáng tạo cho thương hiệu gốm thủ công cao cấp.

Hãy viết một **bài viết marketing dài khoảng 100–150 từ** phù hợp đăng trên {platform}, để giới thiệu sản phẩm **{product_name}**, sử dụng tinh tế các từ khóa: {keywords}.

Yêu cầu:
- Giọng văn mộc mạc, sâu sắc, truyền cảm hứng
- Lồng ghép cảm xúc, triết lý sống chậm, yêu nét đẹp truyền thống
- Không quá bán hàng. Tập trung gợi cảm giác, không gian, cảm xúc người dùng
- Có thể mở đầu bằng một hình ảnh hoặc cảm nhận đời thường
- Kết bài nhẹ nhàng, có thể đặt câu hỏi gợi mở
- Gắn hashtag cuối bài. Không liệt kê hashtag quá dài

Viết 1 bài duy nhất.
"""
    try:
        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.95
        )
        return response.choices[0].message.content.strip()
    except OpenAIError as e:
        return f"⚠️ Không gọi được GPT: {e}"

# Tabs chính
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 Tạo nội dung", "📊 Hiệu quả", "🎯 Gợi ý chiến lược", "🔮 Dự báo", "📥 Bài chờ duyệt"
])

with tab1:
    st.header("📝 Tạo nội dung bài đăng")
    product_name = st.text_input("Tên sản phẩm")
    keywords = st.text_input("Từ khóa", "gốm, thủ công, mộc mạc, decor")
    platform = st.selectbox("Nền tảng", ["Facebook", "Instagram", "Threads"])
    date = st.date_input("📅 Ngày đăng", datetime.today())
    time = st.time_input("⏰ Giờ đăng", datetime.now().time())
    post_time = datetime.combine(date, time)

    mode = st.radio("Chế độ đăng", ["📅 Tự động đúng giờ", "👀 Chờ duyệt thủ công"])
    repeat_flag = "daily" if st.checkbox("🔁 Đăng lặp lại hằng ngày") else "once"

    if st.button("✨ Xử lý bài đăng"):
        if not product_name or not keywords:
            st.warning("⚠️ Vui lòng nhập đủ thông tin.")
        elif mode == "📅 Tự động đúng giờ":
            # Ghi vào file CSV để scheduler xử lý
            with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    product_name,
                    keywords,
                    platform,
                    post_time.strftime("%H:%M"),
                    os.getenv("FB_PAGE_TOKEN"),
                    os.getenv("FB_PAGE_ID"),
                    repeat_flag
                ])
            st.success("📅 Đã lưu để tự động đăng mỗi ngày!")
        else:
            # Sinh nội dung ngay và lưu trong session
            caption = generate_caption(product_name, keywords, platform)
            st.text_area("📋 Nội dung đề xuất", caption, height=150)
            st.session_state.posts.append({
                "id": str(uuid.uuid4())[:8],
                "product": product_name,
                "platform": platform,
                "caption": caption,
                "time": post_time.strftime("%Y-%m-%d %H:%M"),
                "likes": 0, "comments": 0, "shares": 0, "reach": 0
            })
            st.success("✅ Đã lưu bài viết để bạn duyệt & đăng sau!")

    if st.session_state.posts:
        st.markdown("### 📑 Danh sách bài đăng chờ duyệt")
        st.dataframe(pd.DataFrame(st.session_state.posts))
    else:
        st.info("Chưa có bài viết nào.")


# (Các tab khác giữ nguyên)
# ...
