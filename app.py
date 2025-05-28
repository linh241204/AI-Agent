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

# Ví dụ: post_to_facebook("Test caption", "images/my_image.jpg")


# Bạn có thể thay các lệnh os.getenv("FB_PAGE_TOKEN") bằng FB_PAGE_TOKEN ở các nơi dùng để đăng Facebook
# Ví dụ:
# os.getenv("FB_PAGE_TOKEN") => FB_PAGE_TOKEN
# os.getenv("FB_PAGE_ID") => FB_PAGE_ID

# Nhớ cập nhật cả phần scheduler nếu bạn muốn dùng access token này cho việc đăng tự động
