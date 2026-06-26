# central/services/prediction_engine.py
#
# TAHMİN MOTORU — SLIDER TABANLI, KIRPMASIZ TALEP ORANI
#
# TEMEL KAVRAM AYRIMI:
#   Fiziksel doluluk  : %100'de durur (dolap taşamaz)
#   Baş üstü dolap talebi / kapasite oranı : %100 ÜSTÜNe ÇIKABİLİR
#   → 171 beyan / 120 kapasite = %142.5 talep oranı — bu sistemin ölçtüğü değer
#
# Bu yüzden tahmini_doluluk_orani alanı KIRPILMAZ (min(..., 1.0) YOK).
# Alan adı geriye dönük uyumluluk için korunur ama "fiziksel doluluk" değil
# "baş üstü dolap talebi / kapasite" oranını taşır.
#
# İKİ MOD:
#   operasyonel mod  : PNR/beyan sinyali düşük güvenilirlikte olabilir
#   manuel/demo mod  : kullanıcı slider ile senaryo kuruyor; slider ana sinyal

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
import math
import logging

from central.models.flight_models import (
    UcusBilgisi, DolulukTahmini, DolulukSeviyesi
)
from central.repositories.flight_memory_repository import (
    FlightMemoryRepository, HatIstatistigi
)

logger = logging.getLogger(__name__)

WARNING_THRESHOLD  = 0.75
CRITICAL_THRESHOLD = 0.90


class BaseTahminStratejisi(ABC):

    @abstractmethod
    def tahmin_uret(
        self,
        ucus: UcusBilgisi,
        hat_istatistigi: Optional[HatIstatistigi],
    ) -> DolulukTahmini:
        ...

    def _kritik_sira_hesapla(
        self,
        kapasite: int,
        toplam_yolcu: int,
        talep_orani: float,
    ) -> Optional[int]:
        """Kapasitenin dolacağı tahmini yolcu sırası."""
        if talep_orani < WARNING_THRESHOLD:
            return None
        if toplam_yolcu == 0 or talep_orani == 0:
            return None
        sira = int(kapasite / (talep_orani * toplam_yolcu) * toplam_yolcu)
        return min(max(sira, 1), toplam_yolcu)


class KuralBazliStrateji(BaseTahminStratejisi):
    """
    Kural tabanlı tahmin motoru — kirpmasiz talep orani.

    Formül (manuel/demo mod — slider ana sinyal):
        talep_orani = cabin_beyan_sayisi / kapasite   [KIRPILMAZ]

    Formül (operasyonel mod — sefer hafizasi da kullanilir):
        talep_orani = agirlikli_ortalama(varsayilan, gecmis, slider_sinyali)

    NEDEN KIRPILMIYOR?
        171 beyan / 120 kapasite = 1.425 → %142.5 talep oranı.
        min(1.425, 1.0) = 1.0 yapmak, "sistemin %95 ile %70'i ayırt etmemesi"
        sorununu yaratır. %95 slider senaryosu kesinlikle %70'ten yüksek
        tahmin üretmeli.

    OPERASYONEL vs MANUEL AYRIMI:
        ucus.manuel_senaryo=True ise slider sinyali ağırlığı 0.85'e çıkar,
        sefer hafızası en fazla 0.05 ağırlık alır.
    """

    def tahmin_uret(
        self,
        ucus: UcusBilgisi,
        hat_istatistigi: Optional[HatIstatistigi],
    ) -> DolulukTahmini:

        kapasite     = ucus.dolap_kapasitesi
        toplam_yolcu = max(ucus.toplam_yolcu, 1)
        beyan        = ucus.cabin_beyan_sayisi

        # ── SLIDER SİNYALİ (kapasite bazlı talep oranı — kirpilmaz) ──
        # beyan_orani_yolcu = beyan / toplam_yolcu   → "yolcu başına bagaj ihtimali"
        # talep_orani_kapasite = beyan / kapasite    → "kapasiteye göre baskı"
        # Bu ikisi birbirinden farklıdır; burada kapasite bazlı olan kullanılır
        # çünkü "dolap talebinin kapasiteye oranı" sistemin ölçtüğü metriktir.
        slider_talep = beyan / max(kapasite, 1)  # KIRPILMAZ — >1.0 olabilir

        if getattr(ucus, "manuel_senaryo", False):
            # MANUEL/DEMO MOD: kullanıcı senaryoyu bizzat kurdu.
            # Slider sinyali neredeyse tek belirleyici.
            # Sefer hafızası bağlam sinyali olarak çok küçük ağırlıkla kalır.
            slider_agirlik = 0.85
            gecmis_agirlik = 0.05
            varsayilan_agirlik = 1.0 - slider_agirlik - gecmis_agirlik  # = 0.10

            gecmis_talep = (
                hat_istatistigi.ort_doluluk
                if hat_istatistigi and hat_istatistigi.kayit_sayisi >= 3
                else 0.55
            )
            varsayilan_talep = 0.55

            talep_orani = (
                slider_talep      * slider_agirlik
                + gecmis_talep    * gecmis_agirlik
                + varsayilan_talep * varsayilan_agirlik
            )

            logger.debug(
                f"[{ucus.ucus_no}] Manuel mod: slider={slider_talep:.3f}*{slider_agirlik}, "
                f"gecmis={gecmis_talep:.3f}*{gecmis_agirlik}"
            )

        else:
            # OPERASYONEl MOD: PNR/beyan sinyali doğrulanmamış olabilir.
            # Sefer hafızası daha yüksek ağırlık alır.
            varsayilan_talep = 0.55

            gecmis_agirlik = 0.0
            if hat_istatistigi and hat_istatistigi.kayit_sayisi >= 3:
                gecmis_agirlik = round(
                    min(0.60, (hat_istatistigi.kayit_sayisi / 50) * 0.60), 3
                )
            gecmis_talep = (
                hat_istatistigi.ort_doluluk
                if hat_istatistigi and hat_istatistigi.kayit_sayisi >= 3
                else varsayilan_talep
            )

            slider_agirlik = 0.15 if beyan > 0 else 0.0
            varsayilan_agirlik = max(0.0, 1.0 - gecmis_agirlik - slider_agirlik)

            talep_orani = (
                varsayilan_talep * varsayilan_agirlik
                + gecmis_talep   * gecmis_agirlik
                + slider_talep   * slider_agirlik
            )

            logger.debug(
                f"[{ucus.ucus_no}] Operasyonel mod: slider={slider_talep:.3f}*{slider_agirlik}, "
                f"gecmis={gecmis_talep:.3f}*{gecmis_agirlik}, "
                f"varsayilan={varsayilan_talep:.3f}*{varsayilan_agirlik:.3f}"
            )

        # talep_orani KIRPILMAZ — %100 üstüne çıkabilir
        talep_orani = round(talep_orani, 3)

        # Tahmini toplam bagaj: kapasiteye göre normalize, ama yolcu sayısını aşamaz
        # (1 yolcu başına en fazla 1 baş üstü bagaj varsayımı)
        tahmini_bas_ustu = math.ceil(talep_orani * kapasite)
        tahmini_toplam_bagaj = min(tahmini_bas_ustu, toplam_yolcu)

        # Risk kararı kırpılmamış talep_orani'na göre
        asim = talep_orani >= CRITICAL_THRESHOLD

        # Oversized oranı (aksiyon açıklaması için, tahmini çarpmak için DEĞİL)
        oversized_orani = ucus.oversized_beyan / max(beyan, 1)
        tahmini_oversized = math.ceil(tahmini_toplam_bagaj * oversized_orani)

        # Beklenen aşım
        beklenen_asim = max(tahmini_toplam_bagaj - kapasite, 0)

        kritik_sira = self._kritik_sira_hesapla(kapasite, toplam_yolcu, talep_orani)

        # Güven: slider değeri ne kadar yüksekse güven o kadar yüksek
        guven = round(min(0.40 + min(slider_talep, 1.0) * 0.55, 0.95), 3)

        aciklama = self._aciklama(talep_orani, beklenen_asim, oversized_orani)

        return DolulukTahmini(
            ucus_no=ucus.ucus_no,
            tahmini_doluluk_orani=talep_orani,       # kirpilmamis talep orani
            tahmini_toplam_bagaj=tahmini_toplam_bagaj,
            tahmini_oversized=tahmini_oversized,
            kritik_yolcu_sirasi=kritik_sira,
            asim_bekleniyor=asim,
            guven_skoru=guven,
            aciklama=aciklama,
            tahmin_metodu=(
                "rule_based_manual_slider_v2"
                if getattr(ucus, "manuel_senaryo", False)
                else "rule_based_operational_v2"
            ),
        )

    def _aciklama(
        self,
        talep_orani: float,
        beklenen_asim: int,
        oversized_orani: float,
    ) -> str:
        pct = round(talep_orani * 100)
        if talep_orani >= CRITICAL_THRESHOLD:
            mesaj = (
                f"Tahmini baş üstü dolap talebi %{pct} — kapasite aşımı riski."
            )
            if beklenen_asim > 0:
                mesaj += f" Beklenen aşım: +{beklenen_asim} bagaj."
        elif talep_orani >= WARNING_THRESHOLD:
            mesaj = (
                f"Tahmini baş üstü dolap talebi %{pct} — UYARI. "
                f"Büyük kabin bagajları için gate-check hazırlığı planla."
            )
        else:
            mesaj = (
                f"Tahmini baş üstü dolap talebi %{pct} — normal seviye. "
                f"Boarding devam edebilir."
            )
        if oversized_orani >= 0.30:
            mesaj += " Oversized oranı yüksek; gate-check hazırlığı önceliklendirilmeli."
        return mesaj


class MLBazliStrateji(BaseTahminStratejisi):
    """ML tabanlı tahmin — gelecek iterasyon için yer tutucu."""

    def __init__(self):
        self._fallback = KuralBazliStrateji()
        logger.warning("MLBazliStrateji henuz implement edilmedi. Fallback.")

    def tahmin_uret(
        self,
        ucus: UcusBilgisi,
        hat_istatistigi: Optional[HatIstatistigi],
    ) -> DolulukTahmini:
        result = self._fallback.tahmin_uret(ucus, hat_istatistigi)
        result.tahmin_metodu = "ml_based_fallback"
        return result


class PredictionEngine:

    def __init__(
        self,
        strateji: BaseTahminStratejisi,
        memory: FlightMemoryRepository,
    ):
        self._strateji = strateji
        self._memory   = memory
        self._tahmin_cache: dict[str, DolulukTahmini] = {}

    @classmethod
    def create(
        cls,
        metod: str = "rule_based",
        memory: Optional[FlightMemoryRepository] = None,
    ) -> "PredictionEngine":
        mem = memory or FlightMemoryRepository()
        stratejiler = {
            "rule_based": KuralBazliStrateji,
            "ml_based":   MLBazliStrateji,
        }
        if metod not in stratejiler:
            raise ValueError(f"Bilinmeyen metod: {metod}")
        return cls(strateji=stratejiler[metod](), memory=mem)

    def tahmin_uret(self, ucus: UcusBilgisi) -> DolulukTahmini:
        if ucus.ucus_no in self._tahmin_cache:
            return self._tahmin_cache[ucus.ucus_no]
        hat_ist = self._memory.hat_istatistigi_al(ucus.hat, ucus.ucak_tipi.value)
        tahmin  = self._strateji.tahmin_uret(ucus, hat_ist)
        self._tahmin_cache[ucus.ucus_no] = tahmin
        logger.info(
            f"[{ucus.ucus_no}] Tahmin: talep=%{int(tahmin.tahmini_doluluk_orani*100)}, "
            f"asim={tahmin.asim_bekleniyor}, guven={tahmin.guven_skoru:.2f}"
        )
        return tahmin

    def tahmin_gecersiz_kil(self, ucus_no: str) -> None:
        self._tahmin_cache.pop(ucus_no, None)

    def strateji_degistir(self, metod: str) -> None:
        stratejiler = {"rule_based": KuralBazliStrateji, "ml_based": MLBazliStrateji}
        if metod not in stratejiler:
            raise ValueError(f"Bilinmeyen metod: {metod}")
        self._strateji = stratejiler[metod]()
        self._tahmin_cache.clear()
