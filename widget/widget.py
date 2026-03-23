import streamlit as st
from .widget_logic import change_class_status, permanently_delete_class
from .widget_details import render_class_details

def render_class_widget(class_name, next_schedule, class_id):
    """Hàm vẽ giao diện thẻ lớp học và các nút tương tác."""
    status = "active"
    if "data_classes" in st.session_state:
        for c in st.session_state.data_classes:
            if c["id"] == class_id:
                status = c.get("status", "active")
                break

    with st.container(border=True):
        st.markdown(f"### **{class_name}**")
        st.write(f"Lịch học kế tiếp: {next_schedule}")
        st.write("")
        
        if st.button("Xem chi tiết lớp học", key=f"btn_{class_id}", width='stretch'):
            render_class_details(class_name, class_id)
            
        if status == "active":
            col1, col2 = st.columns(2)
            
            with col1:
                if not st.session_state.get(f"confirm_arc_{class_id}", False):
                    if st.button("Lưu trữ", key=f"arc_{class_id}", width='stretch'):
                        st.session_state[f"confirm_arc_{class_id}"] = True
                        st.session_state[f"confirm_del_{class_id}"] = False
                        st.rerun()
                else:
                    st.write("Chắc chắn?")
                    c_yes, c_no = st.columns(2)
                    if c_yes.button("Có", key=f"y_arc_{class_id}"):
                        change_class_status(class_id, "archived")
                    if c_no.button("Hủy", key=f"n_arc_{class_id}"):
                        st.session_state[f"confirm_arc_{class_id}"] = False
                        st.rerun()
                        
            with col2:
                if not st.session_state.get(f"confirm_del_{class_id}", False):
                    if st.button("Xóa", key=f"del_{class_id}", width='stretch'):
                        st.session_state[f"confirm_del_{class_id}"] = True
                        st.session_state[f"confirm_arc_{class_id}"] = False
                        st.rerun()
                else:
                    st.write("Chắc chắn?")
                    c_yes, c_no = st.columns(2)
                    if c_yes.button("Có", key=f"y_del_{class_id}"):
                        change_class_status(class_id, "deleted")
                    if c_no.button("Hủy", key=f"n_del_{class_id}"):
                        st.session_state[f"confirm_del_{class_id}"] = False
                        st.rerun()
        elif status == "archived":
            if st.button("Khôi phục", key=f"res_{class_id}", width='stretch'):
                change_class_status(class_id, "active")
        elif status == "deleted":
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Khôi phục", key=f"res_{class_id}", width='stretch'):
                    change_class_status(class_id, "active")
            with col2:
                if st.button("Xóa vĩnh viễn", key=f"perm_del_{class_id}", width='stretch'):
                    permanently_delete_class(class_id)