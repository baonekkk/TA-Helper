import streamlit as st
import replicate
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CẤU HÌNH BẢO MẬT & MODEL ---
# Đảm bảo bạn đã dán REPLICATE_API_TOKEN vào Streamlit Secrets
if "REPLICATE_API_TOKEN" in st.secrets:
    os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]

GEMINI_MODEL = "google/gemini-2.5-flash"

st.set_page_config(page_title="TA Helper AI", layout="wide")

# --- KHỞI TẠO SESSION STATE ---
if "list_classes" not in st.session_state:
    st.session_state.list_classes = ["402-PP-4B-S3", "440-PP-2B-S3", "348-IX-1A-S3", "341-PP-2A-S3"]

# --- HÀM BACKEND 1: GOOGLE CALENDAR ---
def sync_to_google_calendar(events_list, class_name):
    """Đẩy danh sách lịch học lên Google Calendar thông qua Service Account"""
    try:
        # Đọc credentials từ Streamlit Secrets
        info = json.loads(st.secrets["GOOGLE_APPLICATION_CREDENTIALS"])
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/calendar']
        )
        service = build('calendar', 'v3', credentials=creds)

        for item in events_list:
            event = {
                'summary': f"[{class_name}] {item.get('Tên bài', 'Học phần mới')}",
                'description': f'Tự động tạo từ TA Helper cho lớp {class_name}',
                'start': {
                    'date': item.get('Ngày học'), # Yêu cầu Gemini trả về YYYY-MM-DD
                    'timeZone': 'Asia/Ho_Chi_Minh',
                },
                'end': {
                    'date': item.get('Ngày học'),
                    'timeZone': 'Asia/Ho_Chi_Minh',
                },
            }
            # 'primary' ở đây là lịch mà Service Account đã được chia sẻ quyền (Bước 5 hướng dẫn trước)
            service.events().insert(calendarId='primary', body=event).execute()
        return True
    except Exception as e:
        st.error(f"Lỗi đồng bộ Calendar: {str(e)}")
        return False

# --- HÀM BACKEND 2: GEMINI 2.5 FLASH OCR ---
def call_gemini_25_json(uploaded_file, class_name):
    """Sử dụng Gemini 2.5 Flash để bóc tách folder lớp học vật lý sang JSON"""
    prompt = f"""
    Bạn là trợ lý AI chuyên nghiệp cho giáo vụ. Hãy đọc ảnh hồ sơ lớp {class_name} và trả về JSON:
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
          "Ngày học": "YYYY-MM-DD" 
        }}
      ]
    }}
    Lưu ý quan trọng: 
    - Trường 'Ngày học' BẮT BUỘC phải là định dạng YYYY-MM-DD.
    - Nếu không thấy thông tin, để null. Chỉ trả về mã JSON, không giải thích.
    """
    try:
        output = replicate.run(
            GEMINI_MODEL,
            input={"image": uploaded_file, "prompt": prompt, "temperature": 0.1}
        )
        full_res = "".join(output).strip()
        clean_json = full_res.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"Lỗi AI Gemini 2.5: {str(e)}")
        return None

# --- WIDGET CHI TIẾT (DIALOG) ---
@st.dialog("Quản lý hồ sơ lớp học", width="large")
def class_details_dialog(class_name):
    st.markdown(f"### 🏫 Hồ sơ lớp: {class_name}")
    st.divider()
    
    col_up, col_res = st.columns([0.4, 0.6])

    with col_up:
        st.markdown("**1. Tiếp nhận tài liệu**")
        uploaded_file = st.file_uploader("Chụp/Tải ảnh folder", type=["jpg", "png", "jpeg"], key=f"up_{class_name}")
        if uploaded_file:
            st.image(uploaded_file, use_container_width=True)
            if st.button("🔮 Trích xuất dữ liệu (Gemini 2.5)", type="primary", key=f"run_ai_{class_name}"):
                with st.spinner("Đang bóc tách dữ liệu..."):
                    result = call_gemini_25_json(uploaded_file, class_name)
                    if result:
                        st.session_state[f"ai_result_{class_name}"] = result
                        st.success("Trích xuất thành công!")

    with col_res:
        st.markdown("**2. Dữ liệu trích xuất**")
        data = st.session_state.get(f"ai_result_{class_name}")
        if data:
            tab1, tab2 = st.tabs(["📋 Danh sách học sinh", "📅 Lịch học tập"])
            with tab1:
                st.dataframe(data.get("class_list", []), use_container_width=True)
            with tab2:
                schedule = data.get("class_schedule", [])
                st.table(schedule)
                if st.button("🚀 Đồng bộ lên Google Calendar", key=f"sync_{class_name}"):
                    with st.spinner("Đang đẩy lịch lên Google..."):
                        if sync_to_google_calendar(schedule, class_name):
                            st.success("Lịch đã được đồng bộ vào điện thoại của bạn!")
        else:
            st.info("Vui lòng tải ảnh và nhấn trích xuất để xem dữ liệu.")

# --- WIDGET NHỎ TRÊN DASHBOARD ---
def create_class_widget(class_name):
    with st.container(border=True):
        col_t, col_b = st.columns([0.85, 0.15], vertical_alignment="center")
        col_t.markdown(f"**{class_name}**")
        if col_b.button("⛶", key=f"open_{class_name}"):
            class_details_dialog(class_name)
        
        # Hiển thị trạng thái nhỏ gọn bên dưới
        if f"ai_result_{class_name}" in st.session_state:
            st.caption("✅ Hồ sơ đã sẵn sàng")
        else:
            st.caption("⚪ Chờ cập nhật tài liệu")
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# --- GIAO DIỆN CHÍNH ---
st.title("TA Helper AI")

# --- SIDEBAR: THÊM LỚP ---
with st.sidebar:
    st.header("⚙️ Quản lý lớp")
    with st.form("add_class_form", clear_on_submit=True):
        new_class_name = st.text_input("Tên lớp mới:")
        submit_add = st.form_submit_button("➕ Thêm lớp học")
        if submit_add and new_class_name:
            if new_class_name not in st.session_state.list_classes:
                st.session_state.list_classes.append(new_class_name)
                st.rerun()
            else:
                st.warning("Lớp này đã tồn tại.")

# --- PHẦN 1: LỊCH TỔNG QUAN ---
st.header("📅 Lịch trình tổng quan")
with st.container(border=True):
    # Sau khi đồng bộ, bạn có thể nhúng link public của Google Calendar vào đây
    st.info("Dữ liệu sau khi đồng bộ sẽ xuất hiện trên Google Calendar cá nhân của bạn.")
    st.markdown("<div style='height: 100px; background-color: rgba(128,128,128,0.05); border-radius: 8px;'></div>", unsafe_allow_html=True)

st.divider()

# --- PHẦN 2: DANH SÁCH LỚP HỌC ---
st.header("📂 Danh sách lớp học")
cols = st.columns(3)
for i, class_name in enumerate(st.session_state.list_classes):
    with cols[i % 3]:
        create_class_widget(class_name)