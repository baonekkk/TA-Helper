import streamlit as st
import replicate
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CẤU HÌNH BẢO MẬT & MODEL ---
if "REPLICATE_API_TOKEN" in st.secrets:
    os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]

GEMINI_MODEL = "google/gemini-2.5-flash"

st.set_page_config(page_title="TA Helper AI", layout="wide")

# --- KHỞI TẠO SESSION STATE ---
if "list_classes" not in st.session_state:
    st.session_state.list_classes = ["402-PP-4B-S3", "440-PP-2B-S3", "348-IX-1A-S3", "341-PP-2A-S3"]

# --- HÀM BACKEND 1: GOOGLE CALENDAR (Giữ nguyên) ---
def sync_to_google_calendar(events_list, class_name):
    try:
        info = json.loads(st.secrets["GOOGLE_APPLICATION_CREDENTIALS"])
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/calendar']
        )
        service = build('calendar', 'v3', credentials=creds)
        for item in events_list:
            if not item.get('Ngày học'): continue
            event = {
                'summary': f"[{class_name}] {item.get('Tên bài', 'Học phần mới')}",
                'start': {'date': item.get('Ngày học'), 'timeZone': 'Asia/Ho_Chi_Minh'},
                'end': {'date': item.get('Ngày học'), 'timeZone': 'Asia/Ho_Chi_Minh'},
            }
            service.events().insert(calendarId='primary', body=event).execute()
        return True
    except Exception as e:
        st.error(f"Lỗi Calendar: {str(e)}"); return False

# --- HÀM BACKEND 2: GEMINI 2.5 OCR (TỐI ƯU PROMPT) ---
def call_gemini_25_json(uploaded_file, class_name):
    """Sử dụng Gemini 2.5 Flash với Prompt khắt khe để tránh hallucination"""
    
    # PROMPT MỚI, KHẮT KHE HƠN CŨ 10 LẦN
    prompt = f"""
    Bạn là một robot OCR chuyên nghiệp, chỉ làm việc với sự thật trích xuất được từ hình ảnh. 
    Nhiệm vụ của bạn là bóc tách dữ liệu từ ảnh folder lớp {class_name} và chuyển đổi sang JSON.

    --- QUY TẮC BẮT BUỘC ---
    1. Tuyệt đối KHÔNG ĐƯỢC BỊA ĐẶT thông tin. Chỉ bóc tách những gì bạn nhìn thấy CHẮC CHẮN.
    2. Nếu một trường thông tin (ví dụ: DOB, Địa Chỉ) không có trong ảnh hoặc bạn không đọc được, bạn PHẢI để giá trị là null. KHÔNG ĐƯỢC đoán.
    3. Trường 'Ngày học' PHẢI có định dạng YYYY-MM-DD. Nếu không thấy năm, giả định là năm 2026.
    4. Chỉ trả về duy nhất mã JSON hợp lệ. Không lời chào, không markdown.

    --- ĐẦU RA MONG MUỐN (JSON FORMAT) ---
    {{
      "class_list": [
        {{ "Tên học sinh": "...", "Gender": "...", "DOB": "YYYY-MM-DD hoặc null", "Tên Phụ Huynh": "...", "SĐT": "...", "Địa Chỉ": "..." }}
      ],
      "class_schedule": [
        {{ "Tên bài": "...", "Ngày học": "YYYY-MM-DD" }}
      ]
    }}
    """
    try:
        # Replicate hỗ trợ truyền trực tiếp file object
        output = replicate.run(
            GEMINI_MODEL,
            input={"image": uploaded_file, "prompt": prompt, "temperature": 0.0} # Temperature=0 để AI lỳ lợm nhất, ít sáng tạo nhất
        )
        full_res = "".join(output).strip()
        clean_json = full_res.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"Lỗi AI: {str(e)}"); return None

# --- GIAO DIỆN (Giữ nguyên logic cũ) ---
@st.dialog("Quản lý hồ sơ lớp học", width="large")
def class_details_dialog(class_name):
    st.markdown(f"### 🏫 Hồ sơ lớp: {class_name}")
    col_up, col_res = st.columns([0.4, 0.6])
    with col_up:
        uploaded_file = st.file_uploader("Tải ảnh folder", type=["jpg", "png", "jpeg"], key=f"up_{class_name}")
        if uploaded_file:
            st.image(uploaded_file, use_container_width=True)
            if st.button("🔮 Trích xuất dữ liệu (Gemini 2.5)", type="primary", key=f"run_{class_name}"):
                with st.spinner("AI đang bóc tách..."):
                    result = call_gemini_25_json(uploaded_file, class_name)
                    if result: st.session_state[f"ai_result_{class_name}"] = result
    with col_res:
        data = st.session_state.get(f"ai_result_{class_name}")
        if data:
            t1, t2 = st.tabs(["📋 Danh sách", "📅 Lịch"])
            t1.dataframe(data.get("class_list", []), use_container_width=True)
            with t2:
                schedule = data.get("class_schedule", [])
                st.table(schedule)
                if st.button("🚀 Đồng bộ Google Calendar", key=f"sync_{class_name}"):
                    if sync_to_google_calendar(schedule, class_name): st.success("Đã đồng bộ lịch!")
        else: st.info("Chờ trích xuất...")

def create_class_widget(class_name):
    with st.container(border=True):
        col_t, col_b = st.columns([0.85, 0.15])
        col_t.markdown(f"**{class_name}**")
        if col_b.button("⛶", key=f"open_{class_name}"): class_details_dialog(class_name)
        status = "✅ Đã trích xuất" if f"ai_result_{class_name}" in st.session_state else "⚪ Chờ dữ liệu"
        st.caption(status)

st.title("TA Helper AI")
with st.sidebar:
    st.header("⚙️ Quản lý lớp")
    with st.form("add_class_form", clear_on_submit=True):
        new_class_name = st.text_input("Tên lớp mới:")
        if st.form_submit_button("➕ Thêm lớp") and new_class_name:
            if new_class_name not in st.session_state.list_classes:
                st.session_state.list_classes.append(new_class_name); st.rerun()

st.header("📅 Lịch trình tổng quan")
with st.container(border=True):
    st.info("Khu vực hiển thị Google Calendar")
    st.markdown("<div style='height: 100px; background-color: rgba(128,128,128,0.05); border-radius: 8px;'></div>", unsafe_allow_html=True)

st.divider()
st.header("📂 Danh sách lớp học")
cols = st.columns(3)
for i, class_name in enumerate(st.session_state.list_classes):
    with cols[i % 3]: create_class_widget(class_name)