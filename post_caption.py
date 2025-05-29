import csv
import time
import requests
from datetime import datetime, timedelta # Import timedelta cho việc cập nhật ngày

CSV_FILE = "scheduled_posts.csv"

# ✅ GẮN SẴN PAGE ID & ACCESS TOKEN (nên lấy từ biến môi trường hoặc secrets nếu deploy)
DEFAULT_PAGE_ID = "2076435142631541"
DEFAULT_ACCESS_TOKEN = "EAAbHPY5s4I4BO4lcMP4spMukwjZCmNdt0twbIGVdHAqUY6Q4OYThmtoFbOqx2tCw3yyZB8fKEnbxQbIAiNc7hvvzO4mVZBLnCpIOHvjaRRvpx9DbQjSUSWtPexZC1j812CZCu5DF6OFZB1sHmVSivK8cb9TvxGFmlJMgKWsF0zAsS0zdNZCbenZCaOZBnt2hZCw5zF0HrK" # Token này có thể hết hạn, cần kiểm tra

def post_content_to_facebook(page_id, access_token, message, image_url=None):
    if image_url:
        url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
        data = {
            "message": message,
            "url": image_url, # Sử dụng 'url' nếu ảnh từ URL
            "access_token": access_token
        }
    else:
        url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
        data = {
            "message": message,
            "access_token": access_token
        }
    
    try:
        response = requests.post(url, data=data)
        response.raise_for_status() # Báo lỗi nếu status code là 4xx/5xx
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Lỗi khi gọi API Facebook: {e}")
        if response is not None:
            print(f"   Phản hồi lỗi từ Facebook: {response.text}")
        return {"error": str(e)}

print("🟢 Scheduler AI Agent đang chạy... (kiểm tra mỗi 60 giây)")

while True:
    now = datetime.now()
    updated_rows = []

    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except FileNotFoundError:
        print(f"ℹ️ File CSV '{CSV_FILE}' không tồn tại. Đang chờ bài đăng mới...")
        time.sleep(60)
        continue
    except Exception as e:
        print(f"❌ Không thể đọc file CSV: {e}")
        time.sleep(60)
        continue

    for i, row in enumerate(rows):
        if len(row) < 10:
            print(f"⚠️ Bỏ qua dòng {i+1} thiếu cột hoặc sai định dạng: {row}")
            updated_rows.append(row)
            continue

        try:
            # Giải nén các cột
            product, keywords, platform, time_str, token, page_id, mode, date_str, caption, image_path = row[:10]

            # Xử lý các giá trị
            scheduled_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            token = token.strip() if token.strip() else DEFAULT_ACCESS_TOKEN
            page_id = page_id.strip() if page_id.strip() else DEFAULT_PAGE_ID
            platform = platform.strip().lower()
            mode = mode.strip().lower()
            caption = caption.strip()
            image_path = image_path.strip() # Đảm bảo image_path cũng được làm sạch

            print(f"\n📄 [{product}] | Mode: {mode} | Lịch: {scheduled_time} | Hiện tại: {now}")

            # --- Logic xử lý chế độ đăng ---
            if platform == "facebook":
                if mode == "once":
                    if now >= scheduled_time:
                        print("🚀 Đang đăng bài (once)...")
                        result = post_content_to_facebook(page_id, token, caption, image_path)
                        if "error" not in result:
                            print(f"✅ Đã đăng bài 'once': {result}. Bài này sẽ được xóa.")
                            # Không thêm vào updated_rows để xóa khỏi CSV
                        else:
                            print(f"❌ Lỗi khi đăng bài 'once': {result}. Giữ lại để thử lại.")
                            updated_rows.append(row) # Giữ lại nếu lỗi để thử lại lần sau
                    else:
                        updated_rows.append(row) # Chưa đến giờ, giữ lại
                
                elif mode == "daily":
                    # Để xử lý đăng daily, cần cập nhật ngày đăng trong CSV
                    # nếu bài đã được đăng cho ngày hiện tại.
                    # Điều kiện: đã đến giờ của ngày hôm nay
                    if now.date() == scheduled_time.date() and now >= scheduled_time:
                        print("🚀 Đang đăng bài (daily) cho hôm nay...")
                        result = post_content_to_facebook(page_id, token, caption, image_path)
                        if "error" not in result:
                            print(f"✅ Đã đăng bài 'daily' cho {scheduled_time.date()}: {result}.")
                            # Cập nhật scheduled_time sang ngày mai và thêm vào updated_rows
                            next_scheduled_time = scheduled_time + timedelta(days=1)
                            row[7] = next_scheduled_time.strftime("%Y-%m-%d") # Cập nhật date_str
                            updated_rows.append(row)
                        else:
                            print(f"❌ Lỗi khi đăng bài 'daily': {result}. Giữ lại để thử lại.")
                            updated_rows.append(row) # Giữ lại nếu lỗi để thử lại lần sau
                    elif now.date() > scheduled_time.date():
                         # Nếu đã quá ngày dự kiến đăng (ví dụ scheduler bị dừng)
                         # Cập nhật ngày dự kiến đăng đến hôm nay hoặc ngày mai để tiếp tục
                        print(f"ℹ️ Bài đăng 'daily' đã quá hạn ({scheduled_time.date()}). Cập nhật ngày.")
                        
                        # Điều chỉnh scheduled_time để nó là ngày hôm nay HOẶC ngày mai
                        # Đảm bảo scheduled_time là thời gian trong tương lai gần nhất
                        temp_scheduled_time = scheduled_time
                        while temp_scheduled_time.date() < now.date():
                            temp_scheduled_time += timedelta(days=1)
                        
                        # Nếu ngày đã là hôm nay nhưng giờ chưa tới, giữ nguyên.
                        # Nếu ngày đã là hôm nay và giờ đã qua, chuyển sang ngày mai.
                        if temp_scheduled_time.date() == now.date() and now >= temp_scheduled_time:
                            temp_scheduled_time += timedelta(days=1)

                        row[7] = temp_scheduled_time.strftime("%Y-%m-%d")
                        updated_rows.append(row)

                    else: # Chưa đến ngày hoặc giờ của bài daily
                        updated_rows.append(row) # Giữ lại
                
                elif mode == "manual":
                    # Bài manual chỉ được xử lý thủ công từ Streamlit App, không phải từ scheduler này
                    updated_rows.append(row)
                    print(f"ℹ️ Bài đăng 'manual' được bỏ qua bởi scheduler.")
                
                else:
                    print(f"⚠️ Chế độ '{mode}' không hợp lệ. Giữ lại dòng.")
                    updated_rows.append(row)
            else: # Không phải platform Facebook hoặc Instagram
                updated_rows.append(row) # Giữ lại

        except ValueError as ve:
            print(f"❌ Lỗi định dạng ngày/giờ trong dòng {i+1}: {row}. Lỗi: {ve}. Bỏ qua dòng này.")
            updated_rows.append(row)
        except Exception as e:
            print(f"❌ Lỗi không xác định khi xử lý dòng {i+1}: {row}. Lỗi: {e}")
            updated_rows.append(row)

    try:
        with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(updated_rows)
    except Exception as e:
        print(f"❌ Không thể ghi lại file CSV: {e}")

    time.sleep(60) # Chờ 60 giây trước khi kiểm tra lại
