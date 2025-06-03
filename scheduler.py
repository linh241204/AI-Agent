import csv
import time
import requests
import toml
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

CSV_FILE = "scheduled_posts.csv"
LOG_FILE = "log_scheduler.txt"
SPREADSHEET_ID = "1HUWXhKwglpJtp6yRuUfo2oy76uNKxDRx5n0RUG2q0hM"  # Thay bằng ID Google Sheet của bạn
SHEET_NAME = "xuongbinhgom"  # Hoặc tên sheet bạn đặt

# Đọc secrets từ file .streamlit/secrets.toml
with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
    secrets = toml.load(f)
DEFAULT_PAGE_ID = secrets["FB_PAGE_ID"]
DEFAULT_ACCESS_TOKEN = secrets["FB_PAGE_TOKEN"]
IG_TOKEN = secrets.get("IG_TOKEN", "")
IG_ID = secrets.get("IG_ID", "")

def write_log(platform, mode, status, caption, image_path, error_msg=None):
    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        logf.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ")
        logf.write(f"Platform: {platform.upper()} | Mode: {mode} | Status: {status}\n")
        if status == "SUCCESS":
            logf.write(f"  Caption: {caption[:80]}\n  Image: {image_path}\n\n")
        else:
            logf.write(f"  ERROR: {error_msg}\n  Caption: {caption[:80]}\n  Image: {image_path}\n\n")

def post_content_to_facebook(page_id, access_token, message, image_url=None):
    if image_url:
        print(f"[DEBUG] Đang gửi image_url tới Facebook: {image_url}")
        url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
        data = {
            "message": message,
            "url": image_url,
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
        print(f"[DEBUG] Facebook API response: {response.status_code} {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Lỗi khi gọi API Facebook: {e}")
        if 'response' in locals() and response is not None:
            print(f"   Phản hồi lỗi từ Facebook: {response.text}")
        return {"error": str(e)}

def post_content_to_instagram(ig_user_id, access_token, image_url, caption):
    # Bước 1: Tạo media object
    create_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
    create_params = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token
    }
    create_resp = requests.post(create_url, data=create_params)
    result = create_resp.json()
    if "id" not in result:
        print(f"[IG] ❌ Lỗi tạo media: {result}")
        return {"error": result}
    creation_id = result["id"]
    # Bước 2: Publish media object
    publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
    publish_params = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    publish_resp = requests.post(publish_url, data=publish_params)
    print(f"[IG] API response: {publish_resp.status_code} {publish_resp.text}")
    return publish_resp.json()

def get_gsheet_client():
    # Đọc thông tin service account từ file .streamlit/secrets.toml
    with open(".streamlit/secrets.toml", "r", encoding="utf-8") as f:
        secrets = toml.load(f)
    gdrive_service_account = secrets["gdrive_service_account"]
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_info(gdrive_service_account, scopes=scopes)
    return gspread.authorize(creds)

print("🟢 Scheduler AI Agent đang chạy... (kiểm tra mỗi 60 giây)")

while True:
    now = datetime.now()
    gc = get_gsheet_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)
    rows = worksheet.get_all_values()
    header = rows[0]
    data_rows = rows[1:]
    updated_rows = [header]
    for idx, row in enumerate(data_rows, start=2):  # start=2 vì dòng 1 là header
        if len(row) < 10:
            print(f"⚠️ Bỏ qua dòng {idx} thiếu cột hoặc sai định dạng: {row}")
            updated_rows.append(row)
            continue
        try:
            product, keywords, platform, time_str, token, page_id, mode, date_str, caption, image_path = row[:10]
            scheduled_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            token = token.strip()
            page_id = page_id.strip()
            platform = platform.strip().lower()
            mode = mode.strip().lower()
            caption = caption.strip()
            image_path = image_path.strip()
            print(f"\n📄 [{product}] | Platform: {platform} | Mode: {mode} | Lịch: {scheduled_time} | Hiện tại: {now}")
            # --- Chỉ xử lý mode once và daily ---
            if mode not in ["once", "daily"]:
                updated_rows.append(row)
                print(f"ℹ️ Bỏ qua mode '{mode}' (chỉ xử lý once/daily)")
                continue
            # --- Chỉ xử lý khi đã đến giờ ---
            if now < scheduled_time:
                updated_rows.append(row)
                continue
            # --- Xử lý theo platform ---
            if platform == "facebook":
                result = post_content_to_facebook(
                    page_id or DEFAULT_PAGE_ID,
                    token or DEFAULT_ACCESS_TOKEN,
                    caption,
                    image_url=image_path if image_path else None
                )
            elif platform == "instagram":
                result = post_content_to_instagram(
                    page_id or IG_ID,
                    token or IG_TOKEN,
                    image_url=image_path,
                    caption=caption
                )
            else:
                print(f"⚠️ Platform không hợp lệ: {platform}")
                updated_rows.append(row)
                continue
            # --- Xử lý kết quả ---
            if "error" not in result:
                print(f"✅ Đã đăng thành công [{platform.upper()}] | {mode} | {scheduled_time}")
                write_log(platform, mode, "SUCCESS", caption, image_path)
                if mode == "once":
                    worksheet.delete_rows(idx)
                elif mode == "daily":
                    next_scheduled_time = scheduled_time + timedelta(days=1)
                    worksheet.update_cell(idx, 8, next_scheduled_time.strftime("%Y-%m-%d"))
            else:
                print(f"❌ Lỗi khi đăng [{platform.upper()}]: {result}")
                write_log(platform, mode, "ERROR", caption, image_path, error_msg=str(result))
                updated_rows.append(row)
        except Exception as e:
            print(f"❌ Lỗi không xác định khi xử lý dòng {idx}: {row}. Lỗi: {e}")
            write_log(platform if 'platform' in locals() else 'unknown', mode if 'mode' in locals() else 'unknown', "ERROR", caption if 'caption' in locals() else '', image_path if 'image_path' in locals() else '', error_msg=str(e))
            updated_rows.append(row)
    try:
        worksheet.resize(rows=1)
        if updated_rows:
            worksheet.append_rows(updated_rows)
    except Exception as e:
        print(f"❌ Không thể ghi lại Google Sheets: {e}")
        write_log('system', 'write_gsheet', 'ERROR', '', '', error_msg=str(e))
    time.sleep(60)
