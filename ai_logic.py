import streamlit as st
import replicate
import base64
import os

def get_replicate_client():
    """Khởi tạo client Replicate với token từ secrets.toml."""
    os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]
    return replicate.Client(api_token=st.secrets["REPLICATE_API_TOKEN"])

def process_image_ocr(image_bytes, mime_type, prompt="Hãy trích xuất thông tin từ ảnh này và trả về định dạng JSON nguyên bản."):
    """
    Sử dụng Google Gemini 2.5 Flash trên Replicate để thực hiện OCR và trả về JSON.
    """
    client = get_replicate_client()
    
    # Chuyển đổi byte ảnh sang Base64 Data URI
    base64_data = base64.b64encode(image_bytes).decode('utf-8')
    image_uri = f"data:{mime_type};base64,{base64_data}"
    
    # Cấu trúc input: Ép định dạng snake_case tuyệt đối cho keys
    input_data = {
        "images": [image_uri],
        "prompt": f"{prompt} Lưu ý: Chỉ trả về chuỗi JSON, không thêm văn bản giải thích. Các khóa (keys) trong JSON bắt buộc phải sử dụng chữ viết thường và dấu gạch dưới (_), không được chứa dấu cách hay bất kỳ ký hiệu đặc biệt nào khác."
    }
    
    try:
        # Gọi model google/gemini-2.5-flash
        output = client.run(
            "google/gemini-2.5-flash",
            input=input_data
        )
        
        # Nối các phần tử trong output thành chuỗi văn bản hoàn chỉnh
        result_text = "".join(output)
        return result_text
        
    except Exception as e:
        return f"Lỗi xử lý AI: {e}"