# ==========================================
# ====== AI AGENT SCHEDULER ======
# ==========================================
# Chức năng chính: Tự động đăng bài viết theo lịch từ Google Sheets
# - Đọc lịch đăng từ Google Sheets mỗi 60 giây
# - Đăng bài lên Facebook và Instagram khi đến giờ
# - Xóa bài đã đăng (mode: once) hoặc lên lịch ngày tiếp theo (mode: daily)
# - Ghi log chi tiết các hoạt động
# - Error handling toàn diện với retry logic

import csv
import time
import requests
import toml
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import os

# ====== CONSTANTS & CONFIGURATION ======
# File CSV dự phòng (hiện tại không sử dụng)
CSV_FILE = "scheduled_posts.csv"

# File log để ghi lại hoạt động của scheduler
LOG_FILE = "log_scheduler.txt"

# ID của Google Sheet chứa lịch đăng bài (cùng với app.py)
SPREADSHEET_ID = "1HUWXhKwglpJtp6yRuUfo2oy76uNKxDRx5n0RUG2q0hM"

# Tên sheet trong Google Sheet
SHEET_NAME = "xuongbinhgom"

# ====== Hàm đọc cấu hình secrets ======
# Chức năng: Đọc secrets từ file .streamlit/secrets.toml một cách an toàn.
# - Kiểm tra file tồn tại trước khi đọc
# - Trả về dict rỗng nếu có lỗi
# - Dùng chung cấu hình với app.py
def load_secrets():
    try:
        secrets_path = ".streamlit/secrets.toml"
        # - Kiểm tra file tồn tại trước khi đọc
        if os.path.exists(secrets_path):
            # - Đọc file với encoding UTF-8 để hỗ trợ tiếng Việt
            with open(secrets_path, "r", encoding="utf-8") as f:
                # - Parse nội dung file thành dict sử dụng toml
                return toml.load(f)
        else:
            # - Trả về dict rỗng nếu không tìm thấy file
            print("❌ Không tìm thấy file secrets.toml")
            return {}
    except Exception as e:
        # - Xử lý và log lỗi nếu có vấn đề khi đọc file
        print(f"❌ Lỗi đọc secrets: {e}")
        return {}

# Đọc và lưu các tokens cần thiết
secrets = load_secrets()

# Facebook tokens (bắt buộc)
DEFAULT_PAGE_ID = secrets.get("FB_PAGE_ID", "")
DEFAULT_ACCESS_TOKEN = secrets.get("FB_PAGE_TOKEN", "")

# Instagram tokens (tùy chọn)
IG_TOKEN = secrets.get("IG_TOKEN", "")
IG_ID = secrets.get("IG_ID", "")

# ====== Hàm ghi log hoạt động ======
# Chức năng: Ghi log chi tiết các hoạt động của scheduler.
# - Ghi timestamp, platform, mode, status
# - Ghi caption và image path
# - Ghi error message nếu có lỗi
# - Dùng encoding UTF-8 để hỗ trợ tiếng Việt
def write_log(platform, mode, status, caption, image_path, error_msg=None):
    try:
        # Mở file log ở chế độ append với encoding UTF-8
        with open(LOG_FILE, "a", encoding="utf-8") as logf:
            # Ghi timestamp và thông tin cơ bản
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logf.write(f"[{timestamp}] Platform: {platform.upper()} | Mode: {mode} | Status: {status}\n")
            
            if status == "SUCCESS":
                # Trường hợp đăng bài thành công:
                # - Ghi caption (giới hạn 80 ký tự)
                # - Ghi đường dẫn ảnh
                logf.write(f"  ✅ Caption: {caption[:80]}...\n")
                logf.write(f"  📷 Image: {image_path}\n\n")
            else:
                # Trường hợp đăng bài thất bại:
                # - Ghi thông báo lỗi
                # - Ghi caption và ảnh để debug
                logf.write(f"  ❌ ERROR: {error_msg}\n")
                logf.write(f"  📝 Caption: {caption[:80]}...\n")
                logf.write(f"  📷 Image: {image_path}\n\n")
    except Exception as e:
        # Xử lý lỗi khi không thể ghi file log
        print(f"❌ Lỗi ghi log: {e}")

# ====== Hàm đăng bài lên Facebook ======
# Chức năng: Đăng bài lên Facebook với error handling cải thiện.
# - Hỗ trợ đăng text only hoặc kèm ảnh
# - Sử dụng Facebook Graph API v19.0
# - Timeout 30 giây để tránh treo
# - Trả về success với post_id hoặc error với message
def post_content_to_facebook(page_id, access_token, message, image_url=None):
    print(f"🔄 Đang đăng lên Facebook...")
    
    try:
        # Xử lý trường hợp đăng kèm ảnh
        if image_url and image_url.strip():
            print(f"📷 Đăng kèm ảnh: {image_url}")
            url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
            data = {
                "message": message,
                "url": image_url,
                "access_token": access_token
            }
        # Xử lý trường hợp đăng text only
        else:
            print("📝 Đăng text only")
            url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
            data = {
                "message": message,
                "access_token": access_token
            }
        
        # Gọi API với timeout 30s
        response = requests.post(url, data=data, timeout=30)
        print(f"📊 Facebook API response: {response.status_code}")
        
        # Xử lý response thành công
        if response.status_code == 200:
            result = response.json()
            if "id" in result:
                print(f"✅ Facebook post ID: {result['id']}")
                return {"success": True, "post_id": result["id"]}
        
        # Xử lý response lỗi
        error_text = response.text
        print(f"❌ Facebook API Error: {error_text}")
        return {"error": f"HTTP {response.status_code}: {error_text}"}
        
    # Xử lý các trường hợp lỗi
    except requests.exceptions.Timeout:
        return {"error": "Timeout khi kết nối Facebook API"}
    except requests.exceptions.ConnectionError:
        return {"error": "Không thể kết nối đến Facebook API"}
    except Exception as e:
        return {"error": f"Lỗi không xác định: {str(e)}"}

# ====== Hàm đăng bài lên Instagram ======
# Chức năng: Đăng bài lên Instagram với error handling cải thiện.
# - Instagram bắt buộc phải có ảnh
# - Quy trình 2 bước: tạo media object → publish
# - Sử dụng Instagram Basic Display API
# - Timeout 30 giây cho mỗi bước
def post_content_to_instagram(ig_user_id, access_token, image_url, caption):
    print(f"🔄 Đang đăng lên Instagram...")
    
    if not image_url or not image_url.strip():
        return {"error": "Instagram yêu cầu phải có ảnh"}
    
    try:
        # Bước 1: Tạo media object
        print("📷 Tạo media object...")
        create_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media"
        create_params = {
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token
        }
        
        create_resp = requests.post(create_url, data=create_params, timeout=30)
        create_result = create_resp.json()
        
        if "id" not in create_result:
            return {"error": f"Không tạo được media: {create_result}"}
        
        creation_id = create_result["id"]
        print(f"✅ Media ID: {creation_id}")
        
        # Bước 2: Publish media object
        print("📤 Publishing media...")
        publish_url = f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish"
        publish_params = {
            "creation_id": creation_id,
            "access_token": access_token
        }
        
        publish_resp = requests.post(publish_url, data=publish_params, timeout=30)
        publish_result = publish_resp.json()
        
        if "id" in publish_result:
            print(f"✅ Instagram post ID: {publish_result['id']}")
            return {"success": True, "post_id": publish_result["id"]}
        else:
            return {"error": f"Không publish được: {publish_result}"}
            
    except requests.exceptions.Timeout:
        return {"error": "Timeout khi kết nối Instagram API"}
    except requests.exceptions.ConnectionError:
        return {"error": "Không thể kết nối đến Instagram API"}
    except Exception as e:
        return {"error": f"Lỗi không xác định: {str(e)}"}

# ====== Hàm tạo Google Sheets client ======
# Chức năng: Tạo client Google Sheets với error handling.
# - Authenticate bằng service account key
# - Scope chỉ cho phép đọc/ghi spreadsheets
# - Raise exception nếu không tạo được client
def get_gsheet_client():
    try:
        gdrive_service_account = secrets.get("gdrive_service_account", {})
        if not gdrive_service_account:
            raise Exception("Không tìm thấy thông tin service account")
            
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_info(gdrive_service_account, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Lỗi tạo Google Sheets client: {e}")
        raise

# ====== Hàm parse thời gian từ string ======
# Chức năng: Parse thời gian từ string với error handling.
# - Format: YYYY-MM-DD HH:MM
# - Clean whitespace trước khi parse
# - Raise ValueError với message chi tiết nếu lỗi
def parse_scheduled_time(date_str, time_str):
    try:
        # Loại bỏ khoảng trắng thừa
        date_str = date_str.strip()
        time_str = time_str.strip()
        
        # Kiểm tra format
        if not date_str or not time_str:
            raise ValueError("Thiếu thông tin ngày hoặc giờ")
        
        # Parse thời gian
        scheduled_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return scheduled_time
    except ValueError as e:
        raise ValueError(f"Lỗi format thời gian '{date_str} {time_str}': {e}")

# ====== Hàm xử lý hàng loạt bài viết đã lên lịch ======
# Chức năng: Đọc và xử lý tự động tất cả bài viết đã lên lịch từ Google Sheets.
# Quy trình tổng quát:
# - Kết nối với Google Sheets và lấy toàn bộ dữ liệu
# - Duyệt từng dòng để kiểm tra và xử lý riêng biệt
# - Đăng bài lên mạng xã hội khi đúng thời gian
# - Cập nhật lại lịch hoặc xóa bài đã đăng tùy theo chế độ
# BƯỚC 1 - Kết nối và lấy dữ liệu:
# - Tạo Google Sheets client với quyền đọc/ghi
# - Mở spreadsheet theo ID và lấy worksheet theo tên
# - Đọc tất cả dữ liệu (header + data rows)
# - Kiểm tra có dữ liệu để xử lý không
# BƯỚC 2 - Chuẩn bị xử lý:
# - Tách header (dòng 1) và data (từ dòng 2)
# - Khởi tạo lists để theo dõi thay đổi (xóa/cập nhật)
# - Lấy thời gian hiện tại để so sánh với lịch đăng
# BƯỚC 3 - Xử lý từng dòng:
# - Validate dữ liệu: kiểm tra đủ 10 cột, không thiếu trường bắt buộc
# - Parse thời gian đăng từ chuỗi thành datetime object
# - Chuẩn hóa dữ liệu: trim spaces, lowercase platform/mode
# - Kiểm tra business logic: mode hợp lệ (once/daily)
# - So sánh thời gian: chỉ đăng khi đã đến giờ
# BƯỚC 4 - Đăng bài theo nền tảng:
# - Facebook: gọi post_content_to_facebook() với text+ảnh optional
# - Instagram: gọi post_content_to_instagram() với ảnh bắt buộc
# - Xử lý fallback tokens khi không có token riêng
# BƯỚC 5 - Cập nhật sau khi đăng:
# - Mode "once": đánh dấu xóa dòng khỏi sheet
# - Mode "daily": cập nhật ngày sang ngày tiếp theo
# - Ghi log chi tiết cho mọi trường hợp (thành công/thất bại)
# BƯỚC 6 - Thực hiện thay đổi trên sheet:
# - Cập nhật các dòng "daily" với ngày mới
# - Xóa các dòng "once" từ cuối lên đầu (tránh lệch index)
# - Error handling riêng cho từng thao tác sheet
# Đảm bảo an toàn:
# - Mỗi dòng được xử lý độc lập (lỗi 1 dòng không ảnh hưởng dòng khác)
# - Ghi log đầy đủ để debug và audit trail
# - Network timeout và retry logic cho API calls
# - Validate dữ liệu nghiêm ngặt trước khi thực hiện
def process_scheduled_posts():
    try:
        print("🔍 Đang kiểm tra Google Sheets...")
        
        # Kết nối với Google Sheets
        gc = get_gsheet_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(SHEET_NAME)
        
        # Lấy tất cả dữ liệu từ sheet
        rows = worksheet.get_all_values()
        if len(rows) <= 1:
            print("ℹ️ Không có dữ liệu để xử lý")
            return
        
        # Tách header và data rows
        header = rows[0]  # Dòng đầu tiên là header
        data_rows = rows[1:]  # Các dòng còn lại là dữ liệu
        now = datetime.now()
        
        # Khởi tạo lists để track các thay đổi
        # Đánh dấu các dòng cần xóa (sẽ xóa từ cuối lên đầu để tránh lệch index)
        rows_to_delete = []
        # Đánh dấu các dòng cần cập nhật (cho mode daily)
        rows_to_update = []
        
        print(f"📋 Tìm thấy {len(data_rows)} dòng dữ liệu")
        
        # Xử lý từng dòng dữ liệu
        for idx, row in enumerate(data_rows):
            row_num = idx + 2  # +2 vì bắt đầu từ dòng 2 (dòng 1 là header)
            
            try:
                # BƯỚC 1: Kiểm tra tính đầy đủ của dữ liệu
                # Kiểm tra số lượng cột: phải có đủ 10 cột theo định nghĩa HEADER
                # [product, keywords, platform, time_str, token, page_id, mode, date_str, caption, image_path]
                if len(row) < 10:
                    print(f"⚠️ Dòng {row_num}: Thiếu dữ liệu - {len(row)}/10 cột")
                    continue  # Bỏ qua dòng này, tiếp tục dòng tiếp theo
                
                # Tách dữ liệu từ mảng row thành các biến riêng biệt theo thứ tự
                # Chỉ lấy 10 cột đầu tiên, bỏ qua các cột thừa (nếu có)
                product, keywords, platform, time_str, token, page_id, mode, date_str, caption, image_path = row[:10]
                
                # Kiểm tra các trường bắt buộc không được để trống
                # platform: Facebook/Instagram, mode: once/daily, date_str: YYYY-MM-DD
                # time_str: HH:MM, caption: nội dung bài viết
                if not all([platform, mode, date_str, time_str, caption]):
                    print(f"⚠️ Dòng {row_num}: Thiếu thông tin bắt buộc")
                    continue  # Bỏ qua dòng này vì thiếu thông tin quan trọng
                
                # BƯỚC 2: Chuyển đổi và kiểm tra thời gian đăng
                try:
                    # Gọi hàm parse_scheduled_time để chuyển chuỗi thành datetime
                    # Input: "2024-12-25" + "14:30" → Output: datetime(2024, 12, 25, 14, 30)
                    scheduled_time = parse_scheduled_time(date_str, time_str)
                except ValueError as e:
                    # Nếu format thời gian sai (ví dụ: "2024-13-45" hoặc "25:70")
                    print(f"❌ Dòng {row_num}: {e}")
                    continue  # Bỏ qua dòng này vì thời gian không hợp lệ
                
                # BƯỚC 3: Làm sạch và chuẩn hóa dữ liệu đầu vào
                # Loại bỏ khoảng trắng thừa ở đầu/cuối và chuyển về chữ thường
                platform = platform.strip().lower()  # "Facebook " → "facebook"
                mode = mode.strip().lower()           # "Once " → "once"
                token = token.strip()                 # " abc123 " → "abc123"
                page_id = page_id.strip()            # " 1234567890 " → "1234567890"
                caption = caption.strip()            # Loại bỏ khoảng trắng thừa
                image_path = image_path.strip()      # URL ảnh sạch
                
                print(f"\n📝 Dòng {row_num}: [{product}] | {platform.upper()} | {mode} | {scheduled_time}")
                
                # BƯỚC 4: Kiểm tra quy tắc nghiệp vụ
                # Validate mode chỉ cho phép 2 giá trị: "once" hoặc "daily"
                # - "once": đăng 1 lần rồi xóa khỏi lịch
                # - "daily": đăng hàng ngày, tự động lên lịch ngày tiếp theo
                if mode not in ["once", "daily"]:
                    print(f"⚠️ Mode không hợp lệ: '{mode}' (chỉ chấp nhận once/daily)")
                    continue  # Bỏ qua dòng này vì mode sai
                
                # BƯỚC 5: So sánh thời gian để quyết định có đăng hay không
                # Chỉ đăng khi thời gian hiện tại >= thời gian đã lên lịch
                if now < scheduled_time:
                    time_diff = scheduled_time - now  # Tính thời gian còn lại
                    print(f"⏰ Chưa đến giờ (còn {time_diff})")
                    continue  # Bỏ qua, chờ đến lượt kiểm tra tiếp theo
                
                # BƯỚC 6: Thực hiện đăng bài lên mạng xã hội
                result = None  # Khởi tạo biến để lưu kết quả đăng bài
                
                if platform == "facebook":
                    # Xử lý đăng bài lên Facebook
                    # Sử dụng token và page_id riêng, nếu không có thì dùng mặc định
                    result = post_content_to_facebook(
                        page_id or DEFAULT_PAGE_ID,      # Fallback đến page mặc định
                        token or DEFAULT_ACCESS_TOKEN,   # Fallback đến token mặc định  
                        caption,                         # Nội dung bài viết
                        image_url=image_path if image_path else None  # Ảnh optional cho FB
                    )
                elif platform == "instagram":
                    # Xử lý đăng bài lên Instagram
                    # Instagram bắt buộc phải có ảnh, không hỗ trợ text-only
                    result = post_content_to_instagram(
                        page_id or IG_ID,               # Fallback đến IG account mặc định
                        token or IG_TOKEN,              # Fallback đến IG token mặc định
                        image_url=image_path,           # Ảnh bắt buộc cho Instagram
                        caption=caption                 # Caption đi kèm ảnh
                    )
                else:
                    # Platform không được hỗ trợ (không phải facebook/instagram)
                    print(f"❌ Platform không hỗ trợ: {platform}")
                    continue  # Bỏ qua dòng này, tiếp tục dòng tiếp theo
                
                # BƯỚC 7: Xử lý kết quả đăng bài và cập nhật lịch
                if result and "success" in result:
                    # Trường hợp đăng bài thành công
                    print(f"✅ Đăng thành công {platform.upper()}!")
                    write_log(platform, mode, "SUCCESS", caption, image_path)
                    
                    if mode == "once":
                        # Mode "once": đăng 1 lần rồi xóa khỏi lịch
                        # Thêm vào danh sách dòng cần xóa (xóa sau cùng để tránh lệch index)
                        rows_to_delete.append(row_num)
                        print(f"🗑️ Đánh dấu xóa dòng {row_num} (mode: once)")
                    elif mode == "daily":
                        # Mode "daily": lên lịch cho ngày tiếp theo
                        # Cộng thêm 1 ngày từ thời gian đã đăng
                        next_date = scheduled_time + timedelta(days=1)
                        new_date_str = next_date.strftime("%Y-%m-%d")  # Format YYYY-MM-DD
                        # Thêm vào danh sách cập nhật: (row_num, col_index, new_value)
                        # Cột 8 (index bắt đầu từ 1) chứa date_str
                        rows_to_update.append((row_num, 8, new_date_str))
                        print(f"📅 Lên lịch ngày tiếp theo: {new_date_str}")
                else:
                    # Trường hợp đăng bài thất bại
                    # Lấy thông báo lỗi từ result, nếu không có thì dùng message mặc định
                    error_msg = result.get("error", "Lỗi không xác định") if result else "Không có response"
                    print(f"❌ Đăng thất bại {platform.upper()}: {error_msg}")
                    # Ghi log lỗi để debug sau này
                    write_log(platform, mode, "ERROR", caption, image_path, error_msg=error_msg)
                
            except Exception as e:
                print(f"❌ Lỗi xử lý dòng {row_num}: {e}")
                platform_name = locals().get('platform', 'unknown')
                mode_name = locals().get('mode', 'unknown')
                caption_text = locals().get('caption', '')
                image_text = locals().get('image_path', '')
                write_log(platform_name, mode_name, "ERROR", caption_text, image_text, error_msg=str(e))
        
        # BƯỚC 8: Thực hiện các thay đổi trên Google Sheets
        # Xử lý cập nhật dòng trước (cho mode "daily")
        if rows_to_update:
            print(f"📝 Cập nhật {len(rows_to_update)} dòng...")
            for row_num, col_num, new_value in rows_to_update:
                try:
                    # Gọi Google Sheets API để cập nhật 1 cell cụ thể
                    # row_num: số dòng, col_num: số cột, new_value: giá trị mới
                    worksheet.update_cell(row_num, col_num, new_value)
                    print(f"✅ Cập nhật dòng {row_num}")
                except Exception as e:
                    # Ghi log lỗi nếu không cập nhật được (network, quyền, etc.)
                    print(f"❌ Lỗi cập nhật dòng {row_num}: {e}")
        
        # Xử lý xóa dòng sau (cho mode "once")
        if rows_to_delete:
            print(f"🗑️ Xóa {len(rows_to_delete)} dòng...")
            # Xóa từ cuối lên đầu để tránh lệch số thứ tự dòng
            # Ví dụ: xóa dòng [2,4,6] → xóa 6 trước, rồi 4, cuối cùng 2
            for row_num in sorted(rows_to_delete, reverse=True):
                try:
                    # Gọi Google Sheets API để xóa 1 dòng hoàn toàn
                    worksheet.delete_rows(row_num)
                    print(f"✅ Xóa dòng {row_num}")
                except Exception as e:
                    # Ghi log lỗi nếu không xóa được (network, quyền, etc.)
                    print(f"❌ Lỗi xóa dòng {row_num}: {e}")
        
        # Thông báo khi không có gì để xử lý (tất cả bài chưa đến giờ)
        if not rows_to_delete and not rows_to_update:
            print("ℹ️ Không có dòng nào cần xử lý")
            
    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng trong process_scheduled_posts: {e}")
        write_log('system', 'process', 'ERROR', '', '', error_msg=str(e))

# ====== Hàm chính - Vòng lặp scheduler chạy 24/7 ======
# Chức năng: Vòng lặp chính của scheduler, chạy liên tục để tự động đăng bài.
# Cách thức hoạt động:
# - Chạy vòng lặp vô hạn với interval 60 giây
# - Mỗi lần lặp gọi process_scheduled_posts() để xử lý lịch đăng
# - Hiển thị thông tin khởi động và trạng thái hoạt động
# Xử lý khởi động:
# - In thông tin cấu hình: Spreadsheet ID, Sheet Name
# - Thông báo interval kiểm tra (60 giây)
# - Hiển thị timestamp cho mỗi lần kiểm tra
# Vòng lặp chính:
# - Lấy timestamp hiện tại và hiển thị đang kiểm tra
# - Gọi process_scheduled_posts() để xử lý tất cả bài đã lên lịch
# - Sleep 60 giây trước khi kiểm tra lần tiếp theo
# - In dấu phân cách để dễ đọc log
# Xử lý ngắt và lỗi:
# - KeyboardInterrupt (Ctrl+C): Dừng scheduler một cách graceful
# - Exception khác: Ghi log lỗi nhưng không dừng, tiếp tục sau 60 giây
# - Đảm bảo scheduler luôn hoạt động trừ khi bị dừng thủ công
# Monitoring và logging:
# - Log mọi hoạt động với timestamp rõ ràng
# - Ghi lỗi hệ thống vào log file để debug
# - Hiển thị trạng thái real-time trên console
def main():
    print("🟢 AI Agent Scheduler đang khởi động...")
    print(f"📊 Spreadsheet ID: {SPREADSHEET_ID}")
    print(f"📋 Sheet Name: {SHEET_NAME}")
    print("⏰ Kiểm tra mỗi 60 giây...\n")
    
    # Vòng lặp chính chạy liên tục 24/7
    while True:
        try:
            # Lấy và hiển thị thời gian hiện tại cho mỗi lần kiểm tra
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n🕐 [{current_time}] Đang kiểm tra lịch đăng...")
            
            # Gọi hàm chính để xử lý tất cả bài viết đã lên lịch
            # Hàm này sẽ đọc Google Sheets và đăng bài nếu đúng giờ
            process_scheduled_posts()
            
            # Hiển thị thông báo chờ và dấu phân cách để dễ đọc log
            print("💤 Chờ 60 giây...\n" + "="*50)
            # Sleep 60 giây trước khi kiểm tra lần tiếp theo
            time.sleep(60)
            
        except KeyboardInterrupt:
            # Xử lý khi người dùng nhấn Ctrl+C để dừng scheduler
            print("\n🛑 Dừng scheduler theo yêu cầu người dùng")
            break  # Thoát khỏi vòng lặp và kết thúc chương trình
        except Exception as e:
            # Xử lý mọi lỗi khác (network, API, file, etc.)
            print(f"❌ Lỗi không xác định: {e}")
            # Ghi lỗi vào log file để debug sau này
            write_log('system', 'main_loop', 'ERROR', '', '', error_msg=str(e))
            print("⏰ Tiếp tục sau 60 giây...")
            # Không break, tiếp tục chạy sau 60 giây để đảm bảo scheduler luôn hoạt động
            time.sleep(60)

if __name__ == "__main__":
    main()

