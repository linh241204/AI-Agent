import streamlit as st
from openai import OpenAI
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import uuid

# Load API key từ biến môi trường
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Giả lập dữ liệu bài đăng nếu chưa có
if "posts" not in st.session_state:
    st.session_state.posts = []

# Hàm sinh nội dung bằng OpenAI GPT-4
def generate_caption(product_name, keywords, platform):
    prompt = f"""Bạn là chuyên gia marketing cho sản phẩm gốm thủ công.
Hãy viết caption hấp dẫn (không quá 50 từ) cho sản phẩm '{product_name}' với các từ khóa: {keywords}. Nền tảng: {platform}."""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Lỗi AI: {e}"

# Giao diện Streamlit: Tabs chính
tab1, tab2, tab3 = st.tabs(["📝 Tạo nội dung", "📊 Hiệu quả marketing", "🎯 Gợi ý chiến lược"])

# TAB 1: TẠO NỘI DUNG
with tab1:
    st.header("📝 Tạo nội dung bài đăng")
    product_name = st.text_input("Tên sản phẩm")
    keywords = st.text_input("Từ khóa (phân cách bằng dấu phẩy)", "gốm, decor, thủ công, mộc mạc")
    platform = st.selectbox("Nền tảng", ["Facebook", "Instagram", "Threads"])

    date = st.date_input("📅 Ngày đăng", datetime.today())
    time = st.time_input("⏰ Giờ đăng", datetime.now().time())
    post_time = datetime.combine(date, time)

    st.subheader("3️⃣ Tạo nội dung tự động")
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
                "likes": 0,
                "comments": 0,
                "shares": 0,
                "reach": 0
            })
            st.success("✅ Đã lưu bài viết!")
        else:
            st.warning("⚠️ Vui lòng nhập tên sản phẩm và từ khoá.")

    st.markdown("### 📑 Lịch bài đăng đã lên")
    if st.session_state.posts:
        st.dataframe(pd.DataFrame(st.session_state.posts))
    else:
        st.info("Chưa có bài đăng nào.")

# TAB 2: PHÂN TÍCH HIỆU QUẢ
with tab2:
    st.header("📊 Tổng hợp hiệu quả bài viết")
    if st.session_state.posts:
        df = pd.DataFrame(st.session_state.posts)

        st.markdown("### ✍️ Cập nhật số liệu tương tác")
        for i, row in df.iterrows():
            with st.expander(f"{row['platform']} | {row['caption'][:30]}..."):
                df.at[i, 'likes'] = st.number_input(f"❤️ Likes (#{i})", value=int(row['likes']), key=f"likes_{i}")
                df.at[i, 'comments'] = st.number_input(f"💬 Comments (#{i})", value=int(row['comments']), key=f"comments_{i}")
                df.at[i, 'shares'] = st.number_input(f"🔁 Shares (#{i})", value=int(row['shares']), key=f"shares_{i}")
                df.at[i, 'reach'] = st.number_input(f"📣 Reach (#{i})", value=int(row['reach']), key=f"reach_{i}")

        st.markdown("### 📈 Hiệu suất tổng thể")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Reach", df["reach"].sum())
        col2.metric("Likes", df["likes"].sum())
        col3.metric("Comments", df["comments"].sum())
        col4.metric("Shares", df["shares"].sum())

        st.markdown("### 📊 Biểu đồ tương tác theo nền tảng")
        fig, ax = plt.subplots()
        df.groupby("platform")[["likes", "comments", "shares"]].sum().plot(kind="bar", ax=ax)
        st.pyplot(fig)
    else:
        st.info("Chưa có dữ liệu bài đăng để phân tích.")

# TAB 3: GỢI Ý CHIẾN LƯỢC
with tab3:
    st.header("🎯 Gợi ý điều chỉnh chiến lược nội dung")
    if st.session_state.posts:
        df = pd.DataFrame(st.session_state.posts)
        analysis_prompt = f"""
Dưới đây là dữ liệu hiệu quả bài đăng marketing của một cửa hàng gốm:
{df[['platform', 'caption', 'likes', 'comments', 'shares', 'reach']].to_string(index=False)}

Hãy đánh giá tổng quan hiệu quả chiến lược nội dung hiện tại.
Đưa ra 3 đề xuất để cải thiện nội dung, giờ đăng, nền tảng hoặc cách tiếp cận khách hàng."""

        if st.button("🧠 Phân tích và Gợi ý từ AI"):
            try:
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": analysis_prompt}],
                    temperature=0.7
                )
                suggestions = response.choices[0].message.content.strip()
                st.success("🎯 Dưới đây là phân tích và gợi ý từ AI:")
                st.markdown(suggestions)
            except Exception as e:
                st.error(f"Lỗi khi gọi OpenAI: {e}")
    else:
        st.warning("⚠️ Vui lòng tạo bài viết và cập nhật số liệu trước.")
