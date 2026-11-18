import json
from dataclasses import asdict
from decimal import Decimal, InvalidOperation

from ayarlar import VERI_SURUMU
from hatalar import DepolamaError
from modeller import (
    Fatura,
    FaturaKalemi,
    IptalBilgisi,
    KarantinaKarari,
    MalKabul,
    MalKabulDagitimi,
    MalKabulKalemi,
    NedenliMiktar,
    Siparis,
    SiparisKalemi,
    Tedarikci,
    ToleransKopyasi,
)

def sozluge_cevir(veri):
    """Servisin verisini JSON'a yazılmaya hazır sözlüğe çevirir.

    veri_surumu ve sayaclar olduğu gibi kopyalanır; belge
    listelerindeki her nesne asdict ile sözlüğe döner. Decimal'lere
    dokunulmaz; onları kaydet metne çevirir. Gelen veri değişmez.

    Args:
        veri: Servisin verisi; anahtarlar veri_surumu, sayaclar ve
            beş belge listesi (tedarikciler, siparisler, mal_kabuller,
            faturalar, karantina_kararlari).

    Returns:
        Aynı anahtarlarla, nesneleri sözlüğe çevrilmiş yeni sözlük.
    """
    yeni = {}
    yeni["veri_surumu"] = veri["veri_surumu"]
    yeni["sayaclar"] = veri["sayaclar"]
    for anahtar, belgeler in veri.items():
        if anahtar not in yeni:
            belge_sozlukleri = []
            for belge in belgeler:
                belge_sozlukleri.append(asdict(belge))
            yeni[anahtar] = belge_sozlukleri
    return yeni


def kaydet(veri, dosya_yolu):
    """Servisin verisini JSON dosyasına yazar.

    Önce nesneler sözlüğe çevrilir; Decimal'ler yazılırken metne
    döner (default=str). Dosya varsa üstüne yazılır.

    Args:
        veri: Servisin verisi (sozluge_cevir'deki şema).
        dosya_yolu: Yazılacak dosya, ör. "veri.json".

    Raises:
        DepolamaError: Dosya yazılamazsa (klasör yok, izin yok; 10b).
    """
    sozluk = sozluge_cevir(veri)
    try:
        with open(dosya_yolu, "w", encoding="utf-8") as dosya:
            json.dump(sozluk, dosya, default=str, ensure_ascii=False, indent=4)
    except OSError as hata:
        raise DepolamaError(f"Kaydedilemedi: {dosya_yolu}") from hata


def nesneye_cevir(ham_veri):
    """JSON'dan okunan sözlüğü servisin verisine (nesnelere) çevirir.

    Giriş kapısı (E70): önce veri sürümü kontrol edilir (E108), sonra
    metinler Decimal'e döner ve iç içe nesneler (ToleransKopyasi,
    IptalBilgisi, MalKabulDagitimi) yeniden kurulur.

    Args:
        ham_veri: json.load'un döndürdüğü sözlük; anahtarlar veri_surumu,
            sayaclar ve beş belge listesi.

    Returns:
        Aynı anahtarlarla, belgeleri nesne olan sözlük.

    Raises:
        DepolamaError: veri_surumu programınkine eşit değilse (10d).
        KeyError, InvalidOperation, TypeError: Yapı bozuksa; yukle bunları
            DepolamaError'a çevirir (10c).
    """
    if ham_veri["veri_surumu"] != VERI_SURUMU:
        raise DepolamaError(
            f"Veri dosyasının sürümü {ham_veri['veri_surumu']}, "
            f"programın sürümü {VERI_SURUMU}; dosya okunamıyor"
        )
    yeni = {}
    yeni["veri_surumu"] = ham_veri["veri_surumu"]
    yeni["sayaclar"] = ham_veri["sayaclar"]

    tedarikciler = []
    for tedarikci_sozlugu in ham_veri["tedarikciler"]:
        tedarikci = Tedarikci(
            tedarikci_kodu=tedarikci_sozlugu["tedarikci_kodu"],
            tedarikci_adi=tedarikci_sozlugu["tedarikci_adi"],
            firma_adi=tedarikci_sozlugu["firma_adi"],
        )
        tedarikciler.append(tedarikci)
    yeni["tedarikciler"] = tedarikciler

    siparisler = []
    for siparis_sozlugu in ham_veri["siparisler"]:
        kalemler = []
        for siparis_kalem_sozlugu in siparis_sozlugu["siparis_kalemleri"]:
            tolerans_sozlugu = siparis_kalem_sozlugu["tolerans"]
            cevrilmis = {}
            for alan, deger in tolerans_sozlugu.items():
                if deger is not None:
                    cevrilmis[alan] = Decimal(deger)
                else:
                    cevrilmis[alan] = None
            tolerans = ToleransKopyasi(**cevrilmis)

            miktar_tavani = siparis_kalem_sozlugu["miktar_tavani"]
            siparis_kalemi = SiparisKalemi(
                kalem_no=siparis_kalem_sozlugu["kalem_no"],
                malzeme_adi=siparis_kalem_sozlugu["malzeme_adi"],
                miktar=Decimal(siparis_kalem_sozlugu["miktar"]),
                birim=siparis_kalem_sozlugu["birim"],
                birim_fiyat=Decimal(siparis_kalem_sozlugu["birim_fiyat"]),
                kategori=siparis_kalem_sozlugu["kategori"],
                tolerans=tolerans,
                iskonto_turu=siparis_kalem_sozlugu["iskonto_turu"],
                iskonto_degeri=Decimal(siparis_kalem_sozlugu["iskonto_degeri"]),
                miktar_tavani=(
                    Decimal(miktar_tavani) if miktar_tavani is not None else None
                ),
            )
            kalemler.append(siparis_kalemi)

        iptal_sozlugu = siparis_sozlugu["iptal_bilgisi"]
        iptal_bilgisi = IptalBilgisi(
            iptal_edildi=iptal_sozlugu["iptal_edildi"],
            iptal_gerekcesi=iptal_sozlugu["iptal_gerekcesi"],
            iptal_notu=iptal_sozlugu["iptal_notu"],
            iptal_tarihi=iptal_sozlugu["iptal_tarihi"],
        )
        siparis = Siparis(
            siparis_no=siparis_sozlugu["siparis_no"],
            tedarikci_kodu=siparis_sozlugu["tedarikci_kodu"],
            siparis_kalemleri=kalemler,
            kayit_tarihi=siparis_sozlugu["kayit_tarihi"],
            durum=siparis_sozlugu["durum"],
            iptal_bilgisi=iptal_bilgisi,
        )
        siparisler.append(siparis)
    yeni["siparisler"] = siparisler

    mal_kabuller = []
    for mal_kabul_sozlugu in ham_veri["mal_kabuller"]:
        kalemler = []
        for mal_kabul_kalem_sozlugu in mal_kabul_sozlugu["mal_kabul_kalemleri"]:
            karantinalar = []
            for neden_sozlugu in mal_kabul_kalem_sozlugu["karantinalar"]:
                karantinalar.append(NedenliMiktar(
                    neden=neden_sozlugu["neden"],
                    miktar=Decimal(neden_sozlugu["miktar"]),
                ))
            kapida_redler = []
            for neden_sozlugu in mal_kabul_kalem_sozlugu["kapida_redler"]:
                kapida_redler.append(NedenliMiktar(
                    neden=neden_sozlugu["neden"],
                    miktar=Decimal(neden_sozlugu["miktar"]),
                ))
            mal_kabul_kalemi = MalKabulKalemi(
                kalem_no=mal_kabul_kalem_sozlugu["kalem_no"],
                siparis_kalem_no=mal_kabul_kalem_sozlugu["siparis_kalem_no"],
                kabul_edilen_miktar=Decimal(
                    mal_kabul_kalem_sozlugu["kabul_edilen_miktar"]
                ),
                karantinalar=karantinalar,
                kapida_redler=kapida_redler,
            )
            kalemler.append(mal_kabul_kalemi)

        iptal_sozlugu = mal_kabul_sozlugu["iptal_bilgisi"]
        iptal_bilgisi = IptalBilgisi(
            iptal_edildi=iptal_sozlugu["iptal_edildi"],
            iptal_gerekcesi=iptal_sozlugu["iptal_gerekcesi"],
            iptal_notu=iptal_sozlugu["iptal_notu"],
            iptal_tarihi=iptal_sozlugu["iptal_tarihi"],
        )
        mal_kabul = MalKabul(
            mal_kabul_no=mal_kabul_sozlugu["mal_kabul_no"],
            siparis_no=mal_kabul_sozlugu["siparis_no"],
            mal_kabul_kalemleri=kalemler,
            kayit_tarihi=mal_kabul_sozlugu["kayit_tarihi"],
            mal_kabul_notu=mal_kabul_sozlugu["mal_kabul_notu"],
            iptal_bilgisi=iptal_bilgisi,
        )
        mal_kabuller.append(mal_kabul)
    yeni["mal_kabuller"] = mal_kabuller

    faturalar = []
    for fatura_sozlugu in ham_veri["faturalar"]:
        kalemler = []
        for fatura_kalem_sozlugu in fatura_sozlugu["fatura_kalemleri"]:
            dagitimlar = []
            for dagitim_sozlugu in fatura_kalem_sozlugu["mal_kabul_dagitimi"]:
                dagitim = MalKabulDagitimi(
                    mal_kabul_no=dagitim_sozlugu["mal_kabul_no"],
                    miktar=Decimal(dagitim_sozlugu["miktar"]),
                )
                dagitimlar.append(dagitim)

            fatura_kalemi = FaturaKalemi(
                kalem_no=fatura_kalem_sozlugu["kalem_no"],
                siparis_kalem_no=fatura_kalem_sozlugu["siparis_kalem_no"],
                miktar=Decimal(fatura_kalem_sozlugu["miktar"]),
                birim_fiyat=Decimal(fatura_kalem_sozlugu["birim_fiyat"]),
                mal_kabul_dagitimi=dagitimlar,
                iskonto_turu=fatura_kalem_sozlugu["iskonto_turu"],
                iskonto_degeri=Decimal(fatura_kalem_sozlugu["iskonto_degeri"]),
            )
            kalemler.append(fatura_kalemi)

        iptal_sozlugu = fatura_sozlugu["iptal_bilgisi"]
        iptal_bilgisi = IptalBilgisi(
            iptal_edildi=iptal_sozlugu["iptal_edildi"],
            iptal_gerekcesi=iptal_sozlugu["iptal_gerekcesi"],
            iptal_notu=iptal_sozlugu["iptal_notu"],
            iptal_tarihi=iptal_sozlugu["iptal_tarihi"],
        )
        fatura = Fatura(
            fatura_no=fatura_sozlugu["fatura_no"],
            tedarikci_fatura_no=fatura_sozlugu["tedarikci_fatura_no"],
            siparis_no=fatura_sozlugu["siparis_no"],
            fatura_kalemleri=kalemler,
            kayit_tarihi=fatura_sozlugu["kayit_tarihi"],
            durum=fatura_sozlugu["durum"],
            bloke_neden_kodlari=fatura_sozlugu["bloke_neden_kodlari"],
            karar_gerekcesi=fatura_sozlugu["karar_gerekcesi"],
            karar_notu=fatura_sozlugu["karar_notu"],
            iptal_bilgisi=iptal_bilgisi,
        )
        faturalar.append(fatura)
    yeni["faturalar"] = faturalar

    
    karantina_kararlari = []
    for karar_sozlugu in ham_veri["karantina_kararlari"]:
        karantina_karari = KarantinaKarari(
            mal_kabul_no=karar_sozlugu["mal_kabul_no"],
            mal_kabul_kalem_no=karar_sozlugu["mal_kabul_kalem_no"],
            karar=karar_sozlugu["karar"],
            miktar=Decimal(karar_sozlugu["miktar"]),
            karar_gerekcesi=karar_sozlugu["karar_gerekcesi"],
            kayit_tarihi=karar_sozlugu["kayit_tarihi"],
            karar_notu=karar_sozlugu["karar_notu"],
        )
        karantina_kararlari.append(karantina_karari)
    yeni["karantina_kararlari"] = karantina_kararlari
    return yeni


def bos_veri_olustur():
    """Hiç kayıt yokken veri dosyasının hâlini döndürür (boş şema).

    Boş verinin tek evi: yukle dosya yoksa bunu döndürür, senaryolar test
    dosyasını bununla temizler (E102). Sayaçlar 0 olduğu için ilk numara
    "-0001" olur.

    Returns:
        7 anahtarlı sözlük: veri_surumu, sayaclar (TED, SAS, MKB, FTR = 0)
        ve beş boş liste (tedarikciler, siparisler, mal_kabuller,
        faturalar, karantina_kararlari).
    """
    return {
        "veri_surumu": VERI_SURUMU,
        "sayaclar": {"TED": 0, "SAS": 0, "MKB": 0, "FTR": 0},
        "tedarikciler": [],
        "siparisler": [],
        "mal_kabuller": [],
        "faturalar": [],
        "karantina_kararlari": [],
    }

def yukle(dosya_yolu):
    """Veri dosyasını okuyup servisin verisine çevirir.

    Dosya yoksa boş veriyle başlar (ilk açılış, F4). Dosya bozuksa asla
    boş başlamaz, DepolamaError verir; dosyaya dokunulmaz (F2).

    Args:
        dosya_yolu: Okunacak dosya, ör. "veri.json".

    Returns:
        Servisin verisi (nesneye_cevir'in döndürdüğü sözlük) ya da
        dosya yoksa bos_veri_olustur().

    Raises:
        DepolamaError: JSON okunamazsa (10a), yapısı bozuksa (10c) ya da
            veri sürümü uyumsuzsa (10d).
    """
    try:
        with open(dosya_yolu, "r", encoding="utf-8") as dosya:
            ham_veri = json.load(dosya)
    except FileNotFoundError:
        return bos_veri_olustur()
    except json.JSONDecodeError as hata:
        raise DepolamaError(
            f"Veri dosyası okunamadı (JSON bozuk): {dosya_yolu}"
        ) from hata
    try:
        veri = nesneye_cevir(ham_veri)
    except (KeyError, InvalidOperation, TypeError) as hata:
        raise DepolamaError(
            f"Veri dosyasının yapısı bozuk: {dosya_yolu}"
        ) from hata
    return veri


if __name__ == "__main__":
    print("--- kaydet → yukle (aynı veri geri gelir) ---")
    tolerans = ToleransKopyasi(
        fazla_teslimat_yuzde=Decimal("10"),
        fazla_teslimat_tl=Decimal("1000"),
        asiri_sinir_yuzde=Decimal("25"),
        asiri_sinir_tl=Decimal("5000"),
        fiyat_ust_yuzde=Decimal("5"),
        fiyat_ust_tl=Decimal("500"),
        fiyat_alt_yuzde=Decimal("10"),
        fiyat_alt_tl=Decimal("1000"),
        kucuk_fark_esigi=Decimal("10"),
    )
    kalem = SiparisKalemi(
        kalem_no=10, malzeme_adi="Defter", miktar=Decimal("100"), birim="adet",
        birim_fiyat=Decimal("50"), kategori="SARF", tolerans=tolerans,
    )
    siparis = Siparis(
        siparis_no="SAS-0001", tedarikci_kodu="TED-0001",
        siparis_kalemleri=[kalem], kayit_tarihi="2026-11-02",
    )
    veri = bos_veri_olustur()
    veri["sayaclar"]["TED"] = 1
    veri["sayaclar"]["SAS"] = 1
    veri["tedarikciler"] = [Tedarikci("TED-0001", "ABC Kırtasiye")]
    veri["siparisler"] = [siparis]
    kaydet(veri, "test_veri.json")
    print(yukle("test_veri.json") == veri)  # True

    print("--- hata yolları ---")
    denemeler = [
        ("bozuk JSON (10a)", "{ bozuk"),
        ("yapısı bozuk (10c)", '{"veri_surumu": 1}'),
        ("sürüm 2 (10d)", '{"veri_surumu": 2}'),
    ]
    for ad, icerik in denemeler:
        with open("test_veri.json", "w", encoding="utf-8") as dosya:
            dosya.write(icerik)
        try:
            yukle("test_veri.json")
            print(f"{ad}: hata gelmedi (KALDI)")
        except DepolamaError as hata:
            print(f"{ad}: {hata}")
    try:
        kaydet(bos_veri_olustur(), "olmayan_klasor/deneme.json")
    except DepolamaError as hata:
        print(f"yazılamayan dosya (10b): {hata}")
    print(yukle("olmayan_dosya.json")["sayaclar"])  # dosya yok → sayaçlar 0