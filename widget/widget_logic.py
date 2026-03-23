import streamlit as st
from drive_logic import set_class_status_file, delete_file_from_drive

def change_class_status(class_id, new_status):
    """Hàm thay đổi trạng thái của lớp học."""
    # Cập nhật bằng file báo hiệu trên Google Drive để lưu vĩnh viễn
    set_class_status_file(class_id, new_status)
    
    # Cập nhật session_state để giao diện đổi ngay lập tức
    if "data_classes" in st.session_state:
        for c in st.session_state.data_classes:
            if c["id"] == class_id:
                c["status"] = new_status
                
    if f"confirm_arc_{class_id}" in st.session_state:
        st.session_state[f"confirm_arc_{class_id}"] = False
    if f"confirm_del_{class_id}" in st.session_state:
        st.session_state[f"confirm_del_{class_id}"] = False
    st.rerun()

def permanently_delete_class(class_id):
    """Hàm xóa vĩnh viễn lớp học."""
    # Xóa thư mục gốc của lớp học trên Google Drive
    delete_file_from_drive(class_id)
    
    # Cập nhật giao diện
    if "data_classes" in st.session_state:
        st.session_state.data_classes = [c for c in st.session_state.data_classes if c["id"] != class_id]
    st.rerun()