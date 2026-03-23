import streamlit as st
import io
import json
import pandas as pd
from datetime import datetime, timedelta
from drive_logic import list_files_in_folder, download_file_from_drive, delete_file_from_drive, upload_file_to_drive

def render_task_checklist(class_id, folder_ids, info_df, df_cal):
    now = datetime.now()
    target_date = now
    exam_week = False
    
    future_dates = [datetime.strptime(d_str, "%d/%m/%Y") for d_str in df_cal["actual_date"].dropna() if datetime.strptime(d_str, "%d/%m/%Y").date() >= now.date()]
    if future_dates: target_date = min(future_dates)
    
    start_w = target_date - timedelta(days=target_date.weekday())
    end_w = start_w + timedelta(days=6)
    for _, r in df_cal.iterrows():
        if pd.notna(r.get("actual_date")):
            rd = datetime.strptime(r["actual_date"], "%d/%m/%Y")
            if start_w.date() <= rd.date() <= end_w.date():
                if any(kw in str(r.get("course_book_page_unit", "")).lower() for kw in ['test', 'exam', 'thi', 'kiểm tra']):
                    exam_week = True; break

    target_date_str = target_date.strftime("%d/%m/%Y")
    done_fn = f"DONE_{target_date.strftime('%Y%m%d')}.json"
    khac_raw_id = folder_ids["Khác_raw"]
    
    # Tải dữ liệu cũ nếu đã tồn tại để điền vào form
    all_files_khac = list_files_in_folder(khac_raw_id)
    done_file = next((f for f in all_files_khac if f['name'] == done_fn), None)
    saved_data = None
    if done_file:
        saved_data = json.loads(download_file_from_drive(done_file['id']).decode('utf-8'))
        st.success(f"Dữ liệu cho ngày {target_date_str} đã được lưu. Bạn vẫn có thể điều chỉnh bên dưới.")

    # Logic cảnh báo nếu quá giờ học mà chưa hoàn thành
    info_map = {row["Hạng mục"]: row["Thông tin"] for _, row in info_df.iterrows()}
    day_map_rev = {0: "Thứ 2", 1: "Thứ 3", 2: "Thứ 4", 3: "Thứ 5", 4: "Thứ 6", 5: "Thứ 7", 6: "Chủ Nhật"}
    target_wday_str = day_map_rev.get(target_date.weekday())
    
    end_time_str = ""
    if target_wday_str == info_map.get("Buổi 1: Thứ (Thứ 3-CN)"):
        end_time_str = info_map.get("Buổi 1: Kết thúc (HH:mm)")
    elif target_wday_str == info_map.get("Buổi 2: Thứ (Thứ 3-CN)"):
        end_time_str = info_map.get("Buổi 2: Kết thúc (HH:mm)")
    
    if end_time_str and not done_file:
        h_end, m_end = map(int, end_time_str.split(':'))
        class_end_dt = target_date.replace(hour=h_end, minute=m_end, second=0, microsecond=0)
        if now > class_end_dt:
            st.error(f"⚠️ **CẢNH BÁO:** Buổi học ngày {target_date_str} đã kết thúc nhưng checklist chưa được xác nhận!")

    st.write(f"📌 **Nhiệm vụ cho buổi học: {target_date_str}**")
    with st.form(key=f"task_form_{class_id}"):
        c1 = st.checkbox("1. Tới lớp sớm 15p mở lớp", value=saved_data['tasks'][0] if saved_data else False)
        c2 = st.checkbox("2. Gửi reminder cho ít nhất 1 tuần", value=saved_data['tasks'][1] if saved_data else False)
        st.write("*Hồ sơ lớp:*")
        c3 = st.checkbox("3. Điểm danh học viên", value=saved_data['tasks'][2] if saved_data else False)
        c4 = st.checkbox("4. Lấy chữ ký GV", value=saved_data['tasks'][3] if saved_data else False)
        c5 = st.checkbox("5. Chép điểm bài tập", value=saved_data['tasks'][4] if saved_data else False)
        c6 = st.checkbox("6. Check từ vựng", value=saved_data['tasks'][5] if saved_data else False)
        st.write("*Truyền thông:*")
        c7 = st.checkbox("7. Đăng reminder group lớp", value=saved_data['tasks'][6] if saved_data else False)
        c8 = st.checkbox("8. Ghi chú group TA", value=saved_data['tasks'][7] if saved_data else False)
        
        c9, c10 = False, False
        if exam_week:
            st.info("⚠️ Tuần này có lịch thi/ôn tập.")
            c9 = st.checkbox("9. Kiểm tra đề thi", value=saved_data['tasks'][8] if saved_data else False)
            c10 = st.checkbox("10. Kiểm tra dụng cụ", value=saved_data['tasks'][9] if saved_data else False)
        
        if st.form_submit_button("Xác nhận / Cập nhật buổi học", width='stretch'):
            if done_file:
                delete_file_from_drive(done_file['id'])
            
            data = {"date": target_date_str, "tasks": [c1,c2,c3,c4,c5,c6,c7,c8,c9,c10]}
            upload_file_to_drive(io.BytesIO(json.dumps(data, ensure_ascii=False).encode('utf-8')), done_fn, "application/json", khac_raw_id)
            st.success("Đã cập nhật nhiệm vụ thành công.")