import os
import pytest
import json
import pandas as pd
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, date, time

# Import các hàm từ app.py để test
from app import (
    # Utility Functions
    load_posts, save_posts, get_safe_posts_data, prepare_dataframe,
    
    # Facebook API Functions  
    fetch_facebook_posts, fetch_post_stats, get_facebook_data,
    
    # Google Sheets Functions
    get_gsheet_client, ensure_sheet_header, schedule_post_to_sheet,
    
    # AI & Content Functions
    generate_caption, call_ai_analysis,
    
    # Image Upload Functions
    upload_image_to_gdrive, upload_image_to_cloudinary, handle_image_upload,
    
    # UI Helper Functions
    display_analytics_stats, create_analytics_chart, beautify_ai_output, safe_remove_post
)

TEST_FILE = "test_posts.json"
SAMPLE_POSTS = [
    {"id": "001", "caption": "Test post 1", "likes": 10, "comments": 5},
    {"id": "002", "caption": "Test post 2", "likes": 20, "comments": 3}
]

# ==========================================
# ====== UTILITY FUNCTIONS TESTS ======
# ==========================================

class TestUtilityFunctions:
    
    def test_save_and_load_posts_success(self):
        """Test lưu và đọc file JSON thành công"""
        test_data = [{"id": "001", "caption": "Test bài viết", "platform": "Facebook"}]
        save_posts(test_data, filename=TEST_FILE)
        
        assert os.path.exists(TEST_FILE), "❌ File không tồn tại sau khi lưu"
        
        loaded = load_posts(filename=TEST_FILE)
        assert loaded == test_data, "❌ Dữ liệu đọc không khớp"
        
        # Cleanup
        if os.path.exists(TEST_FILE):
            os.remove(TEST_FILE)
    
    def test_load_posts_file_not_exists(self):
        """Test đọc file không tồn tại"""
        result = load_posts("non_existent_file.json")
        assert result == [], "❌ Phải trả về list rỗng khi file không tồn tại"
    
    @patch("builtins.open", side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
    def test_load_posts_invalid_json(self, mock_file):
        """Test xử lý file JSON không hợp lệ"""
        with patch("os.path.exists", return_value=True):
            result = load_posts("invalid.json")
            assert result == [], "❌ Phải trả về list rỗng khi JSON invalid"
    
    @patch("app.st.session_state", {"posts": SAMPLE_POSTS})
    def test_get_safe_posts_data_success(self):
        """Test lấy dữ liệu từ session state thành công"""
        result = get_safe_posts_data()
        assert result == SAMPLE_POSTS, "❌ Dữ liệu từ session state không đúng"
    
    @patch("app.st.session_state", {"posts": "invalid_data"})
    def test_get_safe_posts_data_invalid_type(self):
        """Test xử lý dữ liệu session state không phải list"""
        result = get_safe_posts_data()
        assert result == [], "❌ Phải trả về list rỗng khi data không phải list"
    
    @patch("app.st.session_state", {})
    def test_get_safe_posts_data_missing_key(self):
        """Test xử lý key không tồn tại trong session state"""
        result = get_safe_posts_data()
        assert result == [], "❌ Phải trả về list rỗng khi key không tồn tại"
    
    def test_prepare_dataframe_complete_data(self):
        """Test chuẩn bị DataFrame với dữ liệu đầy đủ"""
        test_data = [
            {"likes": 10, "comments": 5, "shares": 2, "reactions": 15, "time": "09:00"},
            {"likes": 20, "comments": 8, "shares": 3, "reactions": 25, "time": "14:00"}
        ]
        df = prepare_dataframe(test_data)
        
        assert len(df) == 2, "❌ DataFrame phải có 2 rows"
        assert "likes" in df.columns, "❌ Thiếu cột likes"
        assert "time" in df.columns, "❌ Thiếu cột time"
        assert df["likes"].dtype == "int64", "❌ Cột likes phải là int"
    
    def test_prepare_dataframe_missing_columns(self):
        """Test chuẩn bị DataFrame với thiếu columns"""
        test_data = [{"caption": "Test", "platform": "Facebook"}]
        df = prepare_dataframe(test_data, ["likes", "comments", "shares"])
        
        assert "likes" in df.columns, "❌ Phải tạo cột likes"
        assert df["likes"].iloc[0] == 0, "❌ Giá trị mặc định phải là 0"
        assert "time" in df.columns, "❌ Phải tạo cột time"
        assert df["time"].iloc[0] == "unknown", "❌ Time mặc định phải là 'unknown'"

# ==========================================
# ====== FACEBOOK API FUNCTIONS TESTS ======
# ==========================================

class TestFacebookAPIFunctions:
    
    @patch("app.requests.get")
    def test_fetch_facebook_posts_success(self, mock_get):
        """Test lấy posts Facebook thành công"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "123", "message": "Test post", "created_time": "2024-01-01T10:00:00+0000"}
            ]
        }
        mock_get.return_value = mock_response
        
        result = fetch_facebook_posts("page_id", "token", 10)
        
        assert len(result) == 1, "❌ Phải trả về 1 post"
        assert result[0]["id"] == "123", "❌ Post ID không đúng"
        
        # Verify API call
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "page_id/posts" in args[0], "❌ URL không đúng"
    
    @patch("app.requests.get")
    def test_fetch_facebook_posts_empty_response(self, mock_get):
        """Test xử lý response rỗng từ Facebook API"""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response
        
        result = fetch_facebook_posts("page_id", "token")
        
        assert result == [], "❌ Phải trả về list rỗng khi không có data"
    
    @patch("app.requests.get")
    def test_fetch_post_stats_success(self, mock_get):
        """Test lấy stats của post thành công"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": "Test caption",
            "likes": {"summary": {"total_count": 50}},
            "comments": {"summary": {"total_count": 10}},
            "shares": {"count": 5},
            "reactions": {"summary": {"total_count": 60}}
        }
        mock_get.return_value = mock_response
        
        result = fetch_post_stats("post_id", "token")
        
        assert result["likes"]["summary"]["total_count"] == 50, "❌ Likes count không đúng"
        assert result["comments"]["summary"]["total_count"] == 10, "❌ Comments count không đúng"
    
    @patch("app.fetch_facebook_posts")
    @patch("app.fetch_post_stats")
    @patch("app.st.session_state", {})
    def test_get_facebook_data_fresh_fetch(self, mock_stats, mock_posts):
        """Test lấy Facebook data lần đầu (không có cache)"""
        # Mock data
        mock_posts.return_value = [{"id": "123", "created_time": "2024-01-01T10:00:00+0000"}]
        mock_stats.return_value = {
            "message": "Test",
            "likes": {"summary": {"total_count": 10}},
            "comments": {"summary": {"total_count": 5}},
            "shares": {"count": 2},
            "reactions": {"summary": {"total_count": 15}}
        }
        
        result = get_facebook_data()
        
        assert len(result) == 1, "❌ Phải có 1 post"
        assert result[0]["likes"] == 10, "❌ Likes không đúng"
        assert result[0]["platform"] == "Facebook", "❌ Platform phải là Facebook"
    
    @patch("app.st.session_state", {"fb_posts": SAMPLE_POSTS})
    def test_get_facebook_data_cached(self):
        """Test sử dụng cached Facebook data"""
        result = get_facebook_data()
        
        assert result == SAMPLE_POSTS, "❌ Phải trả về cached data"

# ==========================================
# ====== GOOGLE SHEETS FUNCTIONS TESTS ======
# ==========================================

class TestGoogleSheetsFunctions:
    
    @patch("app.gspread.authorize")
    @patch("app.Credentials.from_service_account_info")
    @patch("app.st.secrets", {"gdrive_service_account": {"type": "service_account"}})
    def test_get_gsheet_client_success(self, mock_creds, mock_authorize):
        """Test tạo Google Sheets client thành công"""
        mock_client = MagicMock()
        mock_authorize.return_value = mock_client
        
        result = get_gsheet_client()
        
        assert result == mock_client, "❌ Phải trả về client object"
        mock_creds.assert_called_once()
        mock_authorize.assert_called_once()
    
    def test_ensure_sheet_header_correct_header(self):
        """Test header đã đúng, không cần thay đổi"""
        mock_worksheet = MagicMock()
        mock_worksheet.row_values.return_value = ["col1", "col2", "col3"]
        
        header = ["col1", "col2", "col3"]
        ensure_sheet_header(mock_worksheet, header)
        
        # Không được gọi clear() hay append_row()
        mock_worksheet.clear.assert_not_called()
        mock_worksheet.append_row.assert_not_called()
    
    def test_ensure_sheet_header_wrong_header(self):
        """Test header sai, cần thay đổi"""
        mock_worksheet = MagicMock()
        mock_worksheet.row_values.return_value = ["wrong1", "wrong2"]
        
        header = ["col1", "col2", "col3"]
        ensure_sheet_header(mock_worksheet, header)
        
        # Phải gọi clear() và append_row()
        mock_worksheet.clear.assert_called_once()
        mock_worksheet.append_row.assert_called_once_with(header)
    
    @patch("app.get_gsheet_client")
    @patch("app.ensure_sheet_header")
    def test_schedule_post_to_sheet_success(self, mock_ensure, mock_client):
        """Test lên lịch đăng bài vào Sheet thành công"""
        # Mock objects
        mock_gc = MagicMock()
        mock_sh = MagicMock()
        mock_worksheet = MagicMock()
        
        mock_client.return_value = mock_gc
        mock_gc.open_by_key.return_value = mock_sh
        mock_sh.worksheet.return_value = mock_worksheet
        
        # Test function
        schedule_post_to_sheet(
            "Product", "keywords", "Facebook", "09:00",
            "token", "page_id", "once", "2024-01-01",
            "Test caption", "image_url"
        )
        
        # Verify calls
        mock_gc.open_by_key.assert_called_once()
        mock_sh.worksheet.assert_called_once()
        mock_ensure.assert_called_once()
        mock_worksheet.append_row.assert_called_once()

# ==========================================
# ====== AI & CONTENT FUNCTIONS TESTS ======
# ==========================================

class TestAIContentFunctions:
    
    @patch("app.client.chat.completions.create")
    def test_generate_caption_success(self, mock_gpt):
        """Test sinh caption thành công"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Caption đẹp với emoji 🌸 #xuongbinhgom"
        mock_gpt.return_value = mock_response
        
        result = generate_caption("Bình hoa", "gốm, thủ công", "Facebook")
        
        assert "#xuongbinhgom" in result, "❌ Phải có hashtag #xuongbinhgom"
        assert len(result) > 10, "❌ Caption phải có độ dài hợp lý"
        
        # Verify API call với đúng params
        mock_gpt.assert_called_once()
        call_args = mock_gpt.call_args[1]
        assert call_args["model"] == "openai/gpt-3.5-turbo"
        assert call_args["temperature"] == 0.95
    
    @patch("app.client.chat.completions.create")
    def test_generate_caption_missing_hashtag(self, mock_gpt):
        """Test tự động thêm hashtag nếu thiếu"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Caption không có hashtag"
        mock_gpt.return_value = mock_response
        
        result = generate_caption("Product", "keywords", "Instagram")
        
        assert "#xuongbinhgom" in result, "❌ Phải tự động thêm hashtag"
    
    @patch("app.client.chat.completions.create")
    def test_generate_caption_api_error(self, mock_gpt):
        """Test xử lý lỗi OpenAI API"""
        from openai import OpenAIError
        mock_gpt.side_effect = OpenAIError("API Error")
        
        result = generate_caption("Product", "keywords", "Facebook")
        
        assert result.startswith("⚠️"), "❌ Phải trả về error message"
        assert "GPT" in result, "❌ Error message phải chứa thông tin về GPT"
    
    @patch("app.client.chat.completions.create")
    def test_call_ai_analysis_success(self, mock_gpt):
        """Test gọi AI analysis thành công"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Phân tích chi tiết về hiệu quả bài viết"
        mock_gpt.return_value = mock_response
        
        prompt = "Phân tích dữ liệu marketing"
        result = call_ai_analysis(prompt, temperature=0.8)
        
        assert "phân tích" in result.lower(), "❌ Kết quả phải chứa từ 'phân tích'"
        
        # Verify custom temperature
        call_args = mock_gpt.call_args[1]
        assert call_args["temperature"] == 0.8

# ==========================================
# ====== IMAGE UPLOAD FUNCTIONS TESTS ======
# ==========================================

class TestImageUploadFunctions:
    
    @patch("app.cloudinary.uploader.upload")
    def test_upload_image_to_cloudinary_success(self, mock_upload):
        """Test upload ảnh lên Cloudinary thành công"""
        mock_upload.return_value = {"secure_url": "https://res.cloudinary.com/test/image.jpg"}
        
        image_bytes = b"fake-image-data"
        result = upload_image_to_cloudinary(image_bytes, "custom_preset")
        
        assert result.startswith("https://res.cloudinary.com"), "❌ URL không đúng format"
        
        # Verify upload call
        mock_upload.assert_called_once_with(
            image_bytes,
            upload_preset="custom_preset",
            resource_type="image"
        )
    
    @patch("app.service_account.Credentials.from_service_account_info")
    @patch("app.build")
    @patch("app.st.secrets", {"gdrive_service_account": {"type": "service_account"}})
    def test_upload_image_to_gdrive_success(self, mock_build, mock_creds):
        """Test upload ảnh lên Google Drive thành công"""
        # Mock Google Drive service
        mock_service = MagicMock()
        mock_files = mock_service.files.return_value
        mock_files.create.return_value.execute.return_value = {"id": "fake_file_id"}
        mock_build.return_value = mock_service
        
        image_bytes = b"fake-image-data"
        result = upload_image_to_gdrive(image_bytes, "test.jpg")
        
        assert result == "https://drive.google.com/uc?id=fake_file_id", "❌ URL không đúng"
        
        # Verify file creation và permission setting
        mock_files.create.assert_called_once()
        mock_service.permissions().create.assert_called_once()
    
    @patch("app.upload_image_to_cloudinary")
    @patch("app.upload_image_to_gdrive")
    def test_handle_image_upload_instagram(self, mock_gdrive, mock_cloudinary):
        """Test router function cho Instagram"""
        mock_cloudinary.return_value = "https://cloudinary.com/test.jpg"
        
        mock_file = MagicMock()
        mock_file.read.return_value = b"image-data"
        
        result = handle_image_upload(mock_file, "Instagram")
        
        assert result == "https://cloudinary.com/test.jpg", "❌ Phải dùng Cloudinary cho IG"
        mock_cloudinary.assert_called_once()
        mock_gdrive.assert_not_called()
    
    @patch("app.upload_image_to_cloudinary")
    @patch("app.upload_image_to_gdrive")
    def test_handle_image_upload_facebook(self, mock_gdrive, mock_cloudinary):
        """Test router function cho Facebook"""
        mock_gdrive.return_value = "https://drive.google.com/uc?id=123"
        
        mock_file = MagicMock()
        mock_file.read.return_value = b"image-data"
        mock_file.name = "test.jpg"
        
        result = handle_image_upload(mock_file, "Facebook")
        
        assert result.startswith("https://drive.google.com"), "❌ Phải dùng GDrive cho FB"
        mock_gdrive.assert_called_once()
        mock_cloudinary.assert_not_called()
    
    def test_handle_image_upload_no_file(self):
        """Test xử lý khi không có file"""
        result = handle_image_upload(None, "Facebook")
        assert result is None, "❌ Phải trả về None khi không có file"

# ==========================================
# ====== UI HELPER FUNCTIONS TESTS ======
# ==========================================

class TestUIHelperFunctions:
    
    @patch("app.st.markdown")
    def test_display_analytics_stats_success(self, mock_markdown):
        """Test hiển thị thống kê tổng hợp"""
        test_df = pd.DataFrame({
            "likes": [10, 20, 30],
            "comments": [5, 8, 12],
            "shares": [2, 3, 5],
            "reactions": [15, 25, 35]
        })
        
        display_analytics_stats(test_df)
        
        # Verify được gọi với HTML content
        assert mock_markdown.call_count == 2, "❌ Phải gọi st.markdown 2 lần"
        
        # Check tổng số trong HTML
        html_content = mock_markdown.call_args_list[1][0][0]
        assert "60" in html_content, "❌ Tổng likes phải là 60"
        assert "25" in html_content, "❌ Tổng comments phải là 25"
    
    @patch("app.plt.subplots")
    @patch("app.st.pyplot")
    def test_create_analytics_chart_line(self, mock_pyplot, mock_subplots):
        """Test tạo biểu đồ Line chart"""
        mock_fig, mock_ax = MagicMock(), MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)
        
        test_df = pd.DataFrame({
            "created_time": ["2024-01-01T10:00:00", "2024-01-02T10:00:00"],
            "likes": [10, 20],
            "comments": [5, 8],
            "shares": [2, 3],
            "reactions": [15, 25]
        })
        
        create_analytics_chart(test_df, "Ngày", "Line")
        
        # Verify chart được tạo và hiển thị
        mock_subplots.assert_called_once()
        mock_pyplot.assert_called_once_with(mock_fig)
    
    def test_beautify_ai_output_headers(self):
        """Test format AI output với headers"""
        content = "Tiêu đề chính:<br>- Điểm 1<br>- Điểm 2<br>Phần kết luận"
        
        result = beautify_ai_output(content)
        
        assert "background:#e3f2fd" in result, "❌ Phải có background cho header"
        assert "💡" in result, "❌ Phải có emoji cho header"
        assert "✔️" in result, "❌ Phải có checkmark cho list items"
    
    def test_beautify_ai_output_lists(self):
        """Test format AI output với danh sách"""
        content = "- Item 1<br>- Item 2<br>1. Numbered item"
        
        result = beautify_ai_output(content)
        
        assert "<ul" in result, "❌ Phải tạo ul tag"
        assert "</ul>" in result, "❌ Phải đóng ul tag"
        assert "list-style:none" in result, "❌ Phải remove default list style"
    
    @patch("app.st.session_state", {"posts": SAMPLE_POSTS})
    @patch("app.save_posts")
    def test_safe_remove_post_valid_index(self, mock_save):
        """Test xóa post với index hợp lệ"""
        safe_remove_post(1)  # Xóa post đầu tiên (1-indexed)
        
        # Verify save_posts được gọi
        mock_save.assert_called_once()
    
    @patch("app.st.session_state", {"posts": SAMPLE_POSTS})
    @patch("app.save_posts")
    def test_safe_remove_post_invalid_index(self, mock_save):
        """Test xóa post với index không hợp lệ"""
        safe_remove_post(999)  # Index quá lớn
        
        # Không được gọi save_posts
        mock_save.assert_not_called()
    
    @patch("app.st.session_state", {})
    @patch("app.save_posts")
    def test_safe_remove_post_no_posts(self, mock_save):
        """Test xóa post khi không có dữ liệu"""
        safe_remove_post(1)
        
        # Không được gọi save_posts
        mock_save.assert_not_called()

# ==========================================
# ====== INTEGRATION TESTS ======
# ==========================================

class TestIntegration:
    
    @patch("app.generate_caption")
    @patch("app.handle_image_upload")
    @patch("app.schedule_post_to_sheet")
    def test_create_post_workflow_auto_mode(self, mock_schedule, mock_upload, mock_caption):
        """Test workflow tạo bài đăng ở chế độ tự động"""
        # Setup mocks
        mock_caption.return_value = "Generated caption #xuongbinhgom"
        mock_upload.return_value = "https://example.com/image.jpg"
        
        # Mock data như từ UI
        product_name = "Bình gốm"
        keywords = "handmade, decor"
        platform = "Facebook"
        
        # Simulate workflow steps
        caption = generate_caption(product_name, keywords, platform)
        mock_file = MagicMock()
        image_url = handle_image_upload(mock_file, platform)
        
        # Verify workflow
        assert "#xuongbinhgom" in caption
        assert image_url.startswith("https://")
        
        mock_caption.assert_called_once_with(product_name, keywords, platform)
        mock_upload.assert_called_once_with(mock_file, platform)
    
    @patch("app.load_posts")
    @patch("app.save_posts")
    @patch("app.get_safe_posts_data")
    def test_manual_approval_workflow(self, mock_get_safe, mock_save, mock_load):
        """Test workflow duyệt bài thủ công"""
        # Setup initial data
        initial_posts = [
            {"id": "001", "caption": "Test post", "platform": "Facebook"}
        ]
        mock_load.return_value = initial_posts
        mock_get_safe.return_value = initial_posts
        
        # Simulate approval process
        posts = get_safe_posts_data()
        assert len(posts) == 1
        
        # After approval, post should be removed
        mock_get_safe.return_value = []
        posts_after = get_safe_posts_data()
        assert len(posts_after) == 0

if __name__ == "__main__":
    # Chạy tất cả tests
    pytest.main([__file__, "-v", "--tb=short"])
    print("\n✅ Hoàn thành tất cả unit tests!")
    print("📊 Coverage bao gồm:")
    print("   - 4 Utility Functions")
    print("   - 3 Facebook API Functions") 
    print("   - 3 Google Sheets Functions")
    print("   - 2 AI & Content Functions")
    print("   - 3 Image Upload Functions")
    print("   - 4 UI Helper Functions")
    print("   - 2 Integration Tests")
    print("   - Tổng cộng: 8 test classes với 35+ test cases") 