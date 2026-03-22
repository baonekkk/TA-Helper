import streamlit as st
import replicate
import os
import json

# --- CẤU HÌNH BẢO MẬT ---
# Streamlit sẽ tự tìm trong st.secrets hoặc biến môi trường hệ thống
if "REPLICATE_API_TOKEN" in st.secrets:
    os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]
else:
    st.error("Cảnh báo: Không tìm thấy REPLICATE_API_TOKEN trong Secrets. Vui lòng cấu hình lại.")

# Cập nhật model ID chính xác
GEMINI_MODEL = "google/gemini-2.5-flash"

st.set_page_config(page_title="TA Helper AI", layout="wide")

# --- HÀM BACKEND: TRÍCH XUẤT JSON ---
def call_gemini_json_ocr(uploaded_file, class_name):
    """Gửi ảnh qua Replicate, yêu cầu Gemini 2.5 Flash trả về cấu trúc JSON chính xác"""
    
    prompt = f"""
    Bạn là một trợ lý AI chuyên bóc tách dữ liệu giáo dục. Hãy đọc ảnh folder lớp {class_name} và trả về một đối tượng JSON duy nhất có cấu trúc sau:
    {{
      "class_list": [
        {{
          "Tên học sinh": "...",
          "Gender": "...",
          "DOB": "...",
          "Tên Phụ Huynh": "...",
          "SĐT": "...",
          "Địa Chỉ": "..."
        }}
      ],
      "class_schedule": [
        {{
          "Tên bài": "...",
          "Ngày học": "..."
        }}
      ]
    }}
    Lưu ý: 
    - Nếu không tìm thấy thông tin nào, hãy để giá trị là null.
    - Chỉ trả về duy nhất mã JSON, không kèm lời giải giải thích hay ký tự markdown (như ```json).
    """

    try:
        output = replicate.run(
            GEMINI_MODEL,
            input={
                "image": uploaded_file,
                "prompt": prompt,
                "temperature": 0.1
            }
        )
        
        full_response = "".join(output).strip()
        clean_json = full_response.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)

    except Exception as e:
        st.error(f"Lỗi khi gọi AI: {str(e)}")
        return None


# --- GIAO DIỆN WIDGET LỚN (DIALOG CHI TIẾT) ---
@st.dialog("Quản lý hồ sơ lớp học", width="large")
def class_details_dialog(class_name):
    st.markdown(f"### 🏫 Hồ sơ lớp: {class_name}")
    st.divider()
    
    col_up, col_res = st.columns([0.4, 0.6])

    with col_up:
        st.markdown("#### 1. Tải ảnh folder")
        uploaded_file = st.file_uploader(
            f"Chụp/Tải ảnh hồ sơ lớp {class_name}", 
            type=["jpg", "jpeg", "png"], 
            key=f"dialog_upload_{class_name}"
        )
        
        if uploaded_file is not None:
            st.image(uploaded_file, use_container_width=True)
            if st.button(f"🔮 Trích xuất JSON (Gemini 2.5)", key=f"ai_btn_{class_name}", type="primary"):
                with st.spinner("Gemini 2.5 Flash đang xử lý dữ liệu..."):
                    result = call_gemini_json_ocr(uploaded_file, class_name)
                    if result:
                        st.session_state[f"ai_result_{class_name}"] = result
                        st.success("Đã trích xuất xong!")

    with col_res:
        st.markdown("#### 2. Dữ liệu hệ thống (JSON)")
        saved_result = st.session_state.get(f"ai_result_{class_name}")
        
        if saved_result:
            tab1, tab2 = st.tabs(["📋 Danh sách lớp", "📅 Lịch lớp"])
            with tab1:
                st.json(saved_result.get("class_list", []))
            with tab2:
                st.json(saved_result.get("class_schedule", []))
        else:
            st.info("Dữ liệu sau khi trích xuất sẽ hiển thị tại đây.")


# --- WIDGET NHỎ (MÀN HÌNH CHÍNH) ---
def create_class_widget(class_name):
    with st.container(border=True):
        col_info, col_btn = st.columns([0.85, 0.15], vertical_alignment="center")
        with col_info:
            st.markdown(f"**{class_name}**", unsafe_allow_html=True)
        with col_btn:
            if st.button("⛶", key=f"btn_{class_name}"):
                class_details_dialog(class_name)
        
        if f"ai_result_{class_name}" in st.session_state:
            st.caption("✅ Đã trích xuất JSON (2.5)")
        else:
            st.caption("⚪ Chờ dữ liệu")
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)


# --- GIAO DIỆN CHÍNH ---
st.title("TA Helper AI")

st.header("📅 Lịch trình tổng quan")
with st.container(border=True):
    st.info("Khu vực hiển thị Google Calendar")
    st.markdown("<div style='height: 100px; background-color: rgba(128,128,128,0.1); border-radius: 10px;'></div>", unsafe_allow_html=True)

st.divider()
st.header("📂 Danh sách hồ sơ lớp học")

list_classes = ["402-PP-4B-S3", "440-PP-2B-S3", "348-IX-1A-S3", "341-PP-2A-S3"]
cols = st.columns(3)

for i, class_name in enumerate(list_classes):
    with cols[i % 3]:
        create_class_widget(class_name)