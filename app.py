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

# Gán access token & page ID cho từng nền tảng
FB_PAGE_TOKEN = "EAASMk7sVKQ8BO8q9kUhe73q0pFsRhyedqzksZBgFkQfdDtWHCG3kDDHVaXOfLeZBKaYP6ss102fJ3WModXczUyWg8ZCbajYpfkW1P8pLoACn45rc9ZCzZAoR7SWqXyXlaiZCLm5NIZCXOB0JO4Bb6vNNWdaKquabc4STA1uV3MN7sVz57X7FYMVvGfyok67x9pAZBpOLtLMy1NtkZCwFmbFzNeo4pbdLO"
IG_PAGE_TOKEN = "EAASMk7sVKQ8BOwDkLv44vEWgt9rYe9Ao0PfOYp2KsChz5U2usOpKatb6caWPObxvbOsqYhNwZCVi14DflW0HQKxdN06XZAiwRmW0jrIDo9O0Dui9H0VyXqtQN1xM7tQ066QMbkHSvXP9f4PnoHXFGBjBuPQo23vsitm7doUDZCmSfs8klUseVzVqNskH4qiQ6jjEgsGcJAAr2GAFpWhlpc2qwZDZD"
THREADS_PAGE_TOKEN = IG_PAGE_TOKEN  # Giả định Threads chung với IG
FB_PAGE_ID = "1280466033649935"

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
- Ngắt đoạn rõ ràng (xuống dòng sau mỗi 1–2 câu)
- Lồng ghép cảm xúc, triết lý sống chậm, yêu nét đẹp truyền thống
- Dùng biểu tượng cảm xúc phù hợp (🌿✨🧘🏽‍♀️🏺❤️…)
- Giọng văn mộc mạc, truyền cảm hứng – không quá quảng cáo
- Kết bài nhẹ nhàng, có thể đặt câu hỏi
- Cuối bài **luôn có dòng hashtag**: #xuongbinhgom

Viết 1 bài duy nhất.
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



# Tabs
st.title("🧠 Trợ lý nội dung đa nền tảng")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 Tạo nội dung", "🔮 Dự báo", "📊 Hiệu quả", "🎯 Gợi ý chiến lược",  "📥 Bài chờ duyệt"
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
        st.date_input("📅 Ngày đăng", value=st.session_state["post_date_once"], key="post_date_once")
        st.time_input("⏰ Giờ đăng", value=st.session_state["post_time_once"], key="post_time_once")

    elif mode == "🤖 Tự động đăng đa dạng mỗi ngày":
        st.date_input("📅 Ngày bắt đầu", value=st.session_state["start_date_loop"], key="start_date_loop")
        st.date_input("📅 Ngày kết thúc", value=st.session_state["end_date_loop"], key="end_date_loop")
        st.time_input("⏰ Giờ đăng mỗi ngày", value=st.session_state["post_time_loop"], key="post_time_loop")

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
            post_datetime = datetime.combine(st.session_state["post_date_once"], st.session_state["post_time_once"])
            with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    product_name,
                    keywords,
                    platform,
                    st.session_state["post_time_once"].strftime("%H:%M"),
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
            current_day = st.session_state["start_date_loop"]
            while current_day <= st.session_state["end_date_loop"]:
                auto_caption = generate_caption(product_name, keywords, platform)
                image_path = get_next_image(product_name)
                with open("scheduled_posts.csv", "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        product_name,
                        keywords,
                        platform,
                        st.session_state["post_time_loop"].strftime("%H:%M"),
                        FB_PAGE_TOKEN,
                        FB_PAGE_ID,
                        "daily",
                        current_day.strftime("%Y-%m-%d"),
                        auto_caption.replace("\n", " "),
                        image_path
                    ])
                current_day += timedelta(days=1)
            st.success(f"🤖 Đã lên lịch đăng từ {st.session_state['start_date_loop']} đến {st.session_state['end_date_loop']} lúc {st.session_state['post_time_loop'].strftime('%H:%M')}")

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
        # Giả sử dự báo lưu trong df_forecast nếu bạn muốn triển khai tiếp sau này
        prompt = f"""Dưới đây là dữ liệu hiệu quả các bài viết:

{df[['platform','caption','likes','comments','shares','reach','reactions']].to_string(index=False)}

Hãy:
- So sánh hiệu quả thực tế với kỳ vọng thông thường
- Gợi ý 3 chiến lược cải thiện nội dung, thời gian hoặc nền tảng phù hợp hơn
- Ưu tiên đề xuất hành động cụ thể
"""
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
    st.header("📥 Bài chờ duyệt")
    if st.session_state.posts:
        df = pd.DataFrame(st.session_state.posts)
        st.dataframe(df)
    else:
        st.info("Chưa có bài viết nào chờ duyệt.")
