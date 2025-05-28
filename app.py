import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import uuid
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
    prompt = f"""Bạn là chuyên gia marketing cho sản phẩm gốm thủ công.
Hãy viết caption hấp dẫn (không quá 50 từ) cho sản phẩm '{product_name}' với các từ khóa: {keywords}. Nền tảng: {platform}."""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except OpenAIError as e:
        return f"⚠️ Không gọi được GPT: {e}"

# Giao diện chính gồm 3 tab
tab1, tab2, tab3 = st.tabs(["📝 Tạo nội dung", "📊 Hiệu quả", "🎯 Gợi ý chiến lược"])

with tab1:
    st.header("📝 Tạo nội dung bài đăng")
    product_name = st.text_input("Tên sản phẩm")
    keywords = st.text_input("Từ khóa", "gốm, thủ công, mộc mạc, decor")
    platform = st.selectbox("Nền tảng", ["Facebook", "Instagram", "Threads"])
    date = st.date_input("📅 Ngày đăng", datetime.today())
    time = st.time_input("⏰ Giờ đăng", datetime.now().time())
    post_time = datetime.combine(date, time)

    if st.button("✨ Sinh nội dung"):
        if product_name and keywords:
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
            st.success("✅ Đã lưu bài viết!")
        else:
            st.warning("⚠️ Vui lòng nhập đủ thông tin.")

    if st.session_state.posts:
        st.markdown("### 📑 Danh sách bài đăng")
        st.dataframe(pd.DataFrame(st.session_state.posts))
    else:
        st.info("Chưa có bài viết nào.")

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
