import sys, os

# Streamlit Cloud'da dosya /mount/src/cabinvision/cabinvision/app.py olarak calisir
# Bu yuzden bir ust dizini (cabinvision/) path'e ekliyoruz
sys.path.insert(0, os.path.dirname(__file__))

# gate_dashboard'u exec ile calistiriyoruz -- import yerine exec kullanmak
# Python 3.14'teki paket bulunamadi hatasini asar
_dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "gate", "gate_dashboard.py")
with open(_dashboard_path, encoding="utf-8") as _f:
    exec(_f.read(), {"__name__": "__main__", "__file__": _dashboard_path})
