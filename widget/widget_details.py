import streamlit as st
import io
import os
import json
import pandas as pd
import re
from datetime import datetime, timedelta
from drive_logic import initialize_class_structure, upload_file_to_drive, list_files_in_folder, delete_file_from_drive, download_file_from_drive
from ai_logic import process_image_ocr
from utils.date_utils import is_holiday
from widget.components.task_checklist import render_task_checklist

@st.dialog("Chi tiết buổi học")
def show_event_details(event_info):
    props = event_info.get('extendedProps', {})
    is_exam = props.get('is_exam', False)
    
    start_t = event_info['start'][11:16]
    end_t = event_info['end'][11:16]
    
    st.write(f"### **{event_info['title']}**")
    st.write(f"**Thời gian:** {start_t} - {end_t}")
    st.write("---")
    
    st.write("**Nội dung bài học:**")
    st.write(props.get('content', 'Không có dữ liệu'))
    
    st.write("**Nhiệm vụ chuẩn bị:**")
    if is_exam:
        st.write("1. Gọi điện hỏi Quản lý lớp Kiểm tra đề thi")
        st.write("2. Chuẩn bị dụng cụ, phòng ốc")
    else:
        st.write("1. Gửi reminder cho lớp")

def refresh_file_cache(class_name, folder_choice, class_id):
    folder_ids_key = f"folder_ids_{class_id}"
    if folder_ids_key not in st.session_state:
        st.session_state[folder_ids_key] = initialize_class_structure(class_name)
    folder_ids = st.session_state[folder_ids_key]
    
    target_folder_id = folder_ids[folder_choice]
    target_raw_folder_id = folder_ids[f"{folder_choice}_raw"]
    files_main = list_files_in_folder(target_folder_id)
    files_raw = list_files_in_folder(target_raw_folder_id)
    all_items = files_main + files_raw
    st.session_state[f"file_cache_{class_id}_{folder_choice}"] = [f for f in all_items if f['mimeType'] != 'application/vnd.google-apps.folder']

def load_and_display_json_data(class_name, folder_choice, class_id):
    cache_key = f"json_data_{class_id}_{folder_choice}"
    folder_ids_key = f"folder_ids_{class_id}"
    
    col_title, col_ref = st.columns([3, 1])
    with col_title: st.write(f"**Dữ liệu từ {folder_choice}:**")
    
    if cache_key in st.session_state:
        with col_ref:
            if st.button("Làm mới ↻", key=f"ref_json_{class_id}_{folder_choice}"):
                del st.session_state[cache_key]
                st.rerun()
                
    if cache_key not in st.session_state:
        if st.button(f"Tải dữ liệu {folder_choice}", key=f"load_btn_json_{class_id}_{folder_choice}", width='stretch'):
            if folder_ids_key not in st.session_state:
                st.session_state[folder_ids_key] = initialize_class_structure(class_name)
            folder_ids = st.session_state[folder_ids_key]
            
            target_raw_id = folder_ids[f"{folder_choice}_raw"]
            json_files = sorted([f for f in list_files_in_folder(target_raw_id) if f['name'].endswith('.json') and f['name'] != 'class_info.json'], key=lambda x: x['name'])
            all_dfs, pages_list = [], []
            
            for i, f in enumerate(json_files):
                try:
                    data = json.loads(download_file_from_drive(f['id']).decode('utf-8').replace('```json', '').replace('```', '').strip())
                    page_data = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [data])
                    df_page = pd.DataFrame(page_data)
                    df_page.columns = [re.sub(r'_+', '_', re.sub(r'[^a-z0-9_]', '_', str(c).lower().strip())) for c in df_page.columns]
                    if folder_choice == "Lịch" and "actual_date" in df_page.columns:
                        df_page["actual_date"] = pd.to_datetime(df_page["actual_date"].astype(str) + f"-{datetime.now().year}", format="%d-%b-%Y", errors='coerce').dt.strftime('%d/%m/%Y')
                    all_dfs.append(df_page)
                    pages_list.append({"label": f"Trang {i+1}", "df": df_page})
                except: continue
                
            if folder_choice == "Lịch" and all_dfs:
                merged_df = pd.concat(all_dfs, ignore_index=True)
                if "class" in merged_df.columns:
                    merged_df["class"] = pd.to_numeric(merged_df["class"], errors='coerce')
                    merged_df = merged_df.sort_values(by="class").reset_index(drop=True)
                info_df = st.session_state.get(f"class_info_df_{class_id}")
                if info_df is not None:
                    day_map = {"Thứ 3": 1, "Thứ 4": 2, "Thứ 5": 3, "Thứ 6": 4, "Thứ 7": 5, "Chủ Nhật": 6}
                    target_wdays = [day_map[str(r["Thông tin"]).strip()] for _, r in info_df.iterrows() if "Thứ" in str(r["Hạng mục"]) and str(r["Thông tin"]).strip() in day_map]
                    last_idx = merged_df[merged_df["actual_date"].notna()].index.max()
                    if pd.notna(last_idx) and target_wdays:
                        curr_dt = datetime.strptime(merged_df.loc[last_idx, "actual_date"], '%d/%m/%Y')
                        for idx in range(last_idx + 1, len(merged_df)):
                            while True:
                                curr_dt += timedelta(days=1)
                                if curr_dt.weekday() in target_wdays and not is_holiday(curr_dt): break
                            merged_df.loc[idx, "actual_date"] = curr_dt.strftime('%d/%m/%Y')
                st.session_state[cache_key] = [{"label": "Toàn bộ lịch học", "df": merged_df}]
            else: 
                st.session_state[cache_key] = pages_list
            st.rerun()
        return
        
    pages = st.session_state[cache_key]
    if len(pages) > 1:
        sel = st.radio("Chọn trang:", options=[p["label"] for p in pages], horizontal=True, key=f"p_sel_{class_id}_{folder_choice}")
        st.dataframe(next(p for p in pages if p["label"] == sel)["df"], width='stretch')
    else: 
        if pages: st.dataframe(pages[0]["df"], width='stretch')
        else: st.write("Dữ liệu trống.")

def preload_class_data(class_name, class_id):
    info_key = f"class_info_df_{class_id}"
    calendar_key = f"json_data_{class_id}_Lịch"
    folder_ids_key = f"folder_ids_{class_id}"
    
    if folder_ids_key not in st.session_state:
        st.session_state[folder_ids_key] = initialize_class_structure(class_name)
    folder_ids = st.session_state[folder_ids_key]
    
    if info_key not in st.session_state:
        raw_id = folder_ids["Khác_raw"]
        f_info = next((f for f in list_files_in_folder(raw_id) if f['name'] == 'class_info.json'), None)
        if f_info: 
            st.session_state[info_key] = pd.DataFrame(json.loads(download_file_from_drive(f_info['id']).decode('utf-8')))
        else: 
            st.session_state[info_key] = pd.DataFrame([{"Hạng mục": h, "Thông tin": ""} for h in ["Tên Quản lý", "Sđt Quản lý", "Phòng học", "Buổi 1: Thứ (Thứ 3-CN)", "Buổi 1: Bắt đầu (HH:mm)", "Buổi 1: Kết thúc (HH:mm)", "Buổi 2: Thứ (Thứ 3-CN)", "Buổi 2: Bắt đầu (HH:mm)", "Buổi 2: Kết thúc (HH:mm)"]])

    if calendar_key not in st.session_state:
        target_raw_id = folder_ids["Lịch_raw"]
        json_files = sorted([f for f in list_files_in_folder(target_raw_id) if f['name'].endswith('.json') and f['name'] != 'class_info.json'], key=lambda x: x['name'])
        all_dfs = []
        for f in json_files:
            try:
                data = json.loads(download_file_from_drive(f['id']).decode('utf-8').replace('```json', '').replace('```', '').strip())
                page_data = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [data])
                df_page = pd.DataFrame(page_data)
                df_page.columns = [re.sub(r'_+', '_', re.sub(r'[^a-z0-9_]', '_', str(c).lower().strip())) for c in df_page.columns]
                if "actual_date" in df_page.columns:
                    df_page["actual_date"] = pd.to_datetime(df_page["actual_date"].astype(str) + f"-{datetime.now().year}", format="%d-%b-%Y", errors='coerce').dt.strftime('%d/%m/%Y')
                all_dfs.append(df_page)
            except: continue
        if all_dfs:
            merged_df = pd.concat(all_dfs, ignore_index=True)
            if "class" in merged_df.columns:
                merged_df["class"] = pd.to_numeric(merged_df["class"], errors='coerce')
                merged_df = merged_df.sort_values(by="class").reset_index(drop=True)
            info_df = st.session_state.get(info_key)
            if info_df is not None:
                day_map = {"Thứ 3": 1, "Thứ 4": 2, "Thứ 5": 3, "Thứ 6": 4, "Thứ 7": 5, "Chủ Nhật": 6}
                target_wdays = [day_map[str(r["Thông tin"]).strip()] for _, r in info_df.iterrows() if "Thứ" in str(r["Hạng mục"]) and str(r["Thông tin"]).strip() in day_map]
                last_idx = merged_df[merged_df["actual_date"].notna()].index.max()
                if pd.notna(last_idx) and target_wdays:
                    curr_dt = datetime.strptime(merged_df.loc[last_idx, "actual_date"], '%d/%m/%Y')
                    for idx in range(last_idx + 1, len(merged_df)):
                        while True:
                            curr_dt += timedelta(days=1)
                            if curr_dt.weekday() in target_wdays and not is_holiday(curr_dt): break
                        merged_df.loc[idx, "actual_date"] = curr_dt.strftime('%d/%m/%Y')
            st.session_state[calendar_key] = [{"label": "Toàn bộ lịch học", "df": merged_df}]
        else:
            st.session_state[calendar_key] = []

@st.dialog("Chi tiết lớp học")
def render_class_details(class_name, class_id):
    st.markdown(f"## **{class_name}**")
    
    info_key = f"class_info_df_{class_id}"
    calendar_key = f"json_data_{class_id}_Lịch"
    folder_ids_key = f"folder_ids_{class_id}"
    
    if folder_ids_key not in st.session_state or info_key not in st.session_state or calendar_key not in st.session_state:
        preload_class_data(class_name, class_id)
            
    folder_ids = st.session_state.get(folder_ids_key, {})

    t1, t2, t3, t4, t5 = st.tabs(["Checklist nhiệm vụ", "Danh Sách Lớp", "Lịch Học", "Thông tin khác", "Quản lý File"])

    with t1:
        info_df = st.session_state.get(info_key)
        has_info = info_df is not None and not (info_df["Thông tin"] == "").all()
        has_calendar = calendar_key in st.session_state and len(st.session_state[calendar_key]) > 0

        if not has_info or not has_calendar:
            st.warning("⚠️ **Thiếu dữ liệu vận hành**")
            if not has_info and not has_calendar:
                st.info("Vui lòng sang tab **Quản lý File** để tải lên ảnh Lịch học và Danh sách lớp.")
            else:
                st.info("Vui lòng kiểm tra lại tab **Lịch Học** và **Thông tin Khác** để đảm bảo dữ liệu đã được nhập đầy đủ.")
        else:
            render_task_checklist(class_id, folder_ids, info_df, st.session_state[calendar_key][0]["df"])

    with t2: load_and_display_json_data(class_name, "Danh Sách Lớp", class_id)
    with t3: load_and_display_json_data(class_name, "Lịch", class_id)
    with t4:
        up_df = st.data_editor(st.session_state[info_key], width='stretch', hide_index=True, key=f"ed_{class_id}", disabled=["Hạng mục"])
        if st.button("Lưu thông tin", key=f"sv_{class_id}", width='stretch'):
            t_p = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
            v_d = ["thứ 3", "thứ 4", "thứ 5", "thứ 6", "thứ 7", "chủ nhật"]
            
            valid = True
            for _, r in up_df.iterrows():
                val = str(r["Thông tin"]).strip()
                item = r["Hạng mục"]
                
                if "HH:mm" in item and val and not re.match(t_p, val):
                    valid = False; break
                if "Thứ (Thứ 3-CN)" in item and val and val.lower() not in v_d:
                    valid = False; break
            
            if valid:
                raw_id = folder_ids["Khác_raw"]
                for f in list_files_in_folder(raw_id): 
                    if f['name'] == 'class_info.json': delete_file_from_drive(f['id'])
                upload_file_to_drive(io.BytesIO(json.dumps(up_df.to_dict(orient='records'), ensure_ascii=False).encode('utf-8')), "class_info.json", "application/json", raw_id)
                st.session_state[info_key] = up_df; st.success("Đã lưu.")
            else: st.error("Dữ liệu sai định dạng (kiểm tra lại Thứ hoặc Giờ HH:mm).")

    with t5:
        cur_f = st.selectbox("Thư mục:", ["Reminders", "Danh Sách Lớp", "Lịch", "Khác"], key=f"f_sel_{class_id}")
        up_fs = st.file_uploader("Tải tệp:", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_{class_id}")
        
        if up_fs and st.button("Tải lên & Quét AI", width='stretch'):
            for f in up_fs:
                upload_file_to_drive(f, f.name, f.type, folder_ids[cur_f])
                res = process_image_ocr(f.getvalue(), f.type)
                upload_file_to_drive(io.BytesIO(res.encode('utf-8')), f"ocr_{os.path.splitext(f.name)[0]}.json", "application/json", folder_ids[f"{cur_f}_raw"])
            st.success("Xong.")
            refresh_file_cache(class_name, cur_f, class_id)
            st.rerun()
            
        if f"file_cache_{class_id}_{cur_f}" not in st.session_state: 
            refresh_file_cache(class_name, cur_f, class_id)
            
        fs = st.session_state[f"file_cache_{class_id}_{cur_f}"]
        
        sel_del = [f['id'] for f in fs if st.checkbox(f['name'], key=f"del_{f['id']}")]; 
        if sel_del and st.button("Xóa", type="primary"):
            for fid in sel_del: delete_file_from_drive(fid)
            refresh_file_cache(class_name, cur_f, class_id)
            st.rerun()