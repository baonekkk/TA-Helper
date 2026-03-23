import streamlit as st
from drive_logic import get_all_classes_from_drive
from modules.main_tab import render_main_tab
from modules.calendar_tab import render_calendar_tab
from widget.widget import render_class_widget

st.set_page_config(layout="wide")
st.title("Hệ thống Hỗ trợ TA")

# Lấy dữ liệu lớp học trực tiếp từ Google Drive khi mới load trang
if "data_classes" not in st.session_state:
    st.session_state.data_classes = get_all_classes_from_drive()

active_classes = [c for c in st.session_state.data_classes if c.get("status", "active") == "active"]
archived_classes = [c for c in st.session_state.data_classes if c.get("status") == "archived"]
deleted_classes = [c for c in st.session_state.data_classes if c.get("status") == "deleted"]

# Khôi phục Tab Lịch tổng vào danh sách
tab_main, tab_calendar, tab_archive, tab_trash, tab_settings = st.tabs([
    "Lớp học", 
    "Lịch tổng",
    "Lưu trữ", 
    "Thùng rác", 
    "Cài đặt"
])

with tab_main:
    render_main_tab(active_classes)

with tab_calendar:
    render_calendar_tab(active_classes)

with tab_archive:
    if not archived_classes: 
        st.write("Chưa có lớp học nào được lưu trữ.")
    else:
        col_l, col_r = st.columns(2)
        for i, cls in enumerate(archived_classes):
            if i % 2 == 0:
                with col_l: render_class_widget(cls["name"], cls["next_date"], cls["id"])
            else:
                with col_r: render_class_widget(cls["name"], cls["next_date"], cls["id"])

with tab_trash:
    if not deleted_classes: 
        st.write("Thùng rác đang trống.")
    else:
        col_l, col_r = st.columns(2)
        for i, cls in enumerate(deleted_classes):
            if i % 2 == 0:
                with col_l: render_class_widget(cls["name"], cls["next_date"], cls["id"])
            else:
                with col_r: render_class_widget(cls["name"], cls["next_date"], cls["id"])

with tab_settings:
    st.write("Bạn có thể đổi giao diện Sáng/Tối bằng cách nhấn vào menu (dấu 3 chấm) ở góc trên bên phải màn hình -> Settings -> Theme.")