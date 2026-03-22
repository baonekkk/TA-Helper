import streamlit as st
import replicate
import os
import json
import base64
import tempfile # Thư viện mới thêm vào để tạo file vật lý
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

# --- HÀM BACKEND 1: GOOGLE CALENDAR ---
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

# --- HÀM BACKEND 2: GEMINI 2.5 OCR (LƯU FILE VẬT LÝ) ---
def call_gemini_25_json(uploaded_file, class_name):
    """Lưu ảnh thành file vật lý trên server để đảm bảo Replicate đọc được 100%"""
    
    prompt = f"""
    Bạn là một robot OCR chuyên nghiệp. Hãy đọc ảnh hồ sơ lớp {class_name} đính kèm và trích xuất thông tin.
    
    QUY TẮC:
    1. Chỉ bóc tách thông tin có thực trong ảnh. Nếu không thấy, để null.
    2. 'Ngày học' định dạng YYYY-MM-DD.
    3. Trả về duy nhất mã JSON, không giải thích.

    JSON FORMAT:
    {{
      "class_list": [
        {{ "Tên học sinh": "...", "Gender": "...", "DOB": "...", "Tên Phụ Huynh": "...", "SĐT": "...", "Địa Chỉ": "..." }}
      ],
      "class_schedule": [
        {{ "Tên bài": "...", "Ngày học": "..." }}
      ]
    }}
    """
    
    tmp_file_path = None
    try:
        # 1. Tạo một file tạm vật lý trên ổ cứng của server
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(uploaded_file.getvalue()) # Ghi dữ liệu từ RAM xuống ổ cứng
            tmp_file_path = tmp_file.name

        # 2. Mở file vật lý đó ra và gửi cho Replicate
        with open(tmp_file_path, "rb") as image_file:
            output = replicate.run(
                GEMINI_MODEL,
                input={
                    "image": image_file, 
                    "prompt": prompt, 
                    "temperature": 0.0
                }
            )
            
        full_res = "".join(output).strip()
        clean_json = full_res.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
        
    except Exception as e:
        st.error(f"Lỗi truyền tải ảnh hoặc AI: {str(e)}")
        return None
    finally:
        # 3. Dọn rác: Xóa file tạm sau khi dùng xong để giải phóng bộ nhớ
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

# --- GIAO DIỆN ---
@st.dialog("Quản lý hồ sơ lớp học", width="large")
def class_details_dialog(class_name):
    st.markdown(f"### 🏫 Hồ sơ lớp: {class_name}")
    col_up, col_res = st.columns([0.4, 0.6])
    with col_up:
        uploaded_file = st.file_uploader("Tải ảnh folder", type=["jpg", "png", "jpeg"], key=f"up_{class_name}")
        if uploaded_file:
            st.image(uploaded_file, use_container_width=True)
            if st.button("🔮 Trích xuất dữ liệu (Gemini 2.5)", type="primary", key=f"run_{class_name}"):
                with st.spinner("AI đang nhìn ảnh..."):
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
                    if sync_to_google_calendar(schedule, class_name): st.success("Đồng bộ thành công!")
        else: st.info("Dữ liệu sẽ xuất hiện tại đây.")

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