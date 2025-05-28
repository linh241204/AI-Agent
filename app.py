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
    mode = st.radio("Chế độ đăng:", ["📤 Đăng ngay", "📅 Tự động đúng giờ", "👀 Chờ duyệt & đăng thủ công"])

    if st.button("✨ Sinh nội dung"):
        if product_name and keywords:
            caption = generate_caption(product_name, keywords, platform)
            st.text_area("📋 Nội dung đề xuất", caption, height=150)
            new_row = [caption, platform, post_time.strftime("%Y-%m-%d %H:%M"), os.getenv("FB_PAGE_TOKEN"), os.getenv("FB_PAGE_ID"), mode.split(" ")[1]]
            if mode == "📤 Đăng ngay":
                requests.post(f"https://graph.facebook.com/{new_row[4]}/feed", data={"message": new_row[0], "access_token": new_row[3]})
                st.success("✅ Đã đăng ngay")
            elif mode == "📅 Tự động đúng giờ":
                with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                    csv.writer(f).writerow(new_row)
                st.success("📅 Đã lưu để tự động đăng đúng giờ")
            else:
                with open("pending_posts.csv", "a", encoding="utf-8", newline="") as f:
                    csv.writer(f).writerow(new_row)
                st.success("👀 Đã lưu bài chờ duyệt")
        else:
            st.warning("⚠️ Vui lòng nhập đủ thông tin.")

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
"""
{caption_forecast}
"""

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
    if os.path.exists("pending_posts.csv"):
        df = pd.read_csv("pending_posts.csv")
        for i, row in df.iterrows():
            with st.expander(f"📝 {row['caption'][:30]}..."):
                st.markdown(f"**Nền tảng:** {row['platform']}")
                st.markdown(f"**Thời gian đăng:** {row['time']}")
                if st.button(f"📤 Đăng ngay #{i}"):
                    try:
                        res = requests.post(
                            f"https://graph.facebook.com/{row['page_id']}/feed",
                            data={"message": row['caption'], "access_token": row['token']}
                        )
                        if res.status_code == 200:
                            st.success("✅ Đã đăng ngay")
                            df = df.drop(i)
                            df.to_csv("pending_posts.csv", index=False)
                            st.experimental_rerun()
                        else:
                            st.error("❌ Lỗi khi đăng bài.")
                    except Exception as e:
                        st.error(f"❌ Lỗi: {e}")
                elif st.button(f"📅 Lên lịch tự động #{i}"):
                    with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                        csv.writer(f).writerow(row)
                    df = df.drop(i)
                    df.to_csv("pending_posts.csv", index=False)
                    st.success("📅 Đã chuyển sang tự động đăng")
                    st.experimental_rerun()
    else:
        st.info("Không có bài chờ duyệt.")
