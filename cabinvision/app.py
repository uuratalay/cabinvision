import sys, os

# Cabinvision klasörünü path'e ekle
_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)

# gate_dashboard dosyasını exec ile çalıştır
# (Python 3.14'te paket import hatalarını aşar)
_f = os.path.join(_dir, "dashboard", "gate", "gate_dashboard.py")
with open(_f, encoding="utf-8") as _fh:
    exec(compile(_fh.read(), _f, "exec"), {"__name__": "__main__", "__file__": _f})
