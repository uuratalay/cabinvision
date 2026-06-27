import streamlit as st

st.set_page_config(
    page_title="CabinVision",
    page_icon="✈",
    layout="wide",
)

st.markdown("""
<style>
.stApp{background:#0d1117;color:#f0f4f8}
</style>
""", unsafe_allow_html=True)

st.title("✈ CabinVision")
st.subheader("AI-Powered Cabin Baggage Management System")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.info("### 🖥️ Gate Monitor\nGate personeli için gerçek zamanlı kabin doluluk takibi ve aksiyon önerileri.\n\n← Soldaki menüden **Gate Monitor**'ü seç.")

with col2:
    st.info("### 🏢 Operations Center\nTüm terminal genelinde gate durumlarını izle, kritik uyarıları yönet.\n\n← Soldaki menüden **Operations Center**'ı seç.")

st.markdown("---")
st.caption("Developed by Konya Teknik Üniversitesi · RoboBoat 2026 Team · THY Terminal Girişim Hızlandırma Programı")
