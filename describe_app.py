import pandas as pd

# Sheet 1: Hàm (Functions)
functions = [
    {
        "Tên hàm": "save_posts",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "Lưu danh sách bài viết vào file JSON",
        "Input/Tham số": "posts, filename (mặc định)",
        "Output/Kết quả trả về": "None"
    },
    {
        "Tên hàm": "load_posts",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "Đọc danh sách bài viết từ file JSON",
        "Input/Tham số": "filename (mặc định)",
        "Output/Kết quả trả về": "List bài viết"
    },
    {
        "Tên hàm": "generate_caption",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "Sinh caption marketing bằng GPT cho sản phẩm, nền tảng, từ khóa",
        "Input/Tham số": "product_name, keywords, platform",
        "Output/Kết quả trả về": "Caption (str) hoặc lỗi"
    },
    {
        "Tên hàm": "upload_image_to_gdrive",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "Upload ảnh lên Google Drive, trả về link công khai",
        "Input/Tham số": "image_bytes, filename",
        "Output/Kết quả trả về": "Link ảnh public"
    },
    {
        "Tên hàm": "list_gdrive_images_recursive",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "Đệ quy lấy danh sách ảnh trong thư mục Google Drive",
        "Input/Tham số": "service, folder_id",
        "Output/Kết quả trả về": "List ảnh"
    },
    {
        "Tên hàm": "list_gdrive_images",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "Lấy danh sách ảnh từ Google Drive",
        "Input/Tham số": "folder_id",
        "Output/Kết quả trả về": "List ảnh"
    },
    {
        "Tên hàm": "list_gdrive_tree",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "Lấy cây thư mục và ảnh trong Google Drive",
        "Input/Tham số": "service, folder_id",
        "Output/Kết quả trả về": "folders, images"
    },
    {
        "Tên hàm": "pick_gdrive_image",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "UI chọn ảnh từ Google Drive (breadcrumb, chọn thư mục, chọn ảnh)",
        "Input/Tham số": "folder_id, path",
        "Output/Kết quả trả về": "None (UI)"
    },
    {
        "Tên hàm": "post_content_to_instagram",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "Đăng bài lên Instagram qua API Graph",
        "Input/Tham số": "ig_user_id, access_token, image_url, caption",
        "Output/Kết quả trả về": "Kết quả API (dict)"
    },
    {
        "Tên hàm": "upload_image_to_cloudinary",
        "Vị trí": "Đầu file",
        "Mô tả chức năng": "Upload ảnh lên Cloudinary, trả về link public",
        "Input/Tham số": "image_bytes, preset",
        "Output/Kết quả trả về": "Link ảnh public"
    }
]

# Sheet 2: Tabs
tabs = [
    {
        "Tên tab": "tab1",
        "Tiêu đề UI": "📝 Tạo nội dung",
        "Mô tả chức năng chính": "Tạo bài đăng mới, sinh caption AI, upload ảnh, lên lịch đăng, lưu bài chờ duyệt",
        "Các bước xử lý chính/Logic": "Nhập liệu → Sinh caption → Upload ảnh → Lưu lịch/bài",
        "Hàm sử dụng chính": "generate_caption, upload_image_to_gdrive, upload_image_to_cloudinary, save_posts"
    },
    {
        "Tên tab": "tab3",
        "Tiêu đề UI": "📊 Hiệu quả",
        "Mô tả chức năng chính": "Lấy dữ liệu bài viết Facebook, thống kê, hiển thị bảng, biểu đồ tương tác",
        "Các bước xử lý chính/Logic": "Lấy API FB → Tổng hợp → Hiển thị bảng/biểu đồ",
        "Hàm sử dụng chính": "fetch_facebook_posts, fetch_post_stats (nội bộ tab)"
    },
    {
        "Tên tab": "tab2",
        "Tiêu đề UI": "🔮 Dự báo",
        "Mô tả chức năng chính": "Dự báo hiệu quả bài viết mới dựa trên caption, thời gian, dữ liệu lịch sử, AI phân tích",
        "Các bước xử lý chính/Logic": "Nhập caption → Lấy dữ liệu → Gọi AI → Hiển thị dự báo",
        "Hàm sử dụng chính": "generate_caption, fetch_facebook_posts, fetch_post_stats (nội bộ tab)"
    },
    {
        "Tên tab": "tab4",
        "Tiêu đề UI": "🎯 Gợi ý chiến lược",
        "Mô tả chức năng chính": "Gợi ý cải thiện nội dung, thời gian, nền tảng dựa trên dữ liệu thực tế, AI sinh gợi ý",
        "Các bước xử lý chính/Logic": "Lấy dữ liệu → Gọi AI → Hiển thị gợi ý",
        "Hàm sử dụng chính": "beautify_ai_output, fetch_facebook_posts, fetch_post_stats (nội bộ tab)"
    },
    {
        "Tên tab": "tab5",
        "Tiêu đề UI": "📥 Bài chờ duyệt",
        "Mô tả chức năng chính": "Quản lý, duyệt/xóa các bài viết chờ duyệt, xuất danh sách, thao tác với file posts_data.json",
        "Các bước xử lý chính/Logic": "Đọc file → Hiển thị → Duyệt/Xóa → Lưu lại",
        "Hàm sử dụng chính": "load_posts, save_posts"
    }
]

# Tạo file Excel
with pd.ExcelWriter("mo_ta_app.xlsx", engine="openpyxl") as writer:
    pd.DataFrame(functions).to_excel(writer, sheet_name="Functions", index=False)
    pd.DataFrame(tabs).to_excel(writer, sheet_name="Tabs", index=False)

print("✅ Đã tạo file mo_ta_app.xlsx mô tả chức năng app.py!")