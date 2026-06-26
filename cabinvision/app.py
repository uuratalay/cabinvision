# app.py -- Streamlit Cloud giriş noktası
# gate_dashboard zaten sys.path'i kendi ayarlıyor, bu dosya sadece
# Streamlit Cloud'un "Main file path" olarak göstereceği wrapper.
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# gate_dashboard'u doğrudan import ediyoruz --
# Streamlit tüm st.* komutlarını çalıştıracak
import dashboard.gate.gate_dashboard  # noqa
