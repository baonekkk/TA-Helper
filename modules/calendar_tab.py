import streamlit as st
import pandas as pd
import json
import re
from datetime import datetime, timedelta
from streamlit_calendar import calendar
from drive_logic import initialize_class_structure, list_files_in_folder, download_file_from_drive, push_to_google_calendar
from widget.widget_details import is_holiday, show_event_details

def render_calendar_tab(active_classes):
    st.write("### Lịch Dạy Tổng Quan")
    
    if st.button("Đồng bộ dữ liệu toàn bộ lớp học", key="sync_all_classes", width='stretch'):
        with st.spinner("Đang tải dữ liệu từ Drive..."):
            for cls in active_classes:
                class_id, class_name = cls["id"], cls["name"]
                info_key, cal_key = f"class_info_df_{class_id}", f"json_data_{class_id}_Lịch"
                
                if info_key not in st.session_state or cal_key not in st.session_state:
                    fids = initialize_class_structure(class_name)
                    if info_key not in st.session_state:
                        raw_id = fids["Khác_raw"]
                        f_info = next((f for f in list_files_in_folder(raw_id) if f['name'] == 'class_info.json'), None)
                        if f_info: 
                            st.session_state[info_key] = pd.DataFrame(json.loads(download_file_from_drive(f_info['id']).decode('utf-8')))
                        else: 
                            st.session_state[info_key] = pd.DataFrame([{"Hạng mục": h, "Thông tin": ""} for h in ["Tên Quản lý", "Sđt Quản lý", "Phòng học", "Buổi 1: Thứ (Thứ 3-CN)", "Buổi 1: Bắt đầu (HH:mm)", "Buổi 1: Kết thúc (HH:mm)", "Buổi 2: Thứ (Thứ 3-CN)", "Buổi 2: Bắt đầu (HH:mm)", "Buổi 2: Kết thúc (HH:mm)"]])
                    
                    if cal_key not in st.session_state:
                        raw_id = fids["Lịch_raw"]
                        json_files = sorted([f for f in list_files_in_folder(raw_id) if f['name'].endswith('.json') and f['name'] != 'class_info.json'], key=lambda x: x['name'])
                        all_dfs = []
                        for f in json_files:
                            try:
                                data = json.loads(download_file_from_drive(f['id']).decode('utf-8').replace('```json', '').replace('```', '').strip())
                                p_data = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [data])
                                df_p = pd.DataFrame(p_data)
                                df_p.columns = [re.sub(r'_+', '_', re.sub(r'[^a-z0-9_]', '_', str(c).lower().strip())) for c in df_p.columns]
                                if "actual_date" in df_p.columns: 
                                    df_p["actual_date"] = pd.to_datetime(df_p["actual_date"].astype(str) + f"-{datetime.now().year}", format="%d-%b-%Y", errors='coerce').dt.strftime('%d/%m/%Y')
                                all_dfs.append(df_p)
                            except: continue
                        if all_dfs:
                            m_df = pd.concat(all_dfs, ignore_index=True)
                            if "class" in m_df.columns: 
                                m_df["class"] = pd.to_numeric(m_df["class"], errors='coerce'); m_df = m_df.sort_values(by="class").reset_index(drop=True)
                            st.session_state[cal_key] = [{"label": "Toàn bộ lịch học", "df": m_df}]
                        else: st.session_state[cal_key] = []
            st.success("Đồng bộ xong!")

    events = []
    day_map = {"thứ 2": 0, "thứ 3": 1, "thứ 4": 2, "thứ 5": 3, "thứ 6": 4, "thứ 7": 5, "chủ nhật": 6}
    now = datetime.now()
    check_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    check_end = (check_start + timedelta(days=6)).replace(hour=23, minute=59, second=59)

    for cls in active_classes:
        class_id, class_name = cls["id"], cls["name"]
        info_key, cal_key = f"class_info_df_{class_id}", f"json_data_{class_id}_Lịch"
        
        if info_key in st.session_state:
            info_df = st.session_state[info_key]
            info_map = {str(row["Hạng mục"]): str(row["Thông tin"]).strip() for _, row in info_df.iterrows()}
            phong_hoc = info_map.get("Phòng học", "Chưa xác định")
            config = {
                "b1_wday": day_map.get(info_map.get("Buổi 1: Thứ (Thứ 3-CN)", "").lower(), -1),
                "b1_start": info_map.get("Buổi 1: Bắt đầu (HH:mm)", ""),
                "b1_end": info_map.get("Buổi 1: Kết thúc (HH:mm)", ""),
                "b2_wday": day_map.get(info_map.get("Buổi 2: Thứ (Thứ 3-CN)", "").lower(), -1),
                "b2_start": info_map.get("Buổi 2: Bắt đầu (HH:mm)", ""),
                "b2_end": info_map.get("Buổi 2: Kết thúc (HH:mm)", "")
            }

            if cal_key in st.session_state and st.session_state[cal_key]:
                merged_df = st.session_state[cal_key][0]["df"]
                for _, row in merged_df.iterrows():
                    if pd.isna(row.get("actual_date")): continue
                    try:
                        date_obj = datetime.strptime(row["actual_date"], "%d/%m/%Y")
                        if check_start <= date_obj <= check_end:
                            wday = date_obj.weekday()
                            st_t, en_t = "", ""
                            if wday == config["b1_wday"]: st_t, en_t = config["b1_start"], config["b1_end"]
                            elif wday == config["b2_wday"]: st_t, en_t = config["b2_start"], config["b2_end"]
                            if st_t and en_t:
                                content = str(row.get('course_book_page_unit', ''))
                                is_ex = any(kw in content.lower() for kw in ['test', 'exam', 'thi', 'kiểm tra'])
                                events.append({"title": f"{class_name} ({phong_hoc})", "start": f"{date_obj.strftime('%Y-%m-%d')}T{st_t}:00", "end": f"{date_obj.strftime('%Y-%m-%d')}T{en_t}:00", "extendedProps": {"content": content, "is_exam": is_ex}})
                    except: continue
            
            elif config["b1_wday"] != -1 or config["b2_wday"] != -1:
                curr = check_start
                while curr <= check_end:
                    wday = curr.weekday()
                    st_t, en_t = "", ""
                    if wday == config["b1_wday"]: st_t, en_t = config["b1_start"], config["b1_end"]
                    elif wday == config["b2_wday"]: st_t, en_t = config["b2_start"], config["b2_end"]
                    if st_t and en_t and not is_holiday(curr):
                        events.append({"title": f"{class_name} ({phong_hoc})", "start": f"{curr.strftime('%Y-%m-%d')}T{st_t}:00", "end": f"{curr.strftime('%Y-%m-%d')}T{en_t}:00", "extendedProps": {"content": "Lịch tự động tuần này", "is_exam": False}})
                    curr += timedelta(days=1)

    if events and st.button("Đẩy danh sách tuần này lên Google Calendar API", type="primary", use_container_width=True):
        with st.spinner("Đang đồng bộ..."):
            try:
                # Thay đổi email thành email cá nhân của bạn
                push_to_google_calendar(events, target_calendar_id='baonguyentu02@gmail.com')
                st.success(f"Đã đẩy thành công {len(events)} buổi học vào lịch cá nhân!")
            except Exception as e: st.error(f"Lỗi API: {e}")

    cal_options = {"headerToolbar": {"left": "today prev,next", "center": "title", "right": "timeGridWeek,dayGridMonth"}, "initialView": "timeGridWeek", "firstDay": 1, "slotMinTime": "08:00:00", "slotMaxTime": "22:00:00", "slotDuration": "00:15:00", "slotLabelInterval": "01:00:00", "allDaySlot": False, "height": "auto", "contentHeight": 450, "aspectRatio": 2.2, "expandRows": False}
    state = calendar(events=events, options=cal_options, key="global_calendar")
    if state.get("callback") == "eventClick": show_event_details(state["eventClick"]["event"])