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

# Gán access token & page ID trực tiếp
FB_PAGE_TOKEN = "EAASMk7sVKQ8BO8q9kUhe73q0pFsRhyedqzksZBgFkQfdDtWHCG3kDDHVaXOfLeZBKaYP6ss102fJ3WModXczUyWg8ZCbajYpfkW1P8pLoACn45rc9ZCzZAoR7SWqXyXlaiZCLm5NIZCXOB0JO4Bb6vNNWdaKquabc4STA1uV3MN7sVz57X7FYMVvGfyok67x9pAZBpOLtLMy1NtkZCwFmbFzNeo4pbdLO"
FB_PAGE_ID = "112233445566778"

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

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 Tạo nội dung", "📊 Hiệu quả", "🎯 Gợi ý chiến lược", "🔮 Dự báo", "📥 Bài chờ duyệt"
])

with tab1:
    st.header("📝 Tạo nội dung bài đăng")
    product_name = st.text_input("Tên sản phẩm")
    keywords = st.text_input("Từ khóa", "gốm, thủ công, mộc mạc, decor")
    platform = st.selectbox("Nền tảng", ["Facebook", "Instagram", "Threads"])

    mode = st.radio("Chế độ đăng", [
        "📅 Tự động đúng giờ",
        "🤖 Tự động đăng đa dạng mỗi ngày",
        "👀 Chờ duyệt thủ công"])

    if mode == "📅 Tự động đúng giờ":
        post_date = st.date_input("📅 Ngày đăng", datetime.today(), key="post_date_once")
        post_time = st.time_input("⏰ Giờ đăng", datetime.now().time(), key="post_time_once")

    elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
        start_date = st.date_input("📅 Ngày bắt đầu", datetime.today(), key="start_date_loop")
        end_date = st.date_input("📅 Ngày kết thúc", datetime.today() + timedelta(days=3), key="end_date_loop")
        post_time = st.time_input("⏰ Giờ đăng mỗi ngày", datetime.now().time(), key="post_time_loop")

    if 'posts' not in st.session_state:
        st.session_state.posts = []

    def get_next_image(product_name):
        df = pd.read_csv("image_map.csv")
        matches = df[df["product_name"] == product_name]
        if matches.empty:
            return ""
        used = st.session_state.get("used_images", {})
        i = used.get(product_name, 0) % len(matches)
        used[product_name] = i + 1
        st.session_state["used_images"] = used
        return matches.iloc[i]["image_path"]

    if st.button("✨ Xử lý bài đăng"):
        if not product_name or not keywords:
            st.warning("⚠️ Vui lòng nhập đủ thông tin.")

        elif mode == "📅 Tự động đúng giờ":
            caption = generate_caption(product_name, keywords, platform)
            image_path = get_next_image(product_name)
            post_datetime = datetime.combine(post_date, post_time)
            with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    product_name,
                    keywords,
                    platform,
                    post_time.strftime("%H:%M"),
                    FB_PAGE_TOKEN,
                    FB_PAGE_ID,
                    "once",
                    post_datetime.strftime("%Y-%m-%d"),
                    caption.replace("\n", " "),
                    image_path
                ])
            st.text_area("📋 Nội dung đề xuất", caption, height=150)
            st.success(f"📅 Đã lên lịch đăng vào {post_datetime.strftime('%d/%m/%Y %H:%M')}")

        elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
            current_day = start_date
            while current_day <= end_date:
                auto_caption = generate_caption(product_name, keywords, platform)
                image_path = get_next_image(product_name)
                with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        product_name,
                        keywords,
                        platform,
                        post_time.strftime("%H:%M"),
                        FB_PAGE_TOKEN,
                        FB_PAGE_ID,
                        "daily",
                        current_day.strftime("%Y-%m-%d"),
                        auto_caption.replace("\n", " "),
                        image_path
                    ])
                current_day += timedelta(days=1)
            st.success(f"🤖 Đã lên lịch đăng từ {start_date} đến {end_date} lúc {post_time.strftime('%H:%M')}")

        else:
            caption = generate_caption(product_name, keywords, platform)
            st.text_area("📋 Nội dung đề xuất", caption, height=150)
            st.session_state.posts.append({
                "id": str(uuid.uuid4())[:8],
                "product": product_name,
                "platform": platform,
                "caption": caption,
                "time": "chờ duyệt",
                "likes": 0, "comments": 0, "shares": 0, "reach": 0
            })
            st.success("✅ Đã lưu bài viết để duyệt thủ công.")
with tab2:
    st.header("📊 Hiệu quả bài viết")
    if st.session_state.posts:
        df = pd.DataFrame(st.session_state.posts)
        for i, row in df.iterrows():
            with st.expander(f"{row['platform']} | {row['caption'][:30]}..."):
                df.at[i, 'likes'] = st.number_input(f"❤️ Likes #{i}", value=int(row['likes']), key=f"likes_{i}")
                df.at[i, 'comments'] = st.number_input(f"💬 Comments #{i}", value=int(row['comments']), key=f"comments_{i}")
                df.at[i, 'shares'] = st.number_input(f"🔁 Shares #{i}", value=int(row['shares']), key=f"shares_{i}")
                df.at[i, 'reach'] = st.number_input(f"📣 Reach #{i}", value=int(row['reach']), key=f"reach_{i}")
        st.metric("Tổng Reach", df["reach"].sum())
        st.metric("Tổng Likes", df["likes"].sum())
        st.metric("Tổng Comments", df["comments"].sum())
        st.metric("Tổng Shares", df["shares"].sum())

        fig, ax = plt.subplots()
        df.groupby("platform")[["likes", "comments", "shares"]].sum().plot(kind="bar", ax=ax)
        st.pyplot(fig)
    else:
        st.info("Chưa có dữ liệu bài viết.")

with tab3:
    st.header("🎯 Gợi ý chiến lược")
    if st.session_state.posts:
        df = pd.DataFrame(st.session_state.posts)
        prompt = f"""Dưới đây là dữ liệu hiệu quả bài viết:
{df[['platform','caption','likes','comments','shares','reach']].to_string(index=False)}

Hãy đánh giá hiệu quả nội dung và đề xuất 3 cách cải thiện."""
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
        st.info("Chưa có dữ liệu để phân tích.")

with tab4:
    st.header("🔮 Dự báo hiệu quả bài viết")
    caption_forecast = st.text_area("✍️ Nhập caption dự kiến", "")
    platform_forecast = st.selectbox("📱 Nền tảng đăng", ["Facebook", "Instagram", "Threads"], key="forecast_platform")
    date_forecast = st.date_input("📅 Ngày dự kiến đăng", datetime.today(), key="forecast_date")
    time_forecast = st.time_input("⏰ Giờ dự kiến đăng", datetime.now().time(), key="forecast_time")
    post_time_forecast = datetime.combine(date_forecast, time_forecast)

if st.button("🔍 Phân tích & Dự báo"):
    prompt = f"""
Bạn là một chuyên gia digital marketing, có kinh nghiệm phân tích nội dung mạng xã hội.

Hãy dự đoán hiệu quả của bài viết dưới đây trên nền tảng {platform_forecast} nếu được đăng vào lúc {post_time_forecast.strftime("%H:%M %d/%m/%Y")}.

Nội dung:
\"\"\"
{caption_forecast}
\"\"\"

Hãy trả lời các phần sau:
1. 🎯 Dự đoán hiệu quả (cao / trung bình / thấp)
2. 📊 Ước lượng số lượt tiếp cận (reach), tương tác (likes), bình luận (comments), chia sẻ (shares)
3. 🧠 Giải thích ngắn gọn lý do
4. 💡 Gợi ý cách viết lại nếu cần
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



with tab5:
    st.header("📥 Bài chờ duyệt")
    if st.session_state.posts:
        df = pd.DataFrame(st.session_state.posts)
        st.dataframe(df)
    else:
        st.info("Chưa có bài viết nào chờ duyệt.")
