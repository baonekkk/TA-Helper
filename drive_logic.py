import streamlit as st
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import json
from datetime import datetime, timedelta

# SCOPES cho Drive và Calendar
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar'
]

def _get_creds():
    """Hàm phụ trợ để lấy credentials từ secrets."""
    creds_data = st.secrets["GOOGLE_APPLICATION_CREDENTIALS"]
    if isinstance(creds_data, str):
        try:
            creds_dict = json.loads(creds_data)
            return service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except ValueError:
            return service_account.Credentials.from_service_account_file(creds_data, scopes=SCOPES)
    else:
        creds_dict = dict(creds_data)
        return service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

@st.cache_resource
def get_drive_service():
    """Khởi tạo và trả về đối tượng kết nối Google Drive API."""
    creds = _get_creds()
    return build('drive', 'v3', credentials=creds, cache_discovery=False)

@st.cache_resource
def get_calendar_service():
    """Khởi tạo và trả về đối tượng kết nối Google Calendar API."""
    creds = _get_creds()
    return build('calendar', 'v3', credentials=creds, cache_discovery=False)

def get_or_create_folder(service, folder_name, parent_id):
    """Tìm kiếm thư mục theo tên và ID cha, nếu không có thì tạo mới."""
    query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(
        q=query, 
        spaces='drive', 
        fields='files(id, name)',
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute(num_retries=3)
    
    items = results.get('files', [])
    
    if not items:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(
            body=file_metadata, 
            fields='id',
            supportsAllDrives=True
        ).execute(num_retries=3)
        st.cache_data.clear()
        return folder.get('id')
    else:
        return items[0].get('id')

def initialize_class_structure(class_name):
    """Tạo cấu trúc thư mục chuẩn cho lớp học mới và trả về bộ ID."""
    service = get_drive_service()
    root_folder_id = st.secrets["GOOGLE_DRIVE_FOLDER_ID"]
    
    class_folder_id = get_or_create_folder(service, class_name, root_folder_id)
    
    query_sub = f"'{class_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res_sub = service.files().list(
        q=query_sub, 
        spaces='drive', 
        fields='files(id, name)',
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute(num_retries=3)
    existing_subs = {f['name']: f['id'] for f in res_sub.get('files', [])}
    
    subfolders = ["Reminders", "Danh Sách Lớp", "Lịch", "Khác"]
    folder_ids = {"root_class_id": class_folder_id}
    
    for sub in subfolders:
        if sub in existing_subs:
            sub_id = existing_subs[sub]
        else:
            file_metadata = {
                'name': sub,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [class_folder_id]
            }
            sub_folder = service.files().create(
                body=file_metadata, 
                fields='id', 
                supportsAllDrives=True
            ).execute(num_retries=3)
            sub_id = sub_folder.get('id')
            st.cache_data.clear()
        
        folder_ids[sub] = sub_id
        raw_id = get_or_create_folder(service, "raw data", sub_id)
        folder_ids[f"{sub}_raw"] = raw_id
        
    return folder_ids

def upload_file_to_drive(file_stream, file_name, mime_type, parent_folder_id):
    """Tải một file từ bộ nhớ tạm của Streamlit lên Google Drive."""
    service = get_drive_service()
    file_metadata = {
        'name': file_name,
        'parents': [parent_folder_id]
    }
    media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)
    uploaded_file = service.files().create(
        body=file_metadata, 
        media_body=media, 
        fields='id',
        supportsAllDrives=True
    ).execute(num_retries=3)
    st.cache_data.clear()
    return uploaded_file.get('id')

@st.cache_data
def list_files_in_folder(parent_folder_id):
    """Liệt kê tất cả thư mục và tệp tin trong một thư mục cụ thể."""
    service = get_drive_service()
    query = f"'{parent_folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name, mimeType)',
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute(num_retries=3)
    return results.get('files', [])

def delete_file_from_drive(file_id):
    """Xóa vĩnh viễn tệp tin/thư mục khỏi Google Drive."""
    service = get_drive_service()
    service.files().delete(
        fileId=file_id, 
        supportsAllDrives=True
    ).execute(num_retries=3)
    st.cache_data.clear()

def set_class_status_file(class_folder_id, status):
    """Tạo hoặc xóa file báo hiệu trạng thái nằm trong thư mục lớp học."""
    service = get_drive_service()
    query = f"'{class_folder_id}' in parents and name contains 'STATUS_' and trashed=false"
    results = service.files().list(
        q=query, 
        spaces='drive', 
        fields='files(id)', 
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute(num_retries=3)
    
    for f in results.get('files', []):
        service.files().delete(fileId=f['id'], supportsAllDrives=True).execute(num_retries=3)
        
    if status in ['archived', 'deleted']:
        file_metadata = {
            'name': f'STATUS_{status.upper()}',
            'parents': [class_folder_id]
        }
        media = MediaIoBaseUpload(io.BytesIO(status.encode('utf-8')), mimetype='text/plain', resumable=True)
        service.files().create(
            body=file_metadata, 
            media_body=media,
            fields='id', 
            supportsAllDrives=True
        ).execute(num_retries=3)
    st.cache_data.clear()

@st.cache_data
def get_all_classes_from_drive():
    """Lấy danh sách các lớp học và đọc file báo hiệu để xác định trạng thái."""
    service = get_drive_service()
    root_id = st.secrets["GOOGLE_DRIVE_FOLDER_ID"]
    
    query_folders = f"'{root_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res_folders = service.files().list(
        q=query_folders, 
        spaces='drive', 
        fields='files(id, name)',
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute(num_retries=3)
    folders = res_folders.get('files', [])
    
    query_status = "name contains 'STATUS_' and trashed=false"
    try:
        res_status = service.files().list(
            q=query_status, 
            spaces='drive', 
            fields='files(name, parents)',
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            corpora='allDrives'
        ).execute(num_retries=3)
    except Exception:
        res_status = service.files().list(
            q=query_status, 
            spaces='drive', 
            fields='files(name, parents)',
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute(num_retries=3)
        
    status_files = res_status.get('files', [])
    status_map = {}
    for sf in status_files:
        if sf.get('parents'):
            parent_id = sf['parents'][0]
            if sf['name'] == 'STATUS_ARCHIVED':
                status_map[parent_id] = 'archived'
            elif sf['name'] == 'STATUS_DELETED':
                status_map[parent_id] = 'deleted'
                
    classes = []
    for item in folders:
        folder_id = item['id']
        status = status_map.get(folder_id, 'active')
        classes.append({
            "id": folder_id,
            "name": item['name'],
            "next_date": "Chưa có",
            "status": status
        })
    return classes

@st.cache_data
def download_file_from_drive(file_id):
    """Tải nội dung file từ Google Drive về bộ nhớ một cách an toàn."""
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk(num_retries=3)
    return fh.getvalue()

def push_to_google_calendar(events, target_calendar_id='baonguyentu02@gmail.com'):
    """Đẩy sự kiện với reminders.useDefault=False theo đúng tài liệu Google."""
    service = get_calendar_service()
    
    for ev in events:
        start_iso = ev['start']
        end_iso = ev['end']
        props = ev.get('extendedProps', {})
        is_exam = props.get('is_exam', False)
        
        # Làm sạch chuỗi thời gian ISO
        if '+' not in start_iso: start_iso = f"{start_iso}+07:00"
        if '+' not in end_iso: end_iso = f"{end_iso}+07:00"

        # 1. Xây dựng Checklist nhiệm vụ
        normal_task = "CHECKLIST NHIỆM VỤ:\n1. Gửi reminder cho lớp"
        exam_task = "CHECKLIST NGÀY THI:\n1. Gọi điện hỏi Quản lý lớp Kiểm tra đề thi\n2. Chuẩn bị dụng cụ, phòng ốc"
        
        description = normal_task
        if is_exam:
            description = f"{exam_task}\n\n{normal_task}"
        
        content = props.get('content', '')
        if content:
            description = f"NỘI DUNG HỌC:\n{content}\n\n{description}"

        # 2. Thiết lập Reminders theo đúng hướng dẫn Google bạn đưa
        reminders_overrides = []
        if is_exam:
            reminders_overrides.append({'method': 'popup', 'minutes': 1440}) # 1 ngày
        
        reminders_overrides.extend([
            {'method': 'popup', 'minutes': 60}, # 1 tiếng
            {'method': 'popup', 'minutes': 30}  # 30 phút
        ])

        event_body = {
            'summary': ev['title'],
            'description': description,
            'start': {'dateTime': start_iso, 'timeZone': 'Asia/Ho_Chi_Minh'},
            'end': {'dateTime': end_iso, 'timeZone': 'Asia/Ho_Chi_Minh'},
            'reminders': {
                'useDefault': False, 
                'overrides': reminders_overrides 
            },
        }
        
        try:
            service.events().insert(calendarId=target_calendar_id, body=event_body).execute(num_retries=3)
        except Exception as e:
            st.error(f"Lỗi khi đẩy sự kiện {ev['title']}: {e}")