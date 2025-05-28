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

# Gán access token & page ID trực tiếp (nếu muốn hardcode)
FB_PAGE_TOKEN = "EAASMk7sVKQ8BO8q9kUhe73q0pFsRhyedqzksZBgFkQfdDtWHCG3kDDHVaXOfLeZBKaYP6ss102fJ3WModXczUyWg8ZCbajYpfkW1P8pLoACn45rc9ZCzZAoR7SWqXyXlaiZCLm5NIZCXOB0JO4Bb6vNNWdaKquabc4STA1uV3MN7sVz57X7FYMVvGfyok67x9pAZBpOLtLMy1NtkZCwFmbFzNeo4pbdLO"
FB_PAGE_ID = "112233445566778"  # <- thay bằng ID trang Facebook bạn quản lý

# Tạo OpenAI client từ OpenRouter
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

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

# Hàm đăng bài viết lên Facebook
def post_to_facebook(caption, image_path):
    url = f"https://graph.facebook.com/{FB_PAGE_ID}/photos"
    with open(image_path, "rb") as img:
        files = {"source": img}
        data = {
            "caption": caption,
            "access_token": FB_PAGE_TOKEN
        }
        response = requests.post(url, data=data, files=files)
        return response.json()

# Giao diện chọn chế độ đăng
mode = st.radio("Chế độ đăng", [
    "📅 Tự động đúng giờ",
    "🤖 Tự động đăng đa dạng mỗi ngày",
    "👀 Chờ duyệt thủ công"
])

# Giao diện theo chế độ
if mode == "📅 Tự động đúng giờ":
    post_date = st.date_input("📅 Ngày đăng", datetime.today(), key="post_date_once")
    post_time = st.time_input("⏰ Giờ đăng", datetime.now().time(), key="post_time_once")

elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
    start_date = st.date_input("📅 Ngày bắt đầu", datetime.today(), key="start_date_loop")
    end_date = st.date_input("📅 Ngày kết thúc", datetime.today() + timedelta(days=3), key="end_date_loop")
    post_time = st.time_input("⏰ Giờ đăng mỗi ngày", datetime.now().time(), key="post_time_loop")

else:  # 👀 Chờ duyệt thủ công
    post_date, post_time = None, None
# Tabs chính
st.set_page_config(layout="wide")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 Tạo nội dung", "📊 Hiệu quả", "🎯 Gợi ý chiến lược", "🔮 Dự báo", "📥 Bài chờ duyệt"
])

# Tab 2: Hiệu quả bài viết
with tab2:
    st.header("📊 Hiệu quả bài viết")
    if os.path.exists("metrics.csv"):
        df = pd.read_csv("metrics.csv")
        st.dataframe(df)
        st.metric("Tổng reach", df["reach"].sum())
        st.metric("Tổng likes", df["likes"].sum())
        st.metric("Tổng shares", df["shares"].sum())
        fig, ax = plt.subplots()
        df.groupby("platform")[["likes", "shares"]].sum().plot(kind="bar", ax=ax)
        st.pyplot(fig)
    else:
        st.info("Chưa có dữ liệu hiệu quả bài viết.")

# Tab 3: Gợi ý chiến lược
with tab3:
    st.header("🎯 Gợi ý chiến lược")
    if os.path.exists("metrics.csv"):
        df = pd.read_csv("metrics.csv")
        prompt = f"""Dưới đây là dữ liệu hiệu quả bài viết:
{df[['platform','caption','likes','shares','reach']].to_string(index=False)}

Hãy đánh giá và gợi ý cải thiện nội dung bài viết.
"""
        if st.button("🧠 Gợi ý từ AI"):
            try:
                res = client.chat.completions.create(
                    model="openai/gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8
                )
                st.markdown(res.choices[0].message.content.strip())
            except Exception as e:
                st.error(f"❌ Lỗi AI: {e}")
    else:
        st.info("Chưa có dữ liệu để phân tích.")

# Tab 4: Dự báo hiệu quả
with tab4:
    st.header("🔮 Dự báo hiệu quả bài viết")
    caption = st.text_area("📋 Nội dung bài viết")
    if st.button("📈 Dự báo"):
        if caption:
            prompt = f"""
Bạn là chuyên gia digital marketing. Dưới đây là nội dung bài viết:
"""
            prompt += caption + """

Dự báo hiệu quả và đưa ra lời khuyên cải thiện nếu cần.
"""
            try:
                res = client.chat.completions.create(
                    model="openai/gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.9
                )
                st.markdown(res.choices[0].message.content.strip())
            except Exception as e:
                st.error(f"❌ Lỗi khi gọi GPT: {e}")

# Tab 5: Bài chờ duyệt
with tab5:
    st.header("📥 Danh sách bài viết chờ duyệt")
    if os.path.exists("pending_posts.csv"):
        df = pd.read_csv("pending_posts.csv")
        st.dataframe(df)
    else:
        st.info("Không có bài viết nào đang chờ duyệt.")

