from decimal import Decimal
from modeller import Tedarikci , ToleransKopyasi , SiparisKalemi , Siparis, MalKabulDagitimi, FaturaKalemi , MalKabul,Fatura,IptalBilgisi,MalKabulKalemi
import json
from dataclasses import asdict
from ayarlar import VERI_SURUMU


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
    """
    sozluk = sozluge_cevir(veri)
    with open(dosya_yolu, "w", encoding="utf-8") as dosya:
        json.dump(sozluk, dosya, default=str, ensure_ascii=False,
                  indent=4)

           
def nesneye_cevir(ham_veri):
    yeni = {}
    yeni["veri_surumu"] = ham_veri["veri_surumu"]
    yeni["sayaclar"] = ham_veri["sayaclar"]
    tedarikciler = []
    for tedarikci_sozlugu in ham_veri["tedarikciler"]:
        tedarikci = Tedarikci(tedarikci_kodu=tedarikci_sozlugu["tedarikci_kodu"], 
                              tedarikci_adi=tedarikci_sozlugu["tedarikci_adi"],
                              firma_adi=tedarikci_sozlugu["firma_adi"])
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
                miktar_tavani=Decimal(miktar_tavani) if miktar_tavani is not None else None,
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



    mal_kabulleri = []
    for mal_kabul_sozlugu in ham_veri["mal_kabuller"]:
        kalem = []
        for mal_kabul_kalem_sozlugu in mal_kabul_sozlugu["mal_kabul_kalemleri"]:
            mal_kabul_kalemi = MalKabulKalemi(kalem_no=mal_kabul_kalem_sozlugu["kalem_no"],
                                              siparis_kalem_no=mal_kabul_kalem_sozlugu["siparis_kalem_no"],
                                              kabul_edilen_miktar=Decimal(mal_kabul_kalem_sozlugu["kabul_edilen_miktar"]),
                                              karantina_miktari=Decimal(mal_kabul_kalem_sozlugu["karantina_miktari"]),
                                              karantina_nedeni=mal_kabul_kalem_sozlugu["karantina_nedeni"],
                                              kapida_reddedilen_miktar=Decimal(mal_kabul_kalem_sozlugu["kapida_reddedilen_miktar"]),
                                              kapida_red_nedeni=mal_kabul_kalem_sozlugu["kapida_red_nedeni"])
            kalem.append(mal_kabul_kalemi)

        
        iptaller_sozlugu = mal_kabul_sozlugu["iptal_bilgisi"]
        iptaller = IptalBilgisi(iptal_edildi=iptaller_sozlugu["iptal_edildi"],
                                iptal_gerekcesi=iptaller_sozlugu["iptal_gerekcesi"],
                                iptal_notu=iptaller_sozlugu["iptal_notu"],
                                iptal_tarihi=iptaller_sozlugu["iptal_tarihi"])
        

        mal_kabul = MalKabul(mal_kabul_no=mal_kabul_sozlugu["mal_kabul_no"],
                             siparis_no=mal_kabul_sozlugu["siparis_no"],
                             mal_kabul_kalemleri=kalem,
                             kayit_tarihi=mal_kabul_sozlugu["kayit_tarihi"],
                             mal_kabul_notu=mal_kabul_sozlugu["mal_kabul_notu"],
                             iptal_bilgisi=iptaller)
        mal_kabulleri.append(mal_kabul)
    yeni["mal_kabuller"] = mal_kabulleri

    
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

    yeni["karantina_kararlari"] = []
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
    try:
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            okunan_dosya = json.load(f)
    except FileNotFoundError:
        return bos_veri_olustur()
    cevirme = nesneye_cevir(okunan_dosya)
    return cevirme

    
    
    
    
    
    
    
    
if __name__ == "__main__":
    tedarikci = Tedarikci(tedarikci_kodu="TED-0001", tedarikci_adi="ABC Kirtasiye")
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
    kalem = SiparisKalemi(kalem_no=10, malzeme_adi="A4 Kagit", miktar=Decimal("100"), birim="adet", birim_fiyat=Decimal("50"),kategori="SARF", tolerans=tolerans)
    siparis = Siparis(siparis_no="SAS-0001" , tedarikci_kodu="TED-0001" , siparis_kalemleri=[kalem], kayit_tarihi="2026-11-02")

    veri = {"veri_surumu":1, "sayaclar":{"TED": 1, "SAS": 1, "MKB": 0, "FTR": 0}, "tedarikciler":[tedarikci], "siparisler":[siparis],  "mal_kabuller":[], "faturalar":[], "karantina_kararlari":[]}

    print(veri)
    print(asdict(tedarikci))
    siparis_sozluk = asdict(siparis)
    print(siparis_sozluk["siparis_kalemleri"][0]["tolerans"])
    print(json.dumps(siparis_sozluk , default=str))  # görmek için ekrana yazdırır.
    print(sozluge_cevir(veri))
    print(kaydet(veri, "test_veri.json"))
    sozluk = {"tedarikci_kodu": "TED-0001", "tedarikci_adi": "ABC", "firma_adi": None}
    tedarikci = Tedarikci(tedarikci_kodu=sozluk["tedarikci_kodu"], tedarikci_adi=sozluk["tedarikci_adi"], firma_adi=sozluk["firma_adi"])
    print(tedarikci)
    sozluk2 = {"mal_kabul_no": "MKB-0001", "miktar": "100"}
    mal_kabul = MalKabulDagitimi(mal_kabul_no=sozluk2["mal_kabul_no"] , miktar=Decimal(sozluk2["miktar"]))
    print(mal_kabul)
    sozluk3 = {
    "kalem_no": 10,
    "siparis_kalem_no": 10,
    "miktar": "100",
    "birim_fiyat": "50",
    "mal_kabul_dagitimi": [{"mal_kabul_no": "MKB-0001", "miktar": "100"}],
    "iskonto_turu": "ORAN",
    "iskonto_degeri": "0",
    },


            

    


