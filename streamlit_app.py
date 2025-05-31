import streamlit as st

st.title("我的第一个 Streamlit 应用")
st.write("你好，Streamlit！")

name = st.text_input("输入你的名字")
if name:
    st.write(f"你好，{name}！")