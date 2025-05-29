import requests

def post_caption_to_facebook(page_id, access_token, caption):
    url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
    data = {
        "message": caption,
        "access_token": access_token
    }
    response = requests.post(url, data=data)
    return response.json()

# ✅ THÔNG TIN ĐÃ GẮN
page_id = "2076435142631541"
access_token = "EAAbHPY5s4I4BO4lcMP4spMukwjZCmNdt0twbIGVdHAqUY6Q4OYThmtoFbOqx2tCw3yyZB8fKEnbxQbIAiNc7hvvzO4mVZBLnCpIOHvjaRRvpx9DbQjSUSWtPexZC1j812CZCu5DF6OFZB1sHmVSivK8cb9TvxGFmlJMgQKsF0zAsS0zdNZCbenZCaOZBnt2hZCw5zF0HrK"
caption = "🌿 Đây là bài đăng thử nghiệm với caption duy nhất. Không có ảnh, nhưng vẫn mang thông điệp của #xuongbinhgom 💚"

# 📤 GỬI BÀI
result = post_caption_to_facebook(page_id, access_token, caption)
print(result)
