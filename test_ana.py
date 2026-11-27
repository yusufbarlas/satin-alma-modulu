"""Menünün (ana.py) testleri (pytest): klavye girişi taklit edilerek.

Her test ana menüyü kendi geçici klasöründe (tmp_path) baştan sona
çalıştırır. input yerine sırayla cevap veren sahte bir fonksiyon konur
(monkeypatch), ekrana yazılanlar capsys ile okunur; sonra veri dosyası
yeniden açılıp kaydedilenler kontrol edilir. Menü tarih sormaz, bu yüzden
belgelerin kayıt tarihi bugündür. Çalıştırma: proje klasöründe `pytest -v`.
"""

import builtins
from decimal import Decimal

import ana
from servis import SatinAlmaServisi


class GirdiBitti(Exception):
    """Menü, testte verilen cevaplardan fazla soru sorduğunda atılır."""


def menuyu_calistir(tmp_path, monkeypatch, capsys, girdiler):
    """Ana menüyü verilen cevaplarla çalıştırır; ekran çıktısını ve servisi döndürür.

    input her çağrıldığında listeden sıradaki cevap verilir. Cevaplar
    biterse GirdiBitti atılır (menü beklenenden fazla soru sordu); menü
    kapandığında kullanılmayan cevap kalırsa test kalır (menü beklenenden
    az soru sordu). Böylece soruların sırası da test edilir.

    Args:
        tmp_path: pytest'in geçici klasörü.
        monkeypatch: pytest'in geçici değiştirme aracı (VERI_DOSYASI, input).
        capsys: pytest'in ekran çıktısı yakalayıcısı.
        girdiler: Sırayla verilecek cevaplar; son cevap "0" (çıkış) olmalı.

    Returns:
        (ekran çıktısı, dosyadan yeniden açılmış SatinAlmaServisi) ikilisi.
    """
    veri_dosyasi = tmp_path / "veri.json"
    monkeypatch.setattr(ana, "VERI_DOSYASI", veri_dosyasi)
    kalan_girdiler = list(girdiler)

    def sahte_input(soru=""):
        if not kalan_girdiler:
            raise GirdiBitti(f"Cevap kalmadı; son soru: {soru!r}")
        return kalan_girdiler.pop(0)

    monkeypatch.setattr(builtins, "input", sahte_input)
    ana.menuyu_baslat()
    cikti = capsys.readouterr().out
    assert kalan_girdiler == []
    return cikti, SatinAlmaServisi(veri_dosyasi)


# Sık kullanılan cevap dizileri (menü seçeneği + soruların cevapları)
TED = ["6", "ABC Kırtasiye", ""]          # 6 Tedarikçi ekle → TED-0001
TED2 = ["6", "XYZ Ltd", ""]               # 6 Tedarikçi ekle → TED-0002
TALEP = ["1", "Muhasebe", "Defter", "10", "adet", "SARF", "12,5", ""]  # 1 Talep aç → TLP-0001
TALEP_ONAY = ["2", "TLP-0001"]            # 2 Talep onayla


def test_menu_basliklari_ve_cikis(tmp_path, monkeypatch, capsys):
    """Menü grup başlıklarını ve 26 seçeneği yazar; geçersiz seçimde uyarır, 0 ile çıkar."""
    cikti, servis = menuyu_calistir(tmp_path, monkeypatch, capsys, ["99", "0"])
    assert "— Talep ve teklif —" in cikti
    assert "26 - Talep iptal" in cikti
    assert "Geçersiz seçim." in cikti
    assert "Çıkış yapılıyor..." in cikti


def test_uctan_uca_menu_talep_teklif_siparis_fatura_odeme(tmp_path, monkeypatch, capsys):
    """Uçtan uca menüden: talep → iki teklif (biri reddedilir) → tekliften sipariş → mal kabul → fatura → kısmi + kalan ödeme (J6 kalıbı)."""
    girdiler = (
        TED + TED2 + TALEP + TALEP_ONAY
        # 4 teklif kaydet: TED-0001, teklif no, talep TLP-0001, miktar 10, fiyat 100, iskonto yok, ek kalem yok
        + ["4", "TED-0001", "T-55", "TLP-0001", "10", "100", "", ""]
        # 4 ikinci tedarikçi teklifi, pahalı
        + ["4", "TED-0002", "", "TLP-0001", "10", "120", "", ""]
        # 5 pahalı teklifi reddet
        + ["5", "TKL-0002", "1", ""]
        # 8 tekliften sipariş
        + ["8", "TKL-0001"]
        # 9 onay
        + ["9", "SAS-0001"]
        # 10 mal kabul: tır kapıda, gelen 10, yanlış ürün yok
        + ["10", "SAS-0001", "", "10", ""]
        # 11 fatura: no, miktar 10, fiyat 100, iskonto yok
        + ["11", "SAS-0001", "F-1001", "10", "100", ""]
        # 20 ödeme bekleyenler
        + ["20"]
        # 16 ödeme: tedarikçi, kısmi 400, bitir, yöntem 1, not yok
        + ["16", "TED-0001", "FTR-0001", "400", "", "1", ""]
        # 16 kalan 600
        + ["16", "TED-0001", "FTR-0001", "600", "", "2", "kalan"]
        + ["20", "0"]
    )
    cikti, servis = menuyu_calistir(tmp_path, monkeypatch, capsys, girdiler)
    assert "Talep açıldı: TLP-0001" in cikti
    assert "Teklif kaydedildi: TKL-0001 · ACIK · toplam 1000.00" in cikti
    assert "Teklif reddedildi: TKL-0002" in cikti
    assert "Sipariş açıldı: SAS-0001 · TASLAK · toplam 1000.00 · teklif TKL-0001" in cikti
    assert "Fatura kaydedildi: FTR-0001 · ONAYLANDI" in cikti
    assert "FTR-0001 · TED-0001 · toplam 1000.00 · kalan 1000.00" in cikti
    assert "FTR-0001: ödenen 400 · kalan 600.00" in cikti
    assert "Ödeme kaydedildi: ODM-0002 · NAKIT · toplam 600" in cikti
    assert cikti.rstrip().endswith("Çıkış yapılıyor...")
    assert "Ödeme bekleyen fatura yok." in cikti
    k = servis.siparis_bul("SAS-0001").siparis_kalemleri[0]
    assert (k.malzeme_adi, k.talep_no, k.teklif_no) == ("Defter", "TLP-0001", "TKL-0001")
    assert servis.fatura_kalan_borc("FTR-0001") == 0


def test_menu_siparis_talepten_ve_ek_kalem(tmp_path, monkeypatch, capsys):
    """Sipariş ekranı: talepten kalem (iskontolu) + talepte olmayan ek kalem."""
    girdiler = (TED + TALEP + TALEP_ONAY
        # 7 sipariş: tedarikçi, talep, miktar 6, fiyat 12, iskonto ORAN 5; ek kalem Kalem
        + ["7", "TED-0001", "TLP-0001", "6", "12", "ORAN", "5",
           "Kalem", "3", "adet", "2", "SARF", "", "", ""]
        + ["0"])
    cikti, servis = menuyu_calistir(tmp_path, monkeypatch, capsys, girdiler)
    sp = servis.siparis_bul("SAS-0001")
    assert [k.malzeme_adi for k in sp.siparis_kalemleri] == ["Defter", "Kalem"]
    assert sp.siparis_kalemleri[0].iskonto_degeri == Decimal("5")
    assert sp.siparis_kalemleri[1].talep_no is None


def test_menu_hata_yollari(tmp_path, monkeypatch, capsys):
    """Hata yolları: 17a alan tekrar sorulur, 18a numara tekrar sorulur; 20d, 20g, 20c, 22a, 18b ana menüye döner."""
    girdiler = (TED
        # talep: önce boş talep eden (17a) → tekrar sorulur
        + ["1", " ", "Defter", "10", "adet", "SARF", "", "",
           "Muhasebe", "Defter", "10", "adet", "SARF", "", ""]
        # onaysız talepten sipariş → 20d ana menüye
        + ["7", "TED-0001", "TLP-0001", "5", "12", "", ""]
        + TALEP_ONAY
        # talep no yanlış (18a) → tekrar; miktar 11 > 10 → 20g ana menü
        + ["7", "TED-0001", "TLP-9999", "TLP-0001", "11", "12", "", ""]
        # doğru sipariş
        + ["7", "TED-0001", "TLP-0001", "10", "12", "", ""]
        # aynı talep kalemiyle ikinci sipariş → 20c
        + ["7", "TED-0001", "TLP-0001", "1", "12", "", ""]
        # talebi iptal etmeye çalış → 22a
        + ["26", "TLP-0001", "3", ""]
        # talebi yeniden onayla → 18b
        + ["2", "TLP-0001"]
        # ödeme bekleyen yok
        + ["20"]
        # ödeme: fatura yok → mesaj ve dönüş
        + ["16", "TED-0001"]
        + ["0"])
    cikti, servis = menuyu_calistir(tmp_path, monkeypatch, capsys, girdiler)
    assert "Talep eden boş olamaz" in cikti
    assert "sadece iptal edilmemiş ONAYLANDI talebe bağlanılır" in cikti
    assert "TLP-9999 numaralı kayıt bulunamadı" in cikti
    assert "talep miktarından (10) büyük olamaz" in cikti
    assert "talep kalemi zaten SAS-0001 siparişine bağlı" in cikti
    assert "talebe bağlı aktif sipariş var (SAS-0001)" in cikti
    assert "sadece iptal edilmemiş TASLAK talep onaylanır" in cikti
    assert "Ödeme bekleyen fatura yok." in cikti
    assert "Bu tedarikçinin ödeme bekleyen faturası yok." in cikti
    assert list(servis.siparisler) == ["SAS-0001"]


def test_menu_odeme_hatalari_ve_iptaller(tmp_path, monkeypatch, capsys):
    """Ödeme: 23e tutar tekrar sorulur; 9c, 12a, 24b ve zincir tersten iptaller (ödeme → fatura → mal kabul → sipariş)."""
    girdiler = (TED + TED2
        + ["7", "TED-0001", "", "A4", "10", "adet", "100", "SARF", "", "", ""]
        + ["9", "SAS-0001", "10", "SAS-0001", "", "10", ""]
        + ["11", "SAS-0001", "F-1", "10", "100", ""]
        # ödeme: kalan borcu aşan tutar (23e) → tekrar; yanlış yöntem yok (seçenek); sonra doğru 300
        + ["16", "TED-0001", "FTR-0001", "2000", "", "1", "",
                             "FTR-0001", "300", "", "1", ""]
        # başka tedarikçi adına ödeme → o tedarikçinin bekleyeni yok
        + ["16", "TED-0002"]
        # faturayı iptal etmeye çalış → 9c
        + ["22", "FTR-0001", "1", ""]
        # ödemeyi iptal et: önce DIGER notsuz (12a) → tekrar
        + ["21", "ODM-0001", "5", "", "2", ""]
        # tekrar iptal → 24b
        + ["21", "ODM-0001", "1", ""]
        # şimdi fatura iptal olur, sonra mal kabul, sipariş
        + ["22", "FTR-0001", "1", ""]
        + ["23", "MKB-0001", "1", ""]
        + ["24", "SAS-0001", "1", ""]
        + ["0"])
    cikti, servis = menuyu_calistir(tmp_path, monkeypatch, capsys, girdiler)
    assert "kalan borcu (1000.00) aşıyor" in cikti
    assert "Ödeme kaydedildi: ODM-0001" in cikti
    assert "Bu tedarikçinin ödeme bekleyen faturası yok." in cikti
    assert "faturanın aktif ödemesi var" in cikti
    assert "DIGER seçildiğinde açıklama notu zorunlu" in cikti
    assert "ödeme zaten iptal edilmiş" in cikti
    assert "Fatura iptal edildi: FTR-0001" in cikti
    assert "Sipariş iptal edildi: SAS-0001" in cikti
    assert servis.odeme_bul("ODM-0001").iptal_bilgisi.iptal_edildi
    assert servis.siparis_bul("SAS-0001").iptal_bilgisi.iptal_edildi


def test_menu_teklif_iptal_ve_talep_iptal_ve_hatalar(tmp_path, monkeypatch, capsys):
    """Teklif: 19a tedarikçi tekrar sorulur; 22b, 21b, 20b, 22c ana menüye döner; sonra zincir tersten iptal edilir."""
    girdiler = (TED + TALEP + TALEP_ONAY
        # teklif: önce yanlış tedarikçi (19a) → tedarikçi ve kalemler tekrar
        + ["4", "TED-9", "", "TLP-0001", "10", "50", "", "",
                "TED-0001", "TLP-0001", "10", "50", "", ""]
        # talepsiz teklif, iki kalem aynı talepten değil: bağsız, iskonto TUTAR 1
        + ["4", "TED-0001", "", "", "Kalem", "3", "adet", "2", "SARF", "TUTAR", "1", ""]
        + ["8", "TKL-0001"]
        # teklifi iptal → 22b
        + ["25", "TKL-0001", "1", ""]
        # siparişe dönüşmüş teklifi reddet → 21b
        + ["5", "TKL-0001", "1", ""]
        # tekliften yeniden sipariş → 20b
        + ["8", "TKL-0001"]
        # bağsız teklifi iptal et
        + ["25", "TKL-0002", "3", ""]
        + ["25", "TKL-0002", "3", ""]
        + ["24", "SAS-0001", "1", ""]
        + ["25", "TKL-0001", "1", ""]
        + ["26", "TLP-0001", "3", ""]
        + ["0"])
    cikti, servis = menuyu_calistir(tmp_path, monkeypatch, capsys, girdiler)
    assert "TED-9 numaralı kayıt bulunamadı" in cikti
    assert "Teklif kaydedildi: TKL-0001" in cikti
    assert "Teklif kaydedildi: TKL-0002 · ACIK · toplam 3.00" in cikti
    assert "teklife bağlı aktif sipariş var" in cikti
    assert "teklif siparişe dönüşmüş" in cikti
    assert "teklif zaten siparişe dönüşmüş" in cikti
    assert "teklif zaten iptal edilmiş" in cikti
    assert "Talep iptal edildi: TLP-0001" in cikti
    assert servis.talep_bul("TLP-0001").iptal_bilgisi.iptal_edildi


def test_menu_talep_reddet(tmp_path, monkeypatch, capsys):
    """Talep reddi: DIGER notsuz (7c) gerekçe tekrar sorulur; reddedilen talep yeniden reddedilmez (18b)."""
    girdiler = (TALEP + ["3", "TLP-0001", "4", "", "1", ""] + ["3", "TLP-0001", "1", ""] + ["0"])
    cikti, servis = menuyu_calistir(tmp_path, monkeypatch, capsys, girdiler)
    assert "DIGER seçildiğinde açıklama notu zorunlu" in cikti
    assert "Talep reddedildi: TLP-0001" in cikti
    assert "sadece iptal edilmemiş TASLAK talep reddedilir" in cikti
    assert servis.talep_bul("TLP-0001").karar_gerekcesi == "BUTCE_YOK"


def test_menu_v1a_akisi_bozulmadi(tmp_path, monkeypatch, capsys):
    """v1a akışı yeni menü numaralarıyla çalışır: fatura önce gelir, mal kabulde eşleşir (R2), serbest bırak, karantina İADE."""
    girdiler = (TED
        + ["7", "TED-0001", "", "A4", "10", "adet", "100", "SARF", "", "", ""]
        + ["9", "SAS-0001"]
        + ["11", "SAS-0001", "F-1", "10", "120", ""]          # mal yok: bekler
        + ["17"]
        + ["10", "SAS-0001", "H", "15", ""]                  # tır gitti, 15 geldi
        + ["18", "19", "12", "FTR-0001"]
        + ["13", "FTR-0001", "1", ""]
        + ["15", "MKB-0001", "10", "1", "2", "1", ""]
        + ["0"])
    cikti, servis = menuyu_calistir(tmp_path, monkeypatch, capsys, girdiler)
    assert "Mal kabul bekleniyor" in cikti
    assert "FTR-0001 · SAS-0001" in cikti
    assert "Bekleyen fatura eşleşti: FTR-0001 · BLOKE" in cikti
    assert "FIYAT_YUKSEK" in cikti
    assert "Fatura serbest bırakıldı: FTR-0001" in cikti
    assert "Karar kaydedildi: MKB-0001 kalem 10" in cikti
    assert servis.fatura_bul("FTR-0001").durum == "SERBEST"
