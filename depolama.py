import json
import os 
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
    Odeme,
    OdemeKalemi,
    Siparis,
    SiparisKalemi,
    Talep,
    TalepKalemi,
    Tedarikci,
    Teklif,
    TeklifKalemi,
    ToleransKopyasi,
)

def sozluge_cevir(veri):
    """Servisin verisini JSON'a yazılmaya hazır sözlüğe çevirir.

    veri_surumu ve sayaclar olduğu gibi kopyalanır; belge
    listelerindeki her nesne asdict ile sözlüğe döner. Decimal'lere
    dokunulmaz; onları kaydet metne çevirir. Gelen veri değişmez.

    Args:
        veri: Servisin verisi; anahtarlar veri_surumu, sayaclar ve
            sekiz belge listesi (tedarikciler, siparisler, mal_kabuller,
            faturalar, karantina_kararlari, talepler, teklifler,
            odemeler). Yeni liste eklenince bu fonksiyon değişmez.

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
    """Servisin verisini JSON dosyasına güvenli yazar (B3, E126).

    Önce nesneler sözlüğe çevrilir; Decimal'ler yazılırken metne döner
    (default=str). Veri önce yanındaki geçici dosyaya ("veri.json.tmp")
    yazılır ve diske indirilir (flush + fsync); yazma bitince os.replace
    geçici dosyayı tek hamlede asıl dosyanın yerine koyar (atomik). Yazma
    yarıda kalırsa asıl dosya eski hâliyle durur; geçici dosya silinir.

    Args:
        veri: Servisin verisi (sozluge_cevir'deki şema).
        dosya_yolu: Yazılacak dosya, ör. "veri.json" ya da Path.

    Raises:
        DepolamaError: Dosya yazılamazsa (klasör yok, izin yok, disk dolu;
            10b). Asıl dosya değişmez.
    """
    sozluk = sozluge_cevir(veri)
    gecici_yol = f"{dosya_yolu}.tmp"
    try:
        with open(gecici_yol, "w", encoding="utf-8") as dosya:
            json.dump(sozluk, dosya, default=str, ensure_ascii=False, indent=4)
            dosya.flush()
            os.fsync(dosya.fileno())
        os.replace(gecici_yol, dosya_yolu)
    except OSError as hata:
        if os.path.exists(gecici_yol):
            os.remove(gecici_yol)
        raise DepolamaError(
            f"Kaydedilemedi: {dosya_yolu}",
            kod="10b",
        ) from hata

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
        DepolamaError: veri_surumu programınkine eşit değilse (10d); sürüm 1
            dosyayı yukle buraya gelmeden dönüştürür, yani 10d sadece
            bilinmeyen ya da programdan yeni sürümde çıkar.
        KeyError, InvalidOperation, TypeError: Yapı bozuksa; yukle bunları
            DepolamaError'a çevirir (10c).
    """
    if ham_veri["veri_surumu"] != VERI_SURUMU:
        raise DepolamaError(
            f"Veri dosyasının sürümü {ham_veri['veri_surumu']}, "
            f"programın sürümü {VERI_SURUMU}; dosya okunamıyor",
            kod="10d",
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
                talep_no=siparis_kalem_sozlugu["talep_no"],
                talep_kalem_no=siparis_kalem_sozlugu["talep_kalem_no"],
                teklif_no=siparis_kalem_sozlugu["teklif_no"],
                teklif_kalem_no=siparis_kalem_sozlugu["teklif_kalem_no"],
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
            karar_tarihi=fatura_sozlugu.get("karar_tarihi"),
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

    talepler = []
    for talep_sozlugu in ham_veri["talepler"]:
        kalemler = []
        for talep_kalem_sozlugu in talep_sozlugu["talep_kalemleri"]:
            tahmini_fiyat = talep_kalem_sozlugu["tahmini_birim_fiyat"]
            talep_kalemi = TalepKalemi(
                kalem_no=talep_kalem_sozlugu["kalem_no"],
                malzeme_adi=talep_kalem_sozlugu["malzeme_adi"],
                miktar=Decimal(talep_kalem_sozlugu["miktar"]),
                birim=talep_kalem_sozlugu["birim"],
                kategori=talep_kalem_sozlugu["kategori"],
                tahmini_birim_fiyat=(
                    Decimal(tahmini_fiyat) if tahmini_fiyat is not None else None
                ),
            )
            kalemler.append(talep_kalemi)

        iptal_sozlugu = talep_sozlugu["iptal_bilgisi"]
        iptal_bilgisi = IptalBilgisi(
            iptal_edildi=iptal_sozlugu["iptal_edildi"],
            iptal_gerekcesi=iptal_sozlugu["iptal_gerekcesi"],
            iptal_notu=iptal_sozlugu["iptal_notu"],
            iptal_tarihi=iptal_sozlugu["iptal_tarihi"],
        )
        talep = Talep(
            talep_no=talep_sozlugu["talep_no"],
            talep_eden=talep_sozlugu["talep_eden"],
            talep_kalemleri=kalemler,
            kayit_tarihi=talep_sozlugu["kayit_tarihi"],
            durum=talep_sozlugu["durum"],
            iptal_bilgisi=iptal_bilgisi,
            karar_gerekcesi=talep_sozlugu["karar_gerekcesi"],
            karar_notu=talep_sozlugu["karar_notu"],
            karar_tarihi=talep_sozlugu["karar_tarihi"],
        )
        talepler.append(talep)
    yeni["talepler"] = talepler

    teklifler = []
    for teklif_sozlugu in ham_veri["teklifler"]:
        kalemler = []
        for teklif_kalem_sozlugu in teklif_sozlugu["teklif_kalemleri"]:
            teklif_kalemi = TeklifKalemi(
                kalem_no=teklif_kalem_sozlugu["kalem_no"],
                malzeme_adi=teklif_kalem_sozlugu["malzeme_adi"],
                miktar=Decimal(teklif_kalem_sozlugu["miktar"]),
                birim=teklif_kalem_sozlugu["birim"],
                kategori=teklif_kalem_sozlugu["kategori"],
                birim_fiyat=Decimal(teklif_kalem_sozlugu["birim_fiyat"]),
                iskonto_turu=teklif_kalem_sozlugu["iskonto_turu"],
                iskonto_degeri=Decimal(teklif_kalem_sozlugu["iskonto_degeri"]),
                talep_no=teklif_kalem_sozlugu["talep_no"],
                talep_kalem_no=teklif_kalem_sozlugu["talep_kalem_no"],
            )
            kalemler.append(teklif_kalemi)

        iptal_sozlugu = teklif_sozlugu["iptal_bilgisi"]
        iptal_bilgisi = IptalBilgisi(
            iptal_edildi=iptal_sozlugu["iptal_edildi"],
            iptal_gerekcesi=iptal_sozlugu["iptal_gerekcesi"],
            iptal_notu=iptal_sozlugu["iptal_notu"],
            iptal_tarihi=iptal_sozlugu["iptal_tarihi"],
        )
        teklif = Teklif(
            teklif_no=teklif_sozlugu["teklif_no"],
            tedarikci_kodu=teklif_sozlugu["tedarikci_kodu"],
            teklif_kalemleri=kalemler,
            kayit_tarihi=teklif_sozlugu["kayit_tarihi"],
            durum=teklif_sozlugu["durum"],
            tedarikci_teklif_no=teklif_sozlugu["tedarikci_teklif_no"],
            iptal_bilgisi=iptal_bilgisi,
            karar_gerekcesi=teklif_sozlugu["karar_gerekcesi"],
            karar_notu=teklif_sozlugu["karar_notu"],
            karar_tarihi=teklif_sozlugu["karar_tarihi"],
        )
        teklifler.append(teklif)
    yeni["teklifler"] = teklifler

    odemeler = []
    for odeme_sozlugu in ham_veri["odemeler"]:
        kalemler = []
        for odeme_kalem_sozlugu in odeme_sozlugu["odeme_kalemleri"]:
            odeme_kalemi = OdemeKalemi(
                kalem_no=odeme_kalem_sozlugu["kalem_no"],
                fatura_no=odeme_kalem_sozlugu["fatura_no"],
                tutar=Decimal(odeme_kalem_sozlugu["tutar"]),
            )
            kalemler.append(odeme_kalemi)

        iptal_sozlugu = odeme_sozlugu["iptal_bilgisi"]
        iptal_bilgisi = IptalBilgisi(
            iptal_edildi=iptal_sozlugu["iptal_edildi"],
            iptal_gerekcesi=iptal_sozlugu["iptal_gerekcesi"],
            iptal_notu=iptal_sozlugu["iptal_notu"],
            iptal_tarihi=iptal_sozlugu["iptal_tarihi"],
        )
        odeme = Odeme(
            odeme_no=odeme_sozlugu["odeme_no"],
            tedarikci_kodu=odeme_sozlugu["tedarikci_kodu"],
            odeme_yontemi=odeme_sozlugu["odeme_yontemi"],
            odeme_kalemleri=kalemler,
            kayit_tarihi=odeme_sozlugu["kayit_tarihi"],
            odeme_notu=odeme_sozlugu["odeme_notu"],
            iptal_bilgisi=iptal_bilgisi,
        )
        odemeler.append(odeme)
    yeni["odemeler"] = odemeler
    return yeni


def bos_veri_olustur():
    """Hiç kayıt yokken veri dosyasının hâlini döndürür (boş şema).

    Boş verinin tek evi: yukle dosya yoksa bunu döndürür, senaryolar test
    dosyasını bununla temizler (E102). Sayaçlar 0 olduğu için ilk numara
    "-0001" olur.

    Returns:
        10 anahtarlı sözlük: veri_surumu, sayaclar (TED, SAS, MKB, FTR,
        TLP, TKL, ODM = 0) ve sekiz boş liste (tedarikciler, siparisler,
        mal_kabuller, faturalar, karantina_kararlari, talepler, teklifler,
        odemeler).
    """
    return {
        "veri_surumu": VERI_SURUMU,
        "sayaclar": {
            "TED": 0, "SAS": 0, "MKB": 0, "FTR": 0,
            "TLP": 0, "TKL": 0, "ODM": 0,
        },
        "tedarikciler": [],
        "siparisler": [],
        "mal_kabuller": [],
        "faturalar": [],
        "karantina_kararlari": [],
        "talepler": [],
        "teklifler": [],
        "odemeler": [],
    }

def surum_1den_2ye(ham_veri):
    """Sürüm 1 veri dosyasını sürüm 2 şekline getirir (v1b, E120, E131).

    Eski veriye dokunmaz, sadece eksikleri ekler: talep, teklif ve ödeme
    listeleri boş, sayaçları 0; her sipariş kalemine dört bağ alanı None
    (talepsiz sipariş). Etiket doğrudan 2 yazılır, VERI_SURUMU'ndan
    alınmaz: bu adım her zaman 1'den 2'ye. Dosyaya yazmaz; ilk kayıtta
    servis dosyayı sürüm 2 olarak yazar.

    Args:
        ham_veri: json.load'un döndürdüğü sürüm 1 sözlüğü.

    Returns:
        Aynı sözlük, sürüm 2 şeklinde.
    """
    ham_veri["veri_surumu"] = 2
    ham_veri["sayaclar"]["TLP"] = 0
    ham_veri["sayaclar"]["TKL"] = 0
    ham_veri["sayaclar"]["ODM"] = 0
    ham_veri["talepler"] = []
    ham_veri["teklifler"] = []
    ham_veri["odemeler"] = []
    for siparis in ham_veri["siparisler"]:
        for siparis_kalemi in siparis["siparis_kalemleri"]:
            siparis_kalemi["talep_no"] = None
            siparis_kalemi["talep_kalem_no"] = None
            siparis_kalemi["teklif_no"] = None
            siparis_kalemi["teklif_kalem_no"] = None
    return ham_veri


def yukle(dosya_yolu):
    """Veri dosyasını okuyup servisin verisine çevirir.

    Dosya yoksa boş veriyle başlar (ilk açılış, F4). Dosya bozuksa asla
    boş başlamaz, DepolamaError verir; dosyaya dokunulmaz (F2).
    Sürüm 1 dosya önce surum_1den_2ye ile sürüm 2 şekline getirilir
    (E131); v2'de altına "sürüm 2 ise 2'den 3'e" satırı eklenir.

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
            f"Veri dosyası okunamadı (JSON bozuk): {dosya_yolu}",
            kod="10a",
        ) from hata
    try:
        if ham_veri["veri_surumu"] == 1:
            ham_veri = surum_1den_2ye(ham_veri)
        veri = nesneye_cevir(ham_veri)
    except (KeyError, InvalidOperation, TypeError) as hata:
        raise DepolamaError(
            f"Veri dosyasının yapısı bozuk: {dosya_yolu}",
            kod="10c",
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

    print("--- sürüm 1 dosyası dönüştürülerek açılır ---")
    surum_1_metni = (
        '{"veri_surumu": 1, "sayaclar": {"TED": 0, "SAS": 0, "MKB": 0, "FTR": 0}, '
        '"tedarikciler": [], "siparisler": [], "mal_kabuller": [], '
        '"faturalar": [], "karantina_kararlari": []}'
    )
    with open("test_veri.json", "w", encoding="utf-8") as dosya:
        dosya.write(surum_1_metni)
    donusen = yukle("test_veri.json")
    print(donusen["veri_surumu"], donusen["sayaclar"], donusen["talepler"])
    # 2 {'TED': 0, 'SAS': 0, 'MKB': 0, 'FTR': 0, 'TLP': 0, 'TKL': 0, 'ODM': 0} []

    print("--- hata yolları ---")
    denemeler = [
        ("bozuk JSON (10a)", "{ bozuk"),
        ("yapısı bozuk (10c)", '{"veri_surumu": 1}'),
        ("programdan yeni sürüm 3 (10d)", '{"veri_surumu": 3}'),
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