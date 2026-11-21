"""Satın Alma Modülü'nün terminal menüsü: kullanıcıyla konuşan tek modül.

Menü hiçbir iş kuralı kontrol etmez (E62): metni para.py çevirir,
kuralları servis kontrol eder. Menü sadece soruyu sorar, hatayı yakalar ve
hata sınıfına göre davranır (hatalar tabındaki "Menü ne yapar" sütunu):
GecersizGirisError ve KayitBulunamadiError gelince alan tekrar sorulur;
IslemYapilamazError ana menüde yakalanır, mesaj gösterilip menüye dönülür.
Menü servisin iç verisine dokunmaz; okumak için genel metotları çağırır
(E100, E112).
"""

from ayarlar import (
    IPTAL_GEREKCELERI,
    KARANTINA_KARAR_GEREKCELERI,
    KARAR_GEREKCELERI,
    VERI_DOSYASI,
)
from hatalar import (
    DepolamaError,
    GecersizGirisError,
    KayitBulunamadiError,
    SatinAlmaError,
)
from para import tutara_cevir
from servis import SatinAlmaServisi


# ---------------------------------------------------------------------------
# Giriş yardımcıları
# ---------------------------------------------------------------------------

def tutar_sor(soru, bos_olabilir=False):
    """Kullanıcıdan tutar alır; geçerli sayı yazılana kadar tekrar sorar.

    Metni tutara_cevir çevirir (virgül kabul edilir). Çevrilemezse hata
    mesajı gösterilir ve aynı soru yeniden sorulur. Eksi ya da sıfır
    kontrolü burada yapılmaz; o servisin işidir.

    Args:
        soru: Ekrana yazılacak soru, ör. "Miktar: ".
        bos_olabilir: True ise boş Enter kabul edilir ve None döner
            (isteğe bağlı alanlar: iskonto, miktar tavanı, yanlış ürün).

    Returns:
        Girilen tutar (Decimal); bos_olabilir ise boş girişte None.
    """
    while True:
        metin = input(soru)
        if bos_olabilir and not metin.strip():
            return None
        try:
            return tutara_cevir(metin)
        except GecersizGirisError as hata:
            print(hata)


def tam_sayi_sor(soru):
    """Kullanıcıdan tam sayı alır; sayı yazılana kadar tekrar sorar.

    Args:
        soru: Ekrana yazılacak soru, ör. "Kalem no: ".

    Returns:
        Girilen sayı (int).
    """
    while True:
        metin = input(soru)
        try:
            return int(metin)
        except ValueError:
            print(f"'{metin}' geçersiz; bir sayı yazın.")


def secenek_sor(secenekler, soru):
    """Sözlüğün değerlerini numaralı listeler, seçilenin anahtarını döndürür.

    Ekranda numara 1'den başlar, listede indeks 0'dan; bu yüzden seçilen
    numaradan 1 çıkarılır. Sayı değilse ya da aralık dışındaysa tekrar
    sorulur.

    Args:
        secenekler: {kod: ekranda görünecek açıklama} sözlüğü.
        soru: Ekrana yazılacak soru, ör. "Gerekçe numarası: ".

    Returns:
        Seçilen kod, ör. "MUKERRER_GIRIS".
    """
    kodlar = list(secenekler.keys())
    sira = 1
    for kod in kodlar:
        print(f"  {sira} - {secenekler[kod]}")
        sira += 1

    while True:
        numara = tam_sayi_sor(soru)
        if 1 <= numara <= len(kodlar):
            return kodlar[numara - 1]
        print(f"Geçersiz numara; 1 ile {len(kodlar)} arasında olmalı.")


def gerekce_sor(gerekceler):
    """Gerekçeyi numarayla seçtirir, sonra isteğe bağlı not sorar.

    "DIGER seçildiyse not zorunlu" kuralını servis kontrol eder (E62);
    burada sadece sorulur.

    Args:
        gerekceler: O işlemin gerekçe sözlüğü, ör. IPTAL_GEREKCELERI["FATURA"].

    Returns:
        (gerekçe kodu, not) ikilisi; not boşsa None.
    """
    kod = secenek_sor(gerekceler, "Gerekçe numarası: ")
    notu = input("Not (boş bırakılabilir): ")
    if not notu.strip():
        notu = None
    return kod, notu


def belge_numarasi_sor(bul, soru):
    """Belge numarasını kayıt bulunana kadar sorar (7a, 8a, 9a, 11a, 15a, 16a).

    Args:
        bul: Servisin okuma metodu, ör. servis.fatura_bul.
        soru: Ekrana yazılacak soru, ör. "Fatura numarası: ".

    Returns:
        Bulunan belge nesnesi.
    """
    while True:
        numara = input(soru).strip()
        try:
            return bul(numara)
        except KayitBulunamadiError as hata:
            print(hata)


def nedenli_metin(nedenli_miktarlar):
    """NedenliMiktar listesini "2 IADE_BEKLIYOR, 2 KARAR_BEKLIYOR" yapar.

    Args:
        nedenli_miktarlar: NedenliMiktar listesi.

    Returns:
        Birleşik metin; liste boşsa "yok".
    """
    parcalar = []
    for nedenli in nedenli_miktarlar:
        parcalar.append(f"{nedenli.miktar} {nedenli.neden}")
    if not parcalar:
        return "yok"
    return ", ".join(parcalar)


def bulgulari_yazdir(sonuc):
    """Eşleştirme sonucunun bulgularını kalem kalem yazar (E63).

    Args:
        sonuc: EslestirmeSonucu.
    """
    bulgular = sonuc.bulgular()
    if not bulgular:
        print("Sapma yok.")
        return
    for bulgu in bulgular:
        satir = (f"Kalem {bulgu.kalem_no}: {bulgu.neden_kodu} · "
                 f"beklenen {bulgu.beklenen} · gelen {bulgu.gerceklesen} · "
                 f"izin {bulgu.izin_verilen_sapma}")
        if bulgu.belirleyici_sinir is not None:
            satir += f" ({bulgu.belirleyici_sinir})"
        print(satir)


# ---------------------------------------------------------------------------
# Sipariş, mal kabul, fatura
# ---------------------------------------------------------------------------

def menu_tedarikci_ekle(servis):
    """Yeni tedarikçiyi kullanıcıdan alıp kaydettirir ve döndürür.

    Firma adı isteğe bağlıdır; boş bırakılırsa None gönderilir. Tedarikçi
    kodu sorulmaz, servis üretir. Ad boşsa (1a) bilgiler yeniden sorulur.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.

    Returns:
        Eklenen Tedarikci (sipariş ekranındaki kısayol kullanır, E65).
    """
    while True:
        tedarikci_adi = input("Tedarikçi adı: ")
        firma_adi = input("Firma adı (boş bırakılabilir): ")
        if not firma_adi.strip():
            firma_adi = None
        try:
            tedarikci = servis.tedarikci_ekle(tedarikci_adi=tedarikci_adi,
                                              firma_adi=firma_adi)
            print(f"Tedarikçi eklendi: {tedarikci.tedarikci_kodu}")
            return tedarikci
        except GecersizGirisError as hata:
            print(hata)


def tedarikci_sec(servis):
    """Tedarikçileri listeler, kodu sorar; "Y" ile yeni tedarikçi ekletir (E65).

    Kodun kayıtlı olup olmadığını servis kontrol eder (2a).

    Args:
        servis: Açık SatinAlmaServisi nesnesi.

    Returns:
        Seçilen ya da yeni eklenen tedarikçinin kodu.
    """
    for tedarikci in servis.tedarikcileri_listele():
        print(f"  {tedarikci.tedarikci_kodu} - {tedarikci.tedarikci_adi}")
    secim = input("Tedarikçi kodu (yeni tedarikçi için Y): ").strip()
    if secim.upper() == "Y":
        return menu_tedarikci_ekle(servis).tedarikci_kodu
    return secim


def siparis_kalemlerini_sor():
    """Sipariş kalemlerini malzeme adı boş bırakılana kadar sorar.

    İskonto ve miktar tavanı isteğe bağlıdır; boş bırakılan alan sözlüğe
    konmaz, servis varsayılanı kullanır.

    Returns:
        Kalem sözlüklerinin listesi (siparis_ac'ın beklediği biçim).
    """
    kalemler = []
    while True:
        malzeme_adi = input("Malzeme adı (bitirmek için boş Enter): ")
        if not malzeme_adi.strip():
            return kalemler
        kalem = {
            "malzeme_adi": malzeme_adi,
            "miktar": tutar_sor("  Miktar: "),
            "birim": input("  Birim: "),
            "birim_fiyat": tutar_sor("  Birim fiyat: "),
            "kategori": input("  Kategori (SARF / STRATEJIK): ").strip().upper(),
        }
        iskonto_turu = input("  İskonto türü (ORAN / TUTAR, yoksa boş): ")
        if iskonto_turu.strip():
            kalem["iskonto_turu"] = iskonto_turu.strip().upper()
            kalem["iskonto_degeri"] = tutar_sor("  İskonto değeri: ")
        miktar_tavani = tutar_sor("  Miktar tavanı (yoksa boş): ",
                                  bos_olabilir=True)
        if miktar_tavani is not None:
            kalem["miktar_tavani"] = miktar_tavani
        kalemler.append(kalem)


def menu_siparis_ac(servis):
    """Tedarikçi ve kalemleri alıp yeni sipariş açtırır.

    Tedarikçi bulunamazsa (2a) sadece tedarikçi, kalem hatasında (2b-2g,
    13a) sadece kalemler yeniden sorulur. Kalem no, tolerans ve tarih
    servisten gelir.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    tedarikci_kodu = tedarikci_sec(servis)
    kalemler = siparis_kalemlerini_sor()
    while True:
        try:
            siparis = servis.siparis_ac(tedarikci_kodu, kalemler)
            print(f"Sipariş açıldı: {siparis.siparis_no} · {siparis.durum} "
                  f"· toplam {siparis.genel_toplam()}")
            return
        except KayitBulunamadiError as hata:
            print(hata)
            tedarikci_kodu = tedarikci_sec(servis)
        except GecersizGirisError as hata:
            print(hata)
            print("Kalemleri yeniden girin.")
            kalemler = siparis_kalemlerini_sor()


def menu_siparis_onayla(servis):
    """Sipariş numarasını alıp siparişi onaylatır.

    Numara bulunamazsa tekrar sorulur (3a). Sipariş iptal edilmiş ya da
    zaten onaylıysa (3b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    siparis = belge_numarasi_sor(servis.siparis_bul, "Sipariş numarası: ")
    servis.siparis_onayla(siparis.siparis_no)
    print(f"Sipariş onaylandı: {siparis.siparis_no}")


def menu_mal_kabul(servis):
    """Siparişin satırlarını gösterip gelen miktarları alır, mal kabul kaydettirir.

    Satırlar siparişten sırayla gelir (kalem no sistemden, E3). Miktar
    hatasında (4f, 4g, 4h) satırlar yeniden sorulur. Sonuçta her satırın
    kabul / karantina / kapıda red miktarı ve belirleyici sınır (E75), bekleyen
    fatura eşleştiyse numarası (R2) gösterilir. Sipariş onaylı değilse, iptal
    edilmişse ya da aktif mal kabulü varsa (4b, 4c) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    siparis = belge_numarasi_sor(servis.siparis_bul, "Sipariş numarası: ")
    tir_cevabi = input("Tır hâlâ kapıda mı? (E / H, boş = E): ").strip().upper()
    tir_kapida = tir_cevabi != "H"

    while True:
        kalemler = []
        for siparis_kalemi in siparis.siparis_kalemleri:
            print(f"Kalem {siparis_kalemi.kalem_no} · {siparis_kalemi.malzeme_adi} "
                  f"(sipariş {siparis_kalemi.miktar} {siparis_kalemi.birim})")
            kalem = {
                "siparis_kalem_no": siparis_kalemi.kalem_no,
                "gelen_miktar": tutar_sor("  Gelen miktar: "),
            }
            yanlis_urun = tutar_sor("  Yanlış ürün miktarı (yoksa boş): ",
                                    bos_olabilir=True)
            if yanlis_urun is not None:
                kalem["yanlis_urun_miktari"] = yanlis_urun
            kalemler.append(kalem)
        try:
            sonuc = servis.mal_kabul_kaydet(siparis.siparis_no, kalemler,
                                            tir_kapida=tir_kapida)
            break
        except GecersizGirisError as hata:
            print(hata)

    print(f"Mal kabul kaydedildi: {sonuc.mal_kabul.mal_kabul_no}")
    for kalem in sonuc.mal_kabul.mal_kabul_kalemleri:
        satir = (f"Kalem {kalem.siparis_kalem_no}: kabul "
                 f"{kalem.kabul_edilen_miktar} · karantina "
                 f"{nedenli_metin(kalem.karantinalar)} · kapıda red "
                 f"{nedenli_metin(kalem.kapida_redler)}")
        kova = sonuc.kova_sonuclari[kalem.siparis_kalem_no]
        if kova.belirleyici_sinir is not None:
            satir += f" · sınır: {kova.belirleyici_sinir}"
        print(satir)
    for fatura_no in sonuc.eslesen_faturalar:
        fatura = servis.fatura_bul(fatura_no)
        print(f"Bekleyen fatura eşleşti: {fatura_no} · {fatura.durum}")


def menu_fatura(servis):
    """Siparişin satırlarını gösterip faturadaki miktar ve fiyatları alır, fatura kaydettirir.

    Satırlar siparişten sırayla gelir (E3); miktarı 0 girilen satırın fiyatı
    sorulmaz ve satır oluşmaz (E10). Giriş hatasında (5d, 5g, 5h, 13a)
    fatura no ve satırlar yeniden sorulur. Mal kabul varsa servis faturayı
    hemen eşleştirir; sonuçta durum, toplam ve varsa bloke nedenleri
    gösterilir. Sipariş onaylı değilse, iptal edilmişse, aktif faturası
    varsa ya da mükerrerse (5b, 5c, 14a) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    siparis = belge_numarasi_sor(servis.siparis_bul, "Sipariş numarası: ")

    while True:
        tedarikci_fatura_no = input("Tedarikçinin fatura numarası: ")
        kalemler = []
        for siparis_kalemi in siparis.siparis_kalemleri:
            print(f"Kalem {siparis_kalemi.kalem_no} · "
                  f"{siparis_kalemi.malzeme_adi} (sipariş "
                  f"{siparis_kalemi.miktar} {siparis_kalemi.birim} × "
                  f"{siparis_kalemi.birim_fiyat})")
            miktar = tutar_sor("  Faturadaki miktar: ")
            if miktar == 0:
                continue
            kalem = {
                "siparis_kalem_no": siparis_kalemi.kalem_no,
                "miktar": miktar,
                "birim_fiyat": tutar_sor("  Faturadaki birim fiyat: "),
            }
            iskonto_turu = input("  İskonto türü (ORAN / TUTAR, yoksa boş): ")
            if iskonto_turu.strip():
                kalem["iskonto_turu"] = iskonto_turu.strip().upper()
                kalem["iskonto_degeri"] = tutar_sor("  İskonto değeri: ")
            kalemler.append(kalem)
        try:
            fatura = servis.fatura_kaydet(siparis.siparis_no,
                                          tedarikci_fatura_no, kalemler)
            break
        except GecersizGirisError as hata:
            print(hata)

    print(f"Fatura kaydedildi: {fatura.fatura_no} · {fatura.durum} "
          f"· toplam {fatura.genel_toplam()}")
    if fatura.bloke_neden_kodlari:
        print(f"Bloke nedeni: {', '.join(fatura.bloke_neden_kodlari)}")
    if fatura.durum == "ESLESME_BEKLIYOR":
        print("Mal kabul bekleniyor; mal gelince eşleştirilecek.")


# ---------------------------------------------------------------------------
# Kararlar
# ---------------------------------------------------------------------------

def menu_fatura_ayrintisi(servis):
    """Faturanın bloke ayrıntısını kalem kalem gösterir (E63).

    Fatura eşleşmemiş, reddedilmiş ya da iptal edilmişse (16b) ana menü
    yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    fatura = belge_numarasi_sor(servis.fatura_bul, "Fatura numarası: ")
    sonuc = servis.fatura_ayrintisini_hesapla(fatura.fatura_no)
    print(f"{fatura.fatura_no} · {fatura.durum}")
    bulgulari_yazdir(sonuc)


def menu_serbest_birak(servis):
    """BLOKE faturanın nedenini gösterip gerekçeyle serbest bıraktırır.

    Gerekçe hatasında (7c) gerekçe yeniden sorulur. Fatura BLOKE değilse
    (7b, 16b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    fatura = belge_numarasi_sor(servis.fatura_bul, "Fatura numarası: ")
    bulgulari_yazdir(servis.fatura_ayrintisini_hesapla(fatura.fatura_no))

    while True:
        gerekce, notu = gerekce_sor(KARAR_GEREKCELERI["SERBEST"])
        try:
            servis.serbest_birak(fatura.fatura_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            print(hata)

    print(f"Fatura serbest bırakıldı: {fatura.fatura_no}")


def menu_reddet(servis):
    """Faturayı gerekçeyle reddettirir; BLOKE ise önce nedenini gösterir.

    ESLESME_BEKLIYOR fatura da reddedilebilir (mal gelmediyse); onun
    ayrıntısı olmadığı için gösterilmez. Gerekçe hatasında (7c) gerekçe
    yeniden sorulur. Fatura başka durumdaysa (7b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    fatura = belge_numarasi_sor(servis.fatura_bul, "Fatura numarası: ")
    if fatura.durum == "BLOKE":
        bulgulari_yazdir(servis.fatura_ayrintisini_hesapla(fatura.fatura_no))

    while True:
        gerekce, notu = gerekce_sor(KARAR_GEREKCELERI["REDDEDILDI"])
        try:
            servis.reddet(fatura.fatura_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            print(hata)

    print(f"Fatura reddedildi: {fatura.fatura_no}")


def menu_karantina_karari(servis):
    """Karantinadaki mal için karar (v1a: İADE) kaydettirir.

    Önce karantinadakiler listelenir. Miktar ya da gerekçe hatasında (15c)
    karar yeniden sorulur. Mal kabul iptal edilmişse, kalem yoksa ya da
    karar bekleyen miktar kalmadıysa (15b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    menu_karantinadakiler(servis)
    if not servis.karantinadakileri_listele():
        return
    mal_kabul = belge_numarasi_sor(servis.mal_kabul_bul, "Mal kabul numarası: ")
    kalem_no = tam_sayi_sor("Kalem no: ")

    while True:
        kararlar = {}
        for karar_turu in KARANTINA_KARAR_GEREKCELERI:
            kararlar[karar_turu] = karar_turu
        karar = secenek_sor(kararlar, "Karar numarası: ")
        miktar = tutar_sor("Miktar: ")
        gerekce, notu = gerekce_sor(KARANTINA_KARAR_GEREKCELERI[karar])
        try:
            kayit = servis.karantina_karari_ver(mal_kabul.mal_kabul_no, kalem_no,
                                                karar, miktar, gerekce, notu)
            break
        except GecersizGirisError as hata:
            print(hata)

    print(f"Karar kaydedildi: {kayit.mal_kabul_no} kalem "
          f"{kayit.mal_kabul_kalem_no} · {kayit.karar} {kayit.miktar}")


# ---------------------------------------------------------------------------
# İptaller (zincir tersten: fatura → mal kabul → sipariş, R3)
# ---------------------------------------------------------------------------

def menu_fatura_iptal(servis):
    """Faturayı gerekçeyle iptal ettirir.

    Gerekçe hatasında (12a) gerekçe yeniden sorulur. Fatura zaten iptal
    edilmişse (9b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    fatura = belge_numarasi_sor(servis.fatura_bul, "Fatura numarası: ")
    while True:
        gerekce, notu = gerekce_sor(IPTAL_GEREKCELERI["FATURA"])
        try:
            servis.fatura_iptal_et(fatura.fatura_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            print(hata)
    print(f"Fatura iptal edildi: {fatura.fatura_no}")


def menu_mal_kabul_iptal(servis):
    """Mal kabulü gerekçeyle iptal ettirir.

    Gerekçe hatasında (12a) gerekçe yeniden sorulur. Zaten iptalse, dayanan
    aktif fatura ya da karantina kararı varsa (8b-8d) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    mal_kabul = belge_numarasi_sor(servis.mal_kabul_bul, "Mal kabul numarası: ")
    while True:
        gerekce, notu = gerekce_sor(IPTAL_GEREKCELERI["MAL_KABUL"])
        try:
            servis.mal_kabul_iptal_et(mal_kabul.mal_kabul_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            print(hata)
    print(f"Mal kabul iptal edildi: {mal_kabul.mal_kabul_no}")


def menu_siparis_iptal(servis):
    """Siparişi gerekçeyle iptal ettirir.

    Gerekçe hatasında (12a) gerekçe yeniden sorulur. Zaten iptalse ya da
    aktif mal kabulü veya faturası varsa (11b, 11c) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    siparis = belge_numarasi_sor(servis.siparis_bul, "Sipariş numarası: ")
    while True:
        gerekce, notu = gerekce_sor(IPTAL_GEREKCELERI["SIPARIS"])
        try:
            servis.siparis_iptal_et(siparis.siparis_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            print(hata)
    print(f"Sipariş iptal edildi: {siparis.siparis_no}")


# ---------------------------------------------------------------------------
# Bekleyen işler listeleri (ilke 10)
# ---------------------------------------------------------------------------

def menu_bekleyen_faturalar(servis):
    """Malı gelmemiş, eşleşme bekleyen faturaları listeler.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    faturalar = servis.bekleyen_faturalari_listele()
    if not faturalar:
        print("Eşleşme bekleyen fatura yok.")
        return
    for fatura in faturalar:
        print(f"{fatura.fatura_no} · {fatura.siparis_no} · tedarikçi no "
              f"{fatura.tedarikci_fatura_no} · toplam {fatura.genel_toplam()}")


def menu_bloke_faturalar(servis):
    """Serbest bırak / reddet kararı bekleyen faturaları listeler.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    faturalar = servis.bloke_faturalari_listele()
    if not faturalar:
        print("Bloke fatura yok.")
        return
    for fatura in faturalar:
        print(f"{fatura.fatura_no} · {fatura.siparis_no} · toplam "
              f"{fatura.genel_toplam()} · neden: "
              f"{', '.join(fatura.bloke_neden_kodlari)}")


def menu_karantinadakiler(servis):
    """Karar bekleyen karantinadaki malı nedene göre listeler (E118).

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    satirlar = servis.karantinadakileri_listele()
    if not satirlar:
        print("Karantinada bekleyen mal yok.")
        return
    for satir in satirlar:
        print(f"{satir.mal_kabul_no} kalem {satir.mal_kabul_kalem_no} "
              f"({satir.siparis_no}): {nedenli_metin(satir.kalanlar)} "
              f"· toplam {satir.kalan_miktar()}")


# ---------------------------------------------------------------------------
# Ana menü
# ---------------------------------------------------------------------------

MENU_SECENEKLERI = [
    ("1", "Tedarikçi ekle", menu_tedarikci_ekle),
    ("2", "Sipariş aç", menu_siparis_ac),
    ("3", "Sipariş onayla", menu_siparis_onayla),
    ("4", "Mal kabul", menu_mal_kabul),
    ("5", "Fatura", menu_fatura),
    ("6", "Fatura ayrıntısı / bloke nedeni", menu_fatura_ayrintisi),
    ("7", "Faturayı serbest bırak", menu_serbest_birak),
    ("8", "Faturayı reddet", menu_reddet),
    ("9", "Karantina kararı", menu_karantina_karari),
    ("10", "Bekleyen faturalar", menu_bekleyen_faturalar),
    ("11", "Bloke faturalar", menu_bloke_faturalar),
    ("12", "Karantinadakiler", menu_karantinadakiler),
    ("13", "Fatura iptal", menu_fatura_iptal),
    ("14", "Mal kabul iptal", menu_mal_kabul_iptal),
    ("15", "Sipariş iptal", menu_siparis_iptal),
]


def menuyu_baslat():
    """Programı açar ve ana menüyü "0" seçilene kadar döndürür.

    Açılışta veri dosyası okunamazsa (DepolamaError, 10a, 10c) mesaj verip
    durur. Menü fonksiyonlarının yakalamadığı bütün hatalar (ör. sipariş
    zaten onaylı) tek except SatinAlmaError ile yakalanır; mesaj gösterilir
    ve menüye dönülür (E99). Genel except Exception yok.
    """
    try:
        servis = SatinAlmaServisi(VERI_DOSYASI)
    except DepolamaError as hata:
        print(hata)
        return

    while True:
        print()
        for numara, baslik, _ in MENU_SECENEKLERI:
            print(f"{numara:>2} - {baslik}")
        print(" 0 - Çıkış")
        secim = input("Seçiminiz: ").strip()

        if secim == "0":
            print("Çıkış yapılıyor...")
            return

        secilen = None
        for numara, _, menu_fonksiyonu in MENU_SECENEKLERI:
            if numara == secim:
                secilen = menu_fonksiyonu
        if secilen is None:
            print("Geçersiz seçim.")
            continue

        try:
            secilen(servis)
        except SatinAlmaError as hata:
            print(hata)


if __name__ == "__main__":
    menuyu_baslat()