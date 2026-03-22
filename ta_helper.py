import streamlit as st
import replicate
import os
import json
import tempfile
import gspread
import pandas as pd # Thêm thư viện để xử lý bảng đẹp
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

# --- CẤU HÌNH HỆ THỐNG ---
if "REPLICATE_API_TOKEN" in st.secrets:
    os.environ["REPLICATE_API_TOKEN"] = st.secrets["REPLICATE_API_TOKEN"]

GEMINI_MODEL = "google/gemini-2.5-flash"
SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID")
DRIVE_FOLDER_ID = st.secrets.get("GOOGLE_DRIVE_FOLDER_ID")

st.set_page_config(page_title="TA Helper AI", layout="wide")

# --- QUẢN LÝ XÁC THỰC GOOGLE ---
def get_google_creds():
    info = json.loads(st.secrets["GOOGLE_APPLICATION_CREDENTIALS"])
    return service_account.Credentials.from_service_account_info(
        info, scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/calendar'
        ]
    )

# --- XỬ LÝ GOOGLE DRIVE ---
def upload_to_drive(file_path, file_name):
    try:
        creds = get_google_creds()
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaFileUpload(file_path, mimetype='image/jpeg')
        file = service.files().create(
            body=file_metadata, media_body=media, fields='id', supportsAllDrives=True 
        ).execute()
        return file.get('id')
    except Exception as e:
        st.error(f"Lỗi Drive Upload: {str(e)}"); return None

def download_from_drive(file_id):
    try:
        creds = get_google_creds()
        service = build('drive', 'v3', credentials=creds)
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return fh.getvalue()
    except: return None

# --- XỬ LÝ GOOGLE SHEETS ---
def save_all_to_db(class_name, data_json, image_id=None):
    try:
        creds = get_google_creds()
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        cell = sheet.find(class_name)
        if cell:
            if data_json: sheet.update_cell(cell.row, 2, json.dumps(data_json, ensure_ascii=False))
            if image_id: sheet.update_cell(cell.row, 3, image_id)
        else:
            sheet.append_row([class_name, json.dumps(data_json, ensure_ascii=False), image_id])
    except Exception as e:
        st.error(f"Lỗi lưu Sheets: {str(e)}")

def load_db_to_session():
    try:
        creds = get_google_creds()
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        records = sheet.get_all_records()
        for row in records:
            name = str(row.get('class_name'))
            if name:
                if row.get('data'):
                    st.session_state[f"ai_result_{name}"] = json.loads(row.get('data'))
                st.session_state[f"img_id_{name}"] = row.get('image_id')
                if name not in st.session_state.list_classes:
                    st.session_state.list_classes.append(name)
    except: pass

# --- KHỞI TẠO DỮ LIỆU ---
if "list_classes" not in st.session_state:
    st.session_state.list_classes = []
    load_db_to_session()
    if not st.session_state.list_classes:
        st.session_state.list_classes = ["402-PP-4B-S3", "440-PP-2B-S3", "348-IX-1A-S3", "341-PP-2A-S3"]

# --- XỬ LÝ GOOGLE CALENDAR ---
def sync_to_google_calendar(events_list, class_name):
    try:
        creds = get_google_creds()
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

# --- HÀM AI OCR ---
def call_gemini_25_json(uploaded_file, class_name):
    prompt = f"Robot OCR: Trích xuất JSON (class_list, class_schedule YYYY-MM-DD) từ ảnh folder lớp {class_name}. Không giải thích."
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(uploaded_file.getvalue()); tmp_path = tmp.name
        img_id = upload_to_drive(tmp_path, f"{class_name}_folder.jpg")
        with open(tmp_path, "rb") as img:
            output = replicate.run(GEMINI_MODEL, input={"images": [img], "prompt": prompt, "temperature": 0.0})
        res_text = "".join(output).strip().replace("```json", "").replace("```", "")
        result = json.loads(res_text)
        save_all_to_db(class_name, result, img_id)
        st.session_state[f"img_id_{class_name}"] = img_id
        return result
    except Exception as e:
        st.error(f"Lỗi AI: {str(e)}"); return None
    finally:
        if tmp_path and os.path.exists(tmp_path): os.remove(tmp_path)

# --- GIAO DIỆN CHI TIẾT (PHẦN CẬP NHẬT GIAO DIỆN ĐẸP) ---
@st.dialog("Quản lý hồ sơ lớp học", width="large")
def class_details_dialog(class_name):
    st.markdown(f"### 🏫 Hồ sơ lớp: {class_name}")
    col_up, col_res = st.columns([0.35, 0.65])
    
    with col_up:
        saved_img_id = st.session_state.get(f"img_id_{class_name}")
        if saved_img_id:
            img_bytes = download_from_drive(saved_img_id)
            if img_bytes: st.image(img_bytes, caption="📸 Ảnh hồ sơ gốc", use_container_width=True)
        
        uploaded_file = st.file_uploader("Cập nhật ảnh folder mới", type=["jpg", "png", "jpeg"], key=f"up_{class_name}")
        if uploaded_file and st.button("🔮 Trích xuất & Lưu trữ", type="primary", key=f"run_{class_name}"):
            with st.spinner("AI đang bóc tách dữ liệu..."):
                result = call_gemini_25_json(uploaded_file, class_name)
                if result: 
                    st.session_state[f"ai_result_{class_name}"] = result
                    st.rerun()

    with col_res:
        data = st.session_state.get(f"ai_result_{class_name}")
        if data:
            # Hiển thị tóm tắt nhanh bằng metrics
            student_list = data.get("class_list", [])
            schedule_list = data.get("class_schedule", [])
            
            m1, m2 = st.columns(2)
            m1.metric("Sĩ số", f"{len(student_list)} HS")
            m2.metric("Số buổi học", f"{len(schedule_list)} buổi")
            
            t1, t2 = st.tabs(["📋 Danh sách học sinh", "📅 Lịch học tập"])
            
            with t1:
                if student_list:
                    df_students = pd.DataFrame(student_list)
                    # Đổi tên cột cho đẹp
                    df_students = df_students.rename(columns={
                        "student_name": "Họ và Tên",
                        "gender": "Giới tính",
                        "dob": "Ngày sinh",
                        "contact_name": "Phụ huynh",
                        "mobile_phone": "SĐT Liên hệ",
                        "student_code": "Mã HS",
                        "no": "STT"
                    })
                    st.dataframe(df_students, use_container_width=True, hide_index=True)
                else:
                    st.warning("Chưa có danh sách học sinh.")

            with t2:
                if schedule_list:
                    df_schedule = pd.DataFrame(schedule_list)
                    df_schedule = df_schedule.rename(columns={
                        "Tên bài": "Nội dung bài học",
                        "Ngày học": "Thời gian"
                    })
                    st.table(df_schedule)
                    if st.button("🚀 Đồng bộ lên Google Calendar", key=f"sync_{class_name}"):
                        if sync_to_google_calendar(schedule_list, class_name):
                            st.success("Đã đồng bộ vào điện thoại!")
                else:
                    st.warning("Chưa có lịch học.")
        else:
            st.info("Vui lòng tải ảnh lên để AI trích xuất thông tin lớp học.")

# --- GIAO DIỆN CHÍNH ---
st.title("TA Helper AI")

with st.sidebar:
    st.header("⚙️ Quản lý")
    with st.form("add_class", clear_on_submit=True):
        new_name = st.text_input("Tên lớp mới:")
        if st.form_submit_button("➕ Thêm lớp") and new_name:
            if new_name not in st.session_state.list_classes:
                st.session_state.list_classes.append(new_name)
                save_all_to_db(new_name, {})
                st.rerun()

st.header("📂 Danh sách lớp học")
cols = st.columns(3)
for i, class_name in enumerate(st.session_state.list_classes):
    with cols[i % 3]:
        with st.container(border=True):
            c1, c2 = st.columns([0.8, 0.2])
            c1.markdown(f"**{class_name}**")
            if c2.button("⛶", key=f"btn_{class_name}"):
                class_details_dialog(class_name)
            
            is_saved = f"img_id_{class_name}" in st.session_state and st.session_state[f"img_id_{class_name}"]
            st.caption("✅ Dữ liệu hoàn tất" if is_saved else "⚪ Chờ cập nhật")