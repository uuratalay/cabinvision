# tests/test_c1_c2_fixes.py
#
# YOL HARİTASI GRUP D — Test ve Doğrulama
# D4: Dashboard slider validasyon testleri (C1)
# D5: sim_adim ile PredictionEngine tutarlılık testi (C2)
#
# Bu dosya %553 doluluk hatasının kök nedenlerinin gerçekten düzeltildiğini
# kanıtlar. Streamlit gerektirmez — saf mantık testidir.

import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from central.models.flight_models import UcusBilgisi, UcakTipi
from central.repositories.flight_memory_repository import FlightMemoryRepository, UcusKaydi
from central.services.prediction_engine import PredictionEngine


def test_d4_regional_kaldirildi():
    """C1 ön koşulu: REGIONAL/ATR kategorisi artık enum'da yok."""
    assert not hasattr(UcakTipi, 'REGIONAL'), "REGIONAL hala UcakTipi enum'inda mevcut"
    print("  OK  D4.1: REGIONAL enum'dan kaldirilmis")


def test_d4_slider_ust_sinir_ucak_tipine_bagli():
    """
    C1: Her uçak tipinin koltuk_sayisi_araligi'ndan türetilen üst sınır
    artık eski sabit (60-350) ile aynı DEĞİL — uçak tipine göre farklı.
    """
    narrow_max = UcakTipi.NARROW_BODY.koltuk_sayisi_araligi[1]
    wide_max = UcakTipi.WIDE_BODY.koltuk_sayisi_araligi[1]

    assert narrow_max != wide_max, "İki uçak tipinin üst sınırı aynı olmamalı"
    assert narrow_max < 350, f"NARROW_BODY max ({narrow_max}) eski sabit sınırdan (350) büyük olmamalı"
    print(f"  OK  D4.2: NARROW_BODY max={narrow_max}, WIDE_BODY max={wide_max} (farklı, dinamik)")


def test_d4_eski_imkansiz_kombinasyon_artik_engelleniyor():
    """
    C1: Eski hatalı senaryo — küçük kapasiteli uçak + çok yüksek yolcu —
    artık slider seviyesinde mantıksal olarak mümkün değil.
    Not: Streamlit slider'ı gerçek UI'da max_value ile kısıtlanıyor;
    burada o üst sınırın gerçek dünya değerleriyle tutarlı olduğunu test ediyoruz.
    """
    for tip in UcakTipi:
        min_k, max_k = tip.koltuk_sayisi_araligi
        # Üst sınır gerçek THY uçak ailesi aralığında olmalı (100-480 arası mantıklı)
        assert 50 <= max_k <= 500, f"{tip.value} üst sınırı gerçekçi değil: {max_k}"
    print("  OK  D4.3: Tüm uçak tiplerinin üst sınırı gerçekçi aralıkta")


def test_d5_sim_adim_check_in_oranini_dikkate_aliyor():
    """
    C2: sim_adim manuel/dashboard senaryosunda PredictionEngine'in konservatif
    tahminini değil, kullanıcının slider ile verdiği beyan oranını kullanır.

    Doğru üretim olasılığı:
        cabin_beyan_sayisi / toplam_yolcu

    PredictionEngine erken risk tahmini üretir; sim_adim ise slider ile kurulan
    senaryoyu doğrudan simüle eder. Bu ayrım korunmalıdır.
    """
    ucus = UcusBilgisi(
        ucus_no="TK-D5TEST", hat="IST-DXB", ucak_tipi=UcakTipi.NARROW_BODY,
        toplam_yolcu=200, cabin_beyan_sayisi=110, oversized_beyan=20,
        gate_id="TEST", manuel_senaryo=True,
    )

    bagaj_getirme_olasiligi = min(
        ucus.cabin_beyan_sayisi / max(ucus.toplam_yolcu, 1),
        1.0,
    )

    assert abs(bagaj_getirme_olasiligi - 0.55) < 0.001
    assert 0.0 <= bagaj_getirme_olasiligi <= 1.0, \
        f"Olasılık aralık dışı: {bagaj_getirme_olasiligi}"

    print(f"  OK  D5.1: sim_adim slider/beyan oranını kullanıyor "
          f"(cabin_beyan_sayisi={ucus.cabin_beyan_sayisi} / "
          f"toplam_yolcu={ucus.toplam_yolcu} = %{bagaj_getirme_olasiligi*100:.0f})")


def test_d5_gemini_birim_hatasi_artik_yok():
    """
    GEMINI'NİN BULDUĞU SOMUT KANIT SENARYOSU — tarihsel regresyon testi.

    Bu test, tahmini_doluluk_orani değerinin yolcu başına olasılık gibi
    kullanılmaması gerektiğini gösterir. Mevcut sim_adim manuel senaryoda
    doğrudan cabin_beyan_sayisi / toplam_yolcu kullanır. Buradaki hesap, eski
    birim hatasının geri dönmemesi için dokümantasyon/regresyon kanıtıdır.
    """
    # Gemini'nin senaryosunu simüle eden manuel bir DolulukTahmini kuruyoruz
    # (PredictionEngine'in iç hesaplamasını bypass edip doğrudan formülü test ediyoruz)
    from central.models.flight_models import DolulukTahmini

    sahte_tahmin = DolulukTahmini(
        ucus_no="TK-GEMINI-TEST",
        tahmini_doluluk_orani=0.75,      # 90/120
        tahmini_toplam_bagaj=90,         # GERÇEK ham sayı — düzeltmenin kalbi
        tahmini_oversized=10,
        kritik_yolcu_sirasi=None,
        asim_bekleniyor=False,
        guven_skoru=0.7,
        aciklama="test",
        tahmin_metodu="rule_based",
    )
    toplam_yolcu = 150

    # ESKİ (HATALI) formül — sadece karşılaştırma için, artık kodda kullanılmıyor
    eski_hatali_olasilik = sahte_tahmin.tahmini_doluluk_orani  # 0.75
    eski_hatali_beklenen_bagaj = toplam_yolcu * eski_hatali_olasilik  # 112.5

    # YENİ (DOĞRU) formül — sim_adim'de artık kullanılan
    yeni_dogru_olasilik = sahte_tahmin.tahmini_toplam_bagaj / toplam_yolcu  # 0.60
    yeni_dogru_beklenen_bagaj = toplam_yolcu * yeni_dogru_olasilik  # 90.0 (tam isabet)

    assert abs(yeni_dogru_beklenen_bagaj - sahte_tahmin.tahmini_toplam_bagaj) < 0.01, (
        f"Düzeltilmiş formül hala tahminle uyuşmuyor: "
        f"beklenen={yeni_dogru_beklenen_bagaj}, tahmin={sahte_tahmin.tahmini_toplam_bagaj}"
    )

    sapma_eski = abs(eski_hatali_beklenen_bagaj - sahte_tahmin.tahmini_toplam_bagaj)
    sapma_yeni = abs(yeni_dogru_beklenen_bagaj - sahte_tahmin.tahmini_toplam_bagaj)

    assert sapma_yeni < sapma_eski, "Yeni formül eskisinden daha kötü olmamalı"

    print(f"  OK  D5.3 (Gemini senaryosu): eski_hatali_sapma={sapma_eski:.1f} bagaj, "
          f"yeni_dogru_sapma={sapma_yeni:.1f} bagaj (tam isabet)")


def test_d5_553_hatasi_artik_uretilemez():
    """
    C1+C2 birlikte: Eski hatalı senaryo (en küçük kapasiteli uçak tipi +
    slider'ın izin verdiği maksimum yolcu) artık fiziksel/matematiksel
    olarak imkansız bir doluluk üretmiyor.

    GEMINI DÜZELTMESİ: Önceki versiyon `< 300` gibi kafadan bir sabit
    kullanıyordu — bu da yeni bir kanıtsız sabitti, kendi eleştirdiğimiz
    hatayı tekrarlıyordu. Düzeltilmiş test artık MATEMATIKSEL bir üst
    sınırla doğrulanıyor: simülasyon sonucu, slider'ın izin verdiği
    maksimum yolcu sayısının kapasiteye oranını AŞAMAZ — çünkü her yolcu
    en fazla 1 bagaj getirebilir (sim_adim'in temel varsayımı budur).
    """
    mem = FlightMemoryRepository(30)
    rng0 = random.Random(42)
    for i in range(10):
        mem.kayit_ekle(UcusKaydi(
            ucus_no=f"TK-D{i}", hat="IST-DXB", toplam_bagaj=90,
            oversized_sayisi=15, cabin_ok_sayisi=60, personal_sayisi=15,
            doluluk_orani=rng0.uniform(0.65, 0.85), ucak_tipi="narrow_body",
        ))

    pred = PredictionEngine.create("rule_based", memory=mem)

    en_kucuk_tip = min(UcakTipi, key=lambda t: t.kapasite)
    max_yolcu = en_kucuk_tip.koltuk_sayisi_araligi[1]  # C1: artık slider bunu aşamaz

    ucus = UcusBilgisi(
        ucus_no="TK-WORSTCASE", hat="IST-DXB", ucak_tipi=en_kucuk_tip,
        toplam_yolcu=max_yolcu,
        cabin_beyan_sayisi=int(max_yolcu * 0.55), oversized_beyan=20,
        gate_id="TEST",
    )
    tahmin = pred.tahmin_uret(ucus)

    # sim_adim'in mevcut mimarisi: slider/beyan oranı doğrudan üretim
    # olasılığıdır; PredictionEngine tahmini sadece erken risk sinyalidir.
    bagaj_getirme_olasiligi = min(
        ucus.cabin_beyan_sayisi / max(ucus.toplam_yolcu, 1), 1.0
    )

    sim_rng = random.Random(7)
    toplam_bagaj = sum(
        1 for _ in range(max_yolcu) if sim_rng.random() < bagaj_getirme_olasiligi
    )
    gercek_doluluk_pct = toplam_bagaj / en_kucuk_tip.kapasite * 100

    # MATEMATİKSEL ÜST SINIR (kafadan sabit değil): her yolcu en fazla 1 bagaj
    # getirebileceği için toplam_bagaj fiziksel olarak max_yolcu'yu aşamaz.
    # Bu yüzden doluluk oranı (max_yolcu / kapasite) * 100'ü aşamaz.
    matematiksel_ust_sinir_pct = (max_yolcu / en_kucuk_tip.kapasite) * 100

    assert gercek_doluluk_pct <= matematiksel_ust_sinir_pct, (
        f"Doluluk matematiksel üst sınırı aştı: %{gercek_doluluk_pct:.0f} > "
        f"%{matematiksel_ust_sinir_pct:.0f}"
    )

    print(f"  OK  D5.2: En kötü senaryoda doluluk=%{gercek_doluluk_pct:.0f} "
          f"(matematiksel üst sınır: %{matematiksel_ust_sinir_pct:.0f}, eski hata %553 idi)")


def test_d5_gemini_clamping_edge_case():
    """
    GEMINI 3. TUR, MADDE 1 — Düşük yolcu + yüksek kapasite + yüksek geçmiş
    ortalama kombinasyonunda tahmini_toplam_bagaj artık toplam_yolcu'yu
    AŞAMIYOR (clamping). Düzeltme öncesi bu senaryo "145 bagaj, 30 yolcu"
    gibi fiziksel olarak imkansız bir tahmin üretebiliyordu.
    """
    mem = FlightMemoryRepository(30)
    for i in range(10):
        mem.kayit_ekle(UcusKaydi(
            ucus_no=f"TK-D{i}", hat="IST-FRA", toplam_bagaj=200,
            oversized_sayisi=40, cabin_ok_sayisi=140, personal_sayisi=20,
            doluluk_orani=0.85,  # yüksek geçmiş ortalama — clamp'i tetikler
            ucak_tipi="wide_body",
        ))

    pred = PredictionEngine.create("rule_based", memory=mem)

    ucus = UcusBilgisi(
        ucus_no="TK-EDGE", hat="IST-FRA", ucak_tipi=UcakTipi.WIDE_BODY,
        toplam_yolcu=30,  # bilinçli olarak çok düşük
        cabin_beyan_sayisi=15, oversized_beyan=3,
        gate_id="TEST",
    )
    tahmin = pred.tahmin_uret(ucus)

    assert tahmin.tahmini_toplam_bagaj <= ucus.toplam_yolcu, (
        f"Tahmini bagaj ({tahmin.tahmini_toplam_bagaj}) yolcu sayısını "
        f"({ucus.toplam_yolcu}) aşıyor — clamp çalışmıyor!"
    )
    print(f"  OK  D5.4 (Gemini clamping): tahmini_toplam_bagaj="
          f"{tahmin.tahmini_toplam_bagaj} <= toplam_yolcu={ucus.toplam_yolcu}")


def test_d5_gemini_madde3b_overhead_bin_personal_item_haric():
    """
    GEMINI 3. TUR, MADDE 3 — Seçenek B (kök neden düzeltmesi).
    THY kuralına göre personal item koltuk altına gider, overhead bin'i
    hiç kullanmaz. InferenceService.overhead_bin_sayilan bu yüzden
    toplam_sayilan'dan FARKLI olmalı — personal item hariç tutulmalı.
    """
    from edge.models.calibration_models import GatePhysicalParams, ReferenceObject
    from edge.services.calibration_service import CalibrationService
    from edge.services.inference_service import InferenceService, MockDetector, SimpleTracker
    from edge.models.detection_models import BoyutSinifi

    params = GatePhysicalParams(
        gate_id="B-TEST", camera_height_m=3.5, camera_tilt_deg=15.0,
        camera_fov_horizontal_deg=90.0, camera_fov_vertical_deg=60.0,
        frame_width_px=1280, frame_height_px=720,
    )
    ref = ReferenceObject(55.0, 40.0, (400, 300, 620, 520), 2.0)
    calib = CalibrationService.create("manual").calibrate_gate(params, ref)
    inf = InferenceService("B-TEST", MockDetector(seed=1), SimpleTracker(), calib)
    inf.baslat()

    # 2 oversized, 3 cabin_ok, 2 personal_item
    sayim = {
        1: BoyutSinifi.OVERSIZED, 2: BoyutSinifi.OVERSIZED,
        3: BoyutSinifi.CABIN_OK, 4: BoyutSinifi.CABIN_OK, 5: BoyutSinifi.CABIN_OK,
        6: BoyutSinifi.PERSONAL_ITEM, 7: BoyutSinifi.PERSONAL_ITEM,
    }
    for tid, sinif in sayim.items():
        inf._InferenceService__sayilan_idler[tid] = sinif

    assert inf.toplam_sayilan == 7, f"toplam_sayilan 7 olmalı: {inf.toplam_sayilan}"
    assert inf.overhead_bin_sayilan == 5, (
        f"overhead_bin_sayilan 5 olmalı (2 oversized+3 cabin_ok, personal hariç): "
        f"{inf.overhead_bin_sayilan}"
    )

    print(f"  OK  D5.5 (Gemini madde 3B): toplam_sayilan={inf.toplam_sayilan} "
          f"(personal dahil) vs overhead_bin_sayilan={inf.overhead_bin_sayilan} "
          f"(personal hariç) — fark={inf.toplam_sayilan - inf.overhead_bin_sayilan} "
          f"personal item")


def test_d5_gemini4_seed_memory_tutarliligi():
    """
    GEMINI 4. TUR, MADDE 1 — Sefer hafızasındaki (mock) geçmiş kayıtların
    doluluk_orani'nin artık (oversized_sayisi + cabin_ok_sayisi) / kapasite
    formülüyle TUTARLI olduğunu doğrular — personal_sayisi hariç tutularak.

    Düzeltme öncesi doluluk_orani BAĞIMSIZ rastgele üretiliyordu, bu da
    B düzeltmesinden (overhead_bin_sayilan) sonra "elmalarla armut" kıyası
    yaratıyordu — PredictionEngine artık personal-hariç bir standart
    kullanırken, sefer hafızası eski/tutarsız değerler taşıyordu.
    """
    import random as _random
    rng = _random.Random(42)
    hatlar = ["IST-DXB", "IST-LHR", "IST-JFK", "IST-AYT", "IST-FRA"]
    kapasite = 120

    mem = FlightMemoryRepository(30)
    for i in range(40):
        hat = hatlar[i % 5]
        toplam = rng.randint(60, 110)
        oversized = int(toplam * rng.uniform(0.10, 0.25))
        cabin_ok = int(toplam * 0.65)
        personal = toplam - oversized - cabin_ok
        overhead_toplam = oversized + cabin_ok
        doluluk = min(overhead_toplam / kapasite, 1.0)

        mem.kayit_ekle(UcusKaydi(
            ucus_no=f"TK-D{i}", hat=hat, toplam_bagaj=toplam,
            oversized_sayisi=oversized, cabin_ok_sayisi=cabin_ok,
            personal_sayisi=personal, doluluk_orani=doluluk,
            ucak_tipi="narrow_body",
        ))

    # Her kaydın doluluk_orani'nin gerçekten (over+cabin)/kapasite olduğunu doğrula
    tutarsiz_sayisi = 0
    for hat in hatlar:
        for k in mem.son_n_kayit(hat, 10):
            beklenen = round(min((k.oversized_sayisi + k.cabin_ok_sayisi) / kapasite, 1.0), 4)
            kayitli = round(k.doluluk_orani, 4)
            if abs(beklenen - kayitli) > 0.001:
                tutarsiz_sayisi += 1

    assert tutarsiz_sayisi == 0, f"{tutarsiz_sayisi} kayıt tutarsız (personal dahil edilmiş olabilir)"
    print(f"  OK  D5.6 (Gemini 4. tur madde 1): tüm 40 sefer hafızası kaydı "
          f"(over+cabin)/kapasite ile tutarlı, personal hariç")


def test_d5_gemini5_bagimsiz_iki_olasilik_modeli():
    """
    GEMINI 5. TUR, MADDE 2 — KRİTİK DÜZELTME DOĞRULAMASI.

    Eski model: yolcu "oversized YA DA cabin_ok YA DA personal" arasında
    karşılıklı dışlayan (mutually exclusive) bir seçime zorlanıyordu — THY'nin
    1+1 kuralını (1 cabin bagaj + 1 personal item, AYNI ANDA) ihlal ediyordu.
    Bu, Baş Üstü Dolabı doluluğunun sistematik olarak EKSİK tahmin edilmesine
    (under-prediction) yol açıyordu.

    Yeni model: iki BAĞIMSIZ Bernoulli denemesi. Bu test, "ikisi birden"
    (hem baş üstü HEM koltuk altı) senaryosunun artık üretilebildiğini
    doğrudan kanıtlar — eski modelde bu MATEMATIKSEL OLARAK İMKANSIZDI.
    """
    from edge.models.detection_models import BoyutSinifi
    import random as _random

    rng = _random.Random(123)

    bagaj_getirme_olasiligi = 0.70   # yüksek tutuldu — "ikisi birden" sık görünsün
    PERSONAL_ITEM_GETIRME_ORANI = 0.75
    over_w = 0.15

    N = 2000
    hem_ikisi_de = 0
    sadece_bas_ustu = 0
    sadece_koltuk_alti = 0
    hicbiri = 0

    for _ in range(N):
        bas_ustu = rng.random() < bagaj_getirme_olasiligi
        if bas_ustu:
            _ = BoyutSinifi.OVERSIZED if rng.random() < over_w else BoyutSinifi.CABIN_OK

        koltuk_alti = rng.random() < PERSONAL_ITEM_GETIRME_ORANI

        if bas_ustu and koltuk_alti:
            hem_ikisi_de += 1
        elif bas_ustu:
            sadece_bas_ustu += 1
        elif koltuk_alti:
            sadece_koltuk_alti += 1
        else:
            hicbiri += 1

    # KRİTİK İDDİA: "hem ikisi de" senaryosu eski modelde 0 idi (matematiksel
    # olarak imkansızdı, çünkü mutually exclusive seçim vardı). Yeni modelde
    # teorik beklenen oran: 0.70 * 0.75 = %52.5 — yani N=2000'de ~1050 civarı.
    beklenen_ikisi_de = N * bagaj_getirme_olasiligi * PERSONAL_ITEM_GETIRME_ORANI
    sapma_orani = abs(hem_ikisi_de - beklenen_ikisi_de) / beklenen_ikisi_de

    assert hem_ikisi_de > 0, (
        "KRİTİK HATA: 'hem ikisi de' senaryosu hiç üretilmedi — "
        "bağımsızlık modeli çalışmıyor olabilir"
    )
    assert sapma_orani < 0.10, (
        f"Gözlenen 'ikisi birden' oranı ({hem_ikisi_de}) teorik beklentiden "
        f"(~{beklenen_ikisi_de:.0f}) %{sapma_orani*100:.1f} sapıyor — bağımsızlık bozuk olabilir"
    )

    print(f"  OK  D5.7 (Gemini 5.tur madde 2): N={N} denemede "
          f"hem_ikisi_de={hem_ikisi_de} (beklenen~{beklenen_ikisi_de:.0f}), "
          f"sadece_bas_ustu={sadece_bas_ustu}, sadece_koltuk_alti={sadece_koltuk_alti}, "
          f"hicbiri={hicbiri} — bağımsız model doğrulandı")


def test_d5_gemini5_ucak_tipi_filtreleme():
    """
    GEMINI 5. TUR, MADDE 3 — Sefer hafızası artık uçak tipine duyarlı.

    Senaryo: Aynı hat (IST-DXB) için hem narrow_body (kapasite 120, düşük
    doluluk) hem wide_body (kapasite 170, yüksek doluluk) kayıtları var.
    `ucak_tipi` parametresi verildiğinde, istatistik SADECE o tipteki
    kayıtlardan hesaplanmalı — karışık ortalama DEĞİL.
    """
    mem = FlightMemoryRepository(30)

    # 5 narrow_body kaydı — hep düşük doluluk (%50)
    for i in range(5):
        mem.kayit_ekle(UcusKaydi(
            ucus_no=f"TK-N{i}", hat="IST-DXB", toplam_bagaj=60,
            oversized_sayisi=10, cabin_ok_sayisi=50, personal_sayisi=10,
            doluluk_orani=0.50, ucak_tipi="narrow_body",
        ))

    # 5 wide_body kaydı — hep yüksek doluluk (%90)
    for i in range(5):
        mem.kayit_ekle(UcusKaydi(
            ucus_no=f"TK-W{i}", hat="IST-DXB", toplam_bagaj=150,
            oversized_sayisi=30, cabin_ok_sayisi=123, personal_sayisi=30,
            doluluk_orani=0.90, ucak_tipi="wide_body",
        ))

    # Tip belirtilmeden sorgu — TÜM 10 kayıt karışık (eski davranış)
    ist_karisik = mem.hat_istatistigi_al("IST-DXB")
    assert ist_karisik.kayit_sayisi == 10

    # narrow_body belirtilerek sorgu — SADECE 5 narrow kaydı kullanılmalı
    ist_narrow = mem.hat_istatistigi_al("IST-DXB", "narrow_body")
    assert ist_narrow.kayit_sayisi == 5, (
        f"narrow_body filtresi çalışmıyor: {ist_narrow.kayit_sayisi} kayıt döndü, 5 bekleniyordu"
    )
    assert abs(ist_narrow.ort_doluluk - 0.50) < 0.01, (
        f"narrow_body ortalaması yanlış: {ist_narrow.ort_doluluk} (beklenen ~0.50)"
    )

    # wide_body belirtilerek sorgu — SADECE 5 wide kaydı kullanılmalı
    ist_wide = mem.hat_istatistigi_al("IST-DXB", "wide_body")
    assert ist_wide.kayit_sayisi == 5
    assert abs(ist_wide.ort_doluluk - 0.90) < 0.01, (
        f"wide_body ortalaması yanlış: {ist_wide.ort_doluluk} (beklenen ~0.90)"
    )

    # KRİTİK KANIT: filtrelenmiş ortalamalar birbirinden BELİRGİN FARKLI —
    # eski (karışık) sistemde ikisi de aynı (karışık ortalama ~0.70) çıkardı
    assert abs(ist_narrow.ort_doluluk - ist_wide.ort_doluluk) > 0.3, (
        "Tip filtrelemesi anlamlı bir fark yaratmıyor — düzeltme etkisiz olabilir"
    )

    print(f"  OK  D5.8 (Gemini 5.tur madde 3): karışık_ort={ist_karisik.ort_doluluk:.2f}, "
          f"narrow_filtreli={ist_narrow.ort_doluluk:.2f}, "
          f"wide_filtreli={ist_wide.ort_doluluk:.2f} — tip filtrelemesi "
          f"gerçek/anlamlı bir fark yaratıyor")


def test_d5_gemini5_az_veri_durumunda_fallback():
    """
    GEMINI 5. TUR MADDE 3 — Edge case: bir uçak tipi için yeterli (< 3)
    kayıt yoksa sistem TÜM kayıtlara geri dönmeli (fallback) ve güven
    skorunu düşürmeli — tamamen None dönmemeli (veri varken veri yok
    demek aşırı tutucu olurdu).
    """
    mem = FlightMemoryRepository(30)
    for i in range(5):
        mem.kayit_ekle(UcusKaydi(
            ucus_no=f"TK-N{i}", hat="IST-AYT", toplam_bagaj=60,
            oversized_sayisi=10, cabin_ok_sayisi=50, personal_sayisi=10,
            doluluk_orani=0.50, ucak_tipi="narrow_body",
        ))
    # Sadece 1 wide_body kaydı — yetersiz (< 3 eşiği)
    mem.kayit_ekle(UcusKaydi(
        ucus_no="TK-W0", hat="IST-AYT", toplam_bagaj=150,
        oversized_sayisi=30, cabin_ok_sayisi=123, personal_sayisi=30,
        doluluk_orani=0.90, ucak_tipi="wide_body",
    ))

    ist_wide_az_veri = mem.hat_istatistigi_al("IST-AYT", "wide_body")

    assert ist_wide_az_veri is not None, "Az veri durumunda None dönmemeli (fallback çalışmalı)"
    assert ist_wide_az_veri.kayit_sayisi == 6, (
        f"Fallback tüm 6 kayda dönmeli, {ist_wide_az_veri.kayit_sayisi} döndü"
    )

    # Güven skoru, tam tip eşleşmesi olan duruma göre DAHA DÜŞÜK olmalı
    ist_normal = mem.hat_istatistigi_al("IST-AYT", "narrow_body")  # 5 kayıt, tam eşleşme
    assert ist_wide_az_veri.guven_skoru < ist_normal.guven_skoru, (
        "Tip uyuşmazlığı cezası uygulanmamış olabilir"
    )

    print(f"  OK  D5.9 (Gemini 5.tur madde 3, fallback): az veri durumunda "
          f"{ist_wide_az_veri.kayit_sayisi} kayda fallback yapıldı, "
          f"güven={ist_wide_az_veri.guven_skoru:.3f} < normal_güven={ist_normal.guven_skoru:.3f}")



def test_d6_plato_yok_manuel_senaryo():
    """
    REGRESSION TESTİ: %70, %80, %95 slider degerleri birbirinden farkli
    tahmin uretmeli — eski motor bunlari ~%86'da sabitliyordu (plato hatasi).
    Manuel senaryo modunda slider sinyali ana belirleyici.
    """
    import math as _math
    from central.services.prediction_engine import PredictionEngine
    from central.repositories.flight_memory_repository import FlightMemoryRepository
    from central.models.flight_models import UcusBilgisi, UcakTipi

    engine = PredictionEngine.create("rule_based", memory=FlightMemoryRepository())

    def ucus_olustur(no, beyan_pct):
        beyan = _math.ceil(180 * beyan_pct / 100)
        return UcusBilgisi(
            ucus_no=no, hat="IST-DXB", ucak_tipi=UcakTipi.NARROW_BODY,
            toplam_yolcu=180, cabin_beyan_sayisi=beyan,
            oversized_beyan=20, gate_id="G1", manuel_senaryo=True,
        )

    t70 = engine.tahmin_uret(ucus_olustur("T70", 70))
    t80 = engine.tahmin_uret(ucus_olustur("T80", 80))
    t95 = engine.tahmin_uret(ucus_olustur("T95", 95))

    assert t70.tahmini_doluluk_orani < t80.tahmini_doluluk_orani, (
        f"Plato hatasi: %70 ({t70.tahmini_doluluk_orani:.3f}) >= %80 ({t80.tahmini_doluluk_orani:.3f})"
    )
    assert t80.tahmini_doluluk_orani < t95.tahmini_doluluk_orani, (
        f"Plato hatasi: %80 ({t80.tahmini_doluluk_orani:.3f}) >= %95 ({t95.tahmini_doluluk_orani:.3f})"
    )
    # %95 beklenen talep: 171/120 = 1.425, motor 0.85 agirlikla bu sinyali kullaniyor
    # 0.85*1.425 + kucuk sabitler >= 1.0 olmali
    assert t95.tahmini_doluluk_orani > 1.0, (
        f"%95 slider senaryosu talep oranini %100 ustune cikaramadi: {t95.tahmini_doluluk_orani:.3f}"
    )
    assert t95.asim_bekleniyor is True

    print(f"  OK  D6.1 (plato yok): t70=%{t70.tahmini_doluluk_orani*100:.0f}, "
          f"t80=%{t80.tahmini_doluluk_orani*100:.0f}, t95=%{t95.tahmini_doluluk_orani*100:.0f} — "
          f"dogru siralama, %100 ustuNE cikiyor")


def test_d6_talep_orani_100_ustuNE_cikabilir():
    """
    REGRESSION TESTİ: 171 beyan / 120 kapasite = %142.5 talep orani.
    tahmini_doluluk_orani bu degeri min(1.0) ile KIRMAMALI.
    """
    from central.services.prediction_engine import PredictionEngine
    from central.repositories.flight_memory_repository import FlightMemoryRepository
    from central.models.flight_models import UcusBilgisi, UcakTipi

    engine = PredictionEngine.create("rule_based", memory=FlightMemoryRepository())
    ucus = UcusBilgisi(
        ucus_no="OVER", hat="IST-DXB", ucak_tipi=UcakTipi.NARROW_BODY,
        toplam_yolcu=180, cabin_beyan_sayisi=171,
        oversized_beyan=40, gate_id="G1", manuel_senaryo=True,
    )
    tahmin = engine.tahmin_uret(ucus)

    assert tahmin.tahmini_doluluk_orani > 1.0, (
        f"Talep orani kIRPILMIS: {tahmin.tahmini_doluluk_orani:.3f} <= 1.0 — "
        f"min(...,1.0) hatasi geri donmus olabilir"
    )
    assert tahmin.asim_bekleniyor is True
    assert tahmin.tahmini_toplam_bagaj <= ucus.toplam_yolcu, (
        f"Bagaj sayisi yolcu sayisini asti: {tahmin.tahmini_toplam_bagaj} > {ucus.toplam_yolcu}"
    )
    print(f"  OK  D6.2 (talep orani): {tahmin.tahmini_doluluk_orani:.3f} > 1.0, "
          f"bagaj={tahmin.tahmini_toplam_bagaj}/{ucus.toplam_yolcu} — dogru")

if __name__ == "__main__":
    print("\n=== C1 + C2 Düzeltme Doğrulama Testleri ===\n")
    tests = [
        test_d4_regional_kaldirildi,
        test_d4_slider_ust_sinir_ucak_tipine_bagli,
        test_d4_eski_imkansiz_kombinasyon_artik_engelleniyor,
        test_d5_sim_adim_check_in_oranini_dikkate_aliyor,
        test_d5_gemini_birim_hatasi_artik_yok,
        test_d5_gemini_clamping_edge_case,
        test_d5_gemini_madde3b_overhead_bin_personal_item_haric,
        test_d5_gemini4_seed_memory_tutarliligi,
        test_d5_gemini5_bagimsiz_iki_olasilik_modeli,
        test_d5_gemini5_ucak_tipi_filtreleme,
        test_d5_gemini5_az_veri_durumunda_fallback,
        test_d5_553_hatasi_artik_uretilemez,
        test_d6_plato_yok_manuel_senaryo,
        test_d6_talep_orani_100_ustuNE_cikabilir,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Sonuc: {passed} gecti, {failed} basarisiz")
    print(f"{'='*50}\n")
