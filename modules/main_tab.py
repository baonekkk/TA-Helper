import streamlit as st
from widget.widget import render_class_widget
from drive_logic import get_all_classes_from_drive, initialize_class_structure

def render_main_tab(active_classes):
    col_add, col_empty = st.columns([1, 2])
    with col_add:
        new_class_name = st.text_input("Thêm lớp học mới", key="new_class_input")
        if st.button("Thêm lớp", width='stretch'):
            if new_class_name:
                initialize_class_structure(new_class_name)
                st.session_state.data_classes = get_all_classes_from_drive()
                st.rerun()
    
    st.write("---")

    col_left, col_right = st.columns(2)
    for i, cls in enumerate(active_classes):
        if i % 2 == 0:
            with col_left:
                render_class_widget(cls["name"], cls["next_date"], cls["id"])
        else:
            with col_right:
                render_class_widget(cls["name"], cls["next_date"], cls["id"])