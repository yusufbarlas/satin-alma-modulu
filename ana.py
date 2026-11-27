"""Satın Alma Modülü'nün terminal menüsü: kullanıcıyla konuşan tek modül.

Menü hiçbir iş kuralı kontrol etmez (E62): metni para.py çevirir,
kuralları servis kontrol eder. Menü sadece soruyu sorar, hatayı yakalar ve
hata sınıfına göre davranır (hatalar tabındaki "Menü ne yapar" sütunu):
GecersizGirisError ve KayitBulunamadiError gelince alan tekrar sorulur;
IslemYapilamazError ana menüde yakalanır, mesaj gösterilip menüye dönülür.
Hata mesajları "Hata: " ile başlar (E132). Numara sorulan her ekranda boş
Enter ile vazgeçilir: Vazgecildi ana menüde yakalanır, hiçbir şey
kaydedilmez. Menü servisin iç verisine dokunmaz; okumak için genel
metotları çağırır (E100, E112).
"""

from ayarlar import (
    IPTAL_GEREKCELERI,
    KARANTINA_KARAR_GEREKCELERI,
    KARAR_GEREKCELERI,
    ODEME_YONTEMLERI,
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


class Vazgecildi(Exception):
    """Kullanıcı numara sorusunu boş geçti: ana menüye dönülür.

    İş hatası değil, kullanıcının kararıdır; bu yüzden SatinAlmaError
    ailesinden değil Exception'dan türer ve sadece menüde yaşar (E132).
    Fırlatan: belge_numarasi_sor, tedarikci_sec. Yakalayan: menuyu_baslat.
    """


def hata_yaz(hata):
    """Hata mesajını başına "Hata: " koyarak yazar (E132).

    Başarı satırlarından ayırt edilsin diye bütün hata mesajları buradan
    geçer.

    Args:
        hata: Yakalanan hata ya da mesaj metni.
    """
    print(f"Hata: {hata}")


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
            hata_yaz(hata)


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
            hata_yaz(f"'{metin}' geçersiz; bir sayı yazın.")


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
        hata_yaz(f"Geçersiz numara; 1 ile {len(kodlar)} arasında olmalı.")


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

    Numara büyük harfe çevrilir ("ftr-0001" de bulunur). Boş Enter
    vazgeçmektir: Vazgecildi fırlatılır, ana menü yakalar (E132).

    Args:
        bul: Servisin okuma metodu, ör. servis.fatura_bul.
        soru: Ekrana yazılacak soru, ör. "Fatura numarası: ".

    Returns:
        Bulunan belge nesnesi.

    Raises:
        Vazgecildi: Numara boş bırakıldıysa.
    """
    while True:
        numara = input(soru).strip().upper()
        if not numara:
            raise Vazgecildi
        try:
            return bul(numara)
        except KayitBulunamadiError as hata:
            hata_yaz(f"{hata} (vazgeçmek için boş Enter)")


def bos_olabilir_belge_sor(bul, soru):
    """Belge numarasını sorar; boş Enter ile "yok" denebilir (v1b).

    Talepten sipariş / teklif açarken talep bağı isteğe bağlıdır. Numara
    yazılırsa büyük harfe çevrilir ve kayıt bulunana kadar tekrar sorulur
    (18a).

    Args:
        bul: Servisin okuma metodu, ör. servis.talep_bul.
        soru: Ekrana yazılacak soru.

    Returns:
        Bulunan belge nesnesi; boş girişte None.
    """
    while True:
        numara = input(soru).strip().upper()
        if not numara:
            return None
        try:
            return bul(numara)
        except KayitBulunamadiError as hata:
            hata_yaz(hata)


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
# Tedarikçi, sipariş, mal kabul, fatura
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
            hata_yaz(hata)


def tedarikci_sec(servis):
    """Tedarikçileri listeler, kodu sorar; "Y" ile yeni tedarikçi ekletir (E65).

    Kod büyük harfe çevrilir. Kodun kayıtlı olup olmadığını servis kontrol
    eder (2a). Boş Enter vazgeçmektir (E132).

    Args:
        servis: Açık SatinAlmaServisi nesnesi.

    Returns:
        Seçilen ya da yeni eklenen tedarikçinin kodu.

    Raises:
        Vazgecildi: Kod boş bırakıldıysa.
    """
    for tedarikci in servis.tedarikcileri_listele():
        print(f"  {tedarikci.tedarikci_kodu} - {tedarikci.tedarikci_adi}")
    secim = input("Tedarikçi kodu (yeni tedarikçi için Y, "
                  "vazgeçmek için boş Enter): ").strip().upper()
    if not secim:
        raise Vazgecildi
    if secim == "Y":
        return menu_tedarikci_ekle(servis).tedarikci_kodu
    return secim


def siparis_kalemlerini_sor(tavan_sor=True):
    """Talepsiz kalemleri malzeme adı boş bırakılana kadar sorar.

    İskonto ve miktar tavanı isteğe bağlıdır; boş bırakılan alan sözlüğe
    konmaz, servis varsayılanı kullanır. Teklifte de kullanılır; teklif
    kaleminde miktar tavanı olmadığı için orada sorulmaz.

    Args:
        tavan_sor: False ise miktar tavanı sorulmaz (teklif).

    Returns:
        Kalem sözlüklerinin listesi (siparis_ac / teklif_kaydet biçimi).
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
        if tavan_sor:
            miktar_tavani = tutar_sor("  Miktar tavanı (yoksa boş): ",
                                      bos_olabilir=True)
            if miktar_tavani is not None:
                kalem["miktar_tavani"] = miktar_tavani
        kalemler.append(kalem)


def talepten_kalemleri_sor(talep):
    """Talebin satırlarını gösterip her biri için miktar ve fiyat sorar (v1b).

    Malzeme adı, birim ve kategori sorulmaz: servis talepten kopyalar (B6).
    Miktarı 0 girilen satır alınmaz. Sipariş ve teklif ekranı kullanır.

    Args:
        talep: Bağlanacak Talep.

    Returns:
        Bağlı kalem sözlüklerinin listesi (talep_no, talep_kalem_no,
        miktar, birim_fiyat; isteğe bağlı iskonto).
    """
    kalemler = []
    for talep_kalemi in talep.talep_kalemleri:
        tahmin = ""
        if talep_kalemi.tahmini_birim_fiyat is not None:
            tahmin = f", tahmini {talep_kalemi.tahmini_birim_fiyat}"
        print(f"Talep kalemi {talep_kalemi.kalem_no} · "
              f"{talep_kalemi.malzeme_adi} ({talep_kalemi.miktar} "
              f"{talep_kalemi.birim}{tahmin})")
        miktar = tutar_sor("  Miktar (almamak için 0): ")
        if miktar == 0:
            continue
        kalem = {
            "talep_no": talep.talep_no,
            "talep_kalem_no": talep_kalemi.kalem_no,
            "miktar": miktar,
            "birim_fiyat": tutar_sor("  Birim fiyat: "),
        }
        iskonto_turu = input("  İskonto türü (ORAN / TUTAR, yoksa boş): ")
        if iskonto_turu.strip():
            kalem["iskonto_turu"] = iskonto_turu.strip().upper()
            kalem["iskonto_degeri"] = tutar_sor("  İskonto değeri: ")
        kalemler.append(kalem)
    return kalemler


def kalemleri_sor(servis, tavan_sor=True):
    """Önce isteğe bağlı talep bağını, sonra talepsiz ek kalemleri sorar (v1b).

    Talep numarası boş bırakılırsa bütün kalemler talepsizdir (v1a gibi).
    Talep yazılırsa onun satırları sorulur; ardından talepte olmayan ek
    kalem eklenebilir.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
        tavan_sor: siparis_kalemlerini_sor'a geçer (teklifte False).

    Returns:
        Kalem sözlüklerinin listesi.
    """
    talep = bos_olabilir_belge_sor(
        servis.talep_bul, "Talep numarası (talepsiz için boş Enter): ")
    kalemler = []
    if talep is not None:
        kalemler = talepten_kalemleri_sor(talep)
        print("Talepte olmayan ek kalem varsa girin.")
    kalemler += siparis_kalemlerini_sor(tavan_sor=tavan_sor)
    return kalemler


def menu_siparis_ac(servis):
    """Tedarikçi ve kalemleri alıp yeni sipariş açtırır.

    Kalemler bir talebe bağlanabilir (v1b, E120): talep numarası verilirse
    onun satırları sorulur. Tedarikçi bulunamazsa (2a) sadece tedarikçi,
    kalem ya da bağ giriş hatasında (2b-2g, 13a, 20f, 20h, 20i) sadece
    kalemler yeniden sorulur. Talep onaysızsa, kalemi başka siparişteyse ya
    da miktar talebi aşıyorsa (20d, 20c, 20g) ana menü yakalar. Kalem no,
    tolerans ve tarih servisten gelir.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    tedarikci_kodu = tedarikci_sec(servis)
    kalemler = kalemleri_sor(servis)
    while True:
        try:
            siparis = servis.siparis_ac(tedarikci_kodu, kalemler)
            print(f"Sipariş açıldı: {siparis.siparis_no} · {siparis.durum} "
                  f"· toplam {siparis.genel_toplam()}")
            return
        except KayitBulunamadiError as hata:
            hata_yaz(hata)
            tedarikci_kodu = tedarikci_sec(servis)
        except GecersizGirisError as hata:
            hata_yaz(hata)
            print("Kalemleri yeniden girin.")
            kalemler = kalemleri_sor(servis)


def menu_tekliften_siparis_ac(servis):
    """Teklif numarasını alıp tekliften sipariş açtırır (v1b, E122).

    Kalemler, tedarikçi ve fiyatlar tekliften gelir; hiçbir şey sorulmaz.
    Teklif açık değilse ya da siparişe dönüşmüşse (20b), talep kalemi başka
    siparişteyse (20c) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    teklif = belge_numarasi_sor(servis.teklif_bul, "Teklif numarası: ")
    siparis = servis.tekliften_siparis_ac(teklif.teklif_no)
    print(f"Sipariş açıldı: {siparis.siparis_no} · {siparis.durum} "
          f"· toplam {siparis.genel_toplam()} · teklif {teklif.teklif_no}")


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
            hata_yaz(hata)

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
            hata_yaz(hata)

    print(f"Fatura kaydedildi: {fatura.fatura_no} · {fatura.durum} "
          f"· toplam {fatura.genel_toplam()}")
    if fatura.bloke_neden_kodlari:
        print(f"Bloke nedeni: {', '.join(fatura.bloke_neden_kodlari)}")
    if fatura.durum == "ESLESME_BEKLIYOR":
        print("Mal kabul bekleniyor; mal gelince eşleştirilecek.")


# ---------------------------------------------------------------------------
# Talep ve teklif (v1b)
# ---------------------------------------------------------------------------

def talep_kalemlerini_sor():
    """Talep kalemlerini malzeme adı boş bırakılana kadar sorar (v1b).

    Fiyat zorunlu değildir: tahmini birim fiyat boş bırakılabilir (E121).

    Returns:
        Kalem sözlüklerinin listesi (talep_ac'ın beklediği biçim).
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
            "kategori": input("  Kategori (SARF / STRATEJIK): ").strip().upper(),
        }
        tahmini = tutar_sor("  Tahmini birim fiyat (yoksa boş): ",
                            bos_olabilir=True)
        if tahmini is not None:
            kalem["tahmini_birim_fiyat"] = tahmini
        kalemler.append(kalem)


def menu_talep_ac(servis):
    """Talep edeni ve kalemleri alıp satın alma talebi açtırır (E121).

    Giriş hatasında (17a, 2b-2g) talep eden ve kalemler yeniden sorulur.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    while True:
        talep_eden = input("Talep eden (kişi ya da birim): ")
        kalemler = talep_kalemlerini_sor()
        try:
            talep = servis.talep_ac(talep_eden, kalemler)
            break
        except GecersizGirisError as hata:
            hata_yaz(hata)
    print(f"Talep açıldı: {talep.talep_no} · {talep.durum} · "
          f"{len(talep.talep_kalemleri)} kalem")


def menu_talep_onayla(servis):
    """Talep numarasını alıp talebi onaylatır (gerekçe sorulmaz, T2).

    Talep TASLAK değilse ya da iptal edilmişse (18b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    talep = belge_numarasi_sor(servis.talep_bul, "Talep numarası: ")
    servis.talep_onayla(talep.talep_no)
    print(f"Talep onaylandı: {talep.talep_no}")


def menu_talep_reddet(servis):
    """Talebi gerekçeyle reddettirir.

    Gerekçe hatasında (7c) gerekçe yeniden sorulur. Talep TASLAK değilse
    ya da iptal edilmişse (18b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    talep = belge_numarasi_sor(servis.talep_bul, "Talep numarası: ")
    while True:
        gerekce, notu = gerekce_sor(KARAR_GEREKCELERI["TALEP_RED"])
        try:
            servis.talep_reddet(talep.talep_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            hata_yaz(hata)
    print(f"Talep reddedildi: {talep.talep_no}")


def menu_teklif_kaydet(servis):
    """Tedarikçinin teklifini alıp kaydettirir (E122).

    Kalemler bir talebe bağlanabilir; talep numarası verilirse onun
    satırları sorulur. Tedarikçi ya da bağlı talep bulunamazsa (19a)
    tedarikçi ve kalemler, giriş hatasında (2b-2g, 13a, 19d, 19e, 19f)
    kalemler yeniden sorulur. Talep onaysızsa ya da kalem talepte yoksa
    (19b, 19c) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    tedarikci_kodu = tedarikci_sec(servis)
    tedarikci_teklif_no = input("Tedarikçinin teklif numarası (boş bırakılabilir): ")
    if not tedarikci_teklif_no.strip():
        tedarikci_teklif_no = None
    kalemler = kalemleri_sor(servis, tavan_sor=False)
    while True:
        try:
            teklif = servis.teklif_kaydet(tedarikci_kodu, kalemler,
                                          tedarikci_teklif_no=tedarikci_teklif_no)
            break
        except KayitBulunamadiError as hata:
            hata_yaz(hata)
            tedarikci_kodu = tedarikci_sec(servis)
            kalemler = kalemleri_sor(servis, tavan_sor=False)
        except GecersizGirisError as hata:
            hata_yaz(hata)
            print("Kalemleri yeniden girin.")
            kalemler = kalemleri_sor(servis, tavan_sor=False)
    print(f"Teklif kaydedildi: {teklif.teklif_no} · {teklif.durum} "
          f"· toplam {teklif.genel_toplam()}")


def menu_teklif_reddet(servis):
    """Teklifi gerekçeyle reddettirir.

    Gerekçe hatasında (7c) gerekçe yeniden sorulur. Teklif açık değilse ya
    da siparişe dönüşmüşse (21b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    teklif = belge_numarasi_sor(servis.teklif_bul, "Teklif numarası: ")
    while True:
        gerekce, notu = gerekce_sor(KARAR_GEREKCELERI["TEKLIF_RED"])
        try:
            servis.teklif_reddet(teklif.teklif_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            hata_yaz(hata)
    print(f"Teklif reddedildi: {teklif.teklif_no}")


# ---------------------------------------------------------------------------
# Ödeme (v1b)
# ---------------------------------------------------------------------------

def odeme_bekleyenleri_yazdir(servis, tedarikci_kodu=None):
    """Ödeme bekleyen faturaları kalan borçlarıyla yazar (O6).

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
        tedarikci_kodu: Verilirse sadece o tedarikçinin faturaları.

    Returns:
        Yazılan fatura sayısı.
    """
    sayi = 0
    for fatura in servis.odeme_bekleyen_faturalari_listele():
        siparis = servis.siparis_bul(fatura.siparis_no)
        if tedarikci_kodu is not None and siparis.tedarikci_kodu != tedarikci_kodu:
            continue
        print(f"  {fatura.fatura_no} · {siparis.tedarikci_kodu} · toplam "
              f"{fatura.genel_toplam()} · kalan "
              f"{servis.fatura_kalan_borc(fatura.fatura_no)}")
        sayi += 1
    return sayi


def odeme_kalemlerini_sor(servis):
    """Ödenecek faturaları fatura numarası boş bırakılana kadar sorar.

    Numara büyük harfe çevrilir ve yazıldığı an kontrol edilir: kayıtlı
    değilse hata gösterilip aynı soru yeniden sorulur, tutar sorulmaz
    (E132). Faturanın ödenebilir olup olmadığını ve tedarikçisini servis
    kontrol eder (23c, 23d).

    Args:
        servis: Açık SatinAlmaServisi nesnesi.

    Returns:
        Kalem sözlüklerinin listesi (fatura_no, tutar).
    """
    kalemler = []
    while True:
        fatura_no = input(
            "Fatura numarası (bitirmek için boş Enter): ").strip().upper()
        if not fatura_no:
            return kalemler
        try:
            servis.fatura_bul(fatura_no)
        except KayitBulunamadiError as hata:
            hata_yaz(hata)
            continue
        kalemler.append({
            "fatura_no": fatura_no,
            "tutar": tutar_sor("  Ödenen tutar: "),
        })


def menu_odeme_kaydet(servis):
    """Tedarikçiye yapılan ödemeyi kaydettirir (E123).

    Önce o tedarikçinin ödeme bekleyen faturaları kalan borçlarıyla
    listelenir; tek ödeme birden çok faturayı kapatabilir (O2). Tedarikçi
    ya da fatura bulunamazsa (23a) tedarikçi ve kalemler, giriş hatasında
    (23b, 23e) yöntem ve kalemler yeniden sorulur. Fatura ödenemez durumdaysa
    ya da başka tedarikçininse (23c, 23d) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    tedarikci_kodu = tedarikci_sec(servis)
    while True:
        if odeme_bekleyenleri_yazdir(servis, tedarikci_kodu) == 0:
            print("Bu tedarikçinin ödeme bekleyen faturası yok.")
            return
        kalemler = odeme_kalemlerini_sor(servis)
        yontemler = {}
        for yontem in ODEME_YONTEMLERI:
            yontemler[yontem] = yontem
        odeme_yontemi = secenek_sor(yontemler, "Ödeme yöntemi numarası: ")
        odeme_notu = input("Not (boş bırakılabilir): ")
        if not odeme_notu.strip():
            odeme_notu = None
        try:
            odeme = servis.odeme_kaydet(tedarikci_kodu, kalemler, odeme_yontemi,
                                        odeme_notu=odeme_notu)
            break
        except KayitBulunamadiError as hata:
            hata_yaz(hata)
            tedarikci_kodu = tedarikci_sec(servis)
        except GecersizGirisError as hata:
            hata_yaz(hata)
    print(f"Ödeme kaydedildi: {odeme.odeme_no} · {odeme.odeme_yontemi} "
          f"· toplam {odeme.toplam()}")
    for kalem in odeme.odeme_kalemleri:
        print(f"  {kalem.fatura_no}: ödenen {kalem.tutar} · kalan "
              f"{servis.fatura_kalan_borc(kalem.fatura_no)}")


def menu_odeme_bekleyen_faturalar(servis):
    """Kalan borcu olan ödenebilir faturaları listeler (ilke 10, O6).

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    if odeme_bekleyenleri_yazdir(servis) == 0:
        print("Ödeme bekleyen fatura yok.")


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
            hata_yaz(hata)

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
            hata_yaz(hata)

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
            hata_yaz(hata)

    print(f"Karar kaydedildi: {kayit.mal_kabul_no} kalem "
          f"{kayit.mal_kabul_kalem_no} · {kayit.karar} {kayit.miktar}")


# ---------------------------------------------------------------------------
# İptaller (zincir tersten: ödeme → fatura → mal kabul → sipariş → teklif
# → talep, R3)
# ---------------------------------------------------------------------------

def menu_odeme_iptal(servis):
    """Ödemeyi gerekçeyle iptal ettirir (ters kayıt, v1b).

    Gerekçe hatasında (12a) gerekçe yeniden sorulur. Ödeme zaten iptal
    edilmişse (24b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    odeme = belge_numarasi_sor(servis.odeme_bul, "Ödeme numarası: ")
    while True:
        gerekce, notu = gerekce_sor(IPTAL_GEREKCELERI["ODEME"])
        try:
            servis.odeme_iptal_et(odeme.odeme_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            hata_yaz(hata)
    print(f"Ödeme iptal edildi: {odeme.odeme_no}")


def menu_fatura_iptal(servis):
    """Faturayı gerekçeyle iptal ettirir.

    Gerekçe hatasında (12a) gerekçe yeniden sorulur. Fatura zaten iptal
    edilmişse ya da aktif ödemesi varsa (9b, 9c) ana menü yakalar.

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
            hata_yaz(hata)
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
            hata_yaz(hata)
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
            hata_yaz(hata)
    print(f"Sipariş iptal edildi: {siparis.siparis_no}")


def menu_teklif_iptal(servis):
    """Teklifi gerekçeyle iptal ettirir (v1b).

    Gerekçe hatasında (12a) gerekçe yeniden sorulur. Zaten iptalse ya da
    bağlı aktif siparişi varsa (22c, 22b) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    teklif = belge_numarasi_sor(servis.teklif_bul, "Teklif numarası: ")
    while True:
        gerekce, notu = gerekce_sor(IPTAL_GEREKCELERI["TEKLIF"])
        try:
            servis.teklif_iptal_et(teklif.teklif_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            hata_yaz(hata)
    print(f"Teklif iptal edildi: {teklif.teklif_no}")


def menu_talep_iptal(servis):
    """Talebi gerekçeyle iptal ettirir (v1b).

    Gerekçe hatasında (12a) gerekçe yeniden sorulur. Zaten iptalse ya da
    bağlı aktif teklifi veya siparişi varsa (22c, 22a) ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    talep = belge_numarasi_sor(servis.talep_bul, "Talep numarası: ")
    while True:
        gerekce, notu = gerekce_sor(IPTAL_GEREKCELERI["TALEP"])
        try:
            servis.talep_iptal_et(talep.talep_no, gerekce, notu)
            break
        except GecersizGirisError as hata:
            hata_yaz(hata)
    print(f"Talep iptal edildi: {talep.talep_no}")


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
    (None, "Talep ve teklif", None),
    ("1", "Talep aç", menu_talep_ac),
    ("2", "Talep onayla", menu_talep_onayla),
    ("3", "Talep reddet", menu_talep_reddet),
    ("4", "Teklif kaydet", menu_teklif_kaydet),
    ("5", "Teklif reddet", menu_teklif_reddet),
    (None, "Sipariş", None),
    ("6", "Tedarikçi ekle", menu_tedarikci_ekle),
    ("7", "Sipariş aç (talepten ya da talepsiz)", menu_siparis_ac),
    ("8", "Tekliften sipariş aç", menu_tekliften_siparis_ac),
    ("9", "Sipariş onayla", menu_siparis_onayla),
    (None, "Mal kabul ve fatura", None),
    ("10", "Mal kabul", menu_mal_kabul),
    ("11", "Fatura", menu_fatura),
    ("12", "Fatura ayrıntısı / bloke nedeni", menu_fatura_ayrintisi),
    ("13", "Faturayı serbest bırak", menu_serbest_birak),
    ("14", "Faturayı reddet", menu_reddet),
    ("15", "Karantina kararı", menu_karantina_karari),
    (None, "Ödeme", None),
    ("16", "Ödeme kaydet", menu_odeme_kaydet),
    (None, "Bekleyen işler", None),
    ("17", "Bekleyen faturalar (mal bekleyen)", menu_bekleyen_faturalar),
    ("18", "Bloke faturalar", menu_bloke_faturalar),
    ("19", "Karantinadakiler", menu_karantinadakiler),
    ("20", "Ödeme bekleyen faturalar", menu_odeme_bekleyen_faturalar),
    (None, "İptaller (zincir tersten)", None),
    ("21", "Ödeme iptal", menu_odeme_iptal),
    ("22", "Fatura iptal", menu_fatura_iptal),
    ("23", "Mal kabul iptal", menu_mal_kabul_iptal),
    ("24", "Sipariş iptal", menu_siparis_iptal),
    ("25", "Teklif iptal", menu_teklif_iptal),
    ("26", "Talep iptal", menu_talep_iptal),
]


def menuyu_baslat():
    """Programı açar ve ana menüyü "0" seçilene kadar döndürür.

    Açılışta veri dosyası okunamazsa (DepolamaError, 10a, 10c) mesaj verip
    durur. Menü fonksiyonlarının yakalamadığı bütün hatalar (ör. sipariş
    zaten onaylı) tek except SatinAlmaError ile yakalanır; mesaj gösterilir
    ve menüye dönülür (E99). Kullanıcı bir numara sorusunu boş geçerse
    Vazgecildi burada yakalanır ve menüye dönülür (E132). Genel except
    Exception yok. Seçenekler akış sırasıyla gruplanır (talep → ödeme →
    listeler → iptaller); numarası None olan satır grup başlığıdır,
    seçilemez.
    """
    try:
        servis = SatinAlmaServisi(VERI_DOSYASI)
    except DepolamaError as hata:
        hata_yaz(hata)
        return

    while True:
        print()
        for numara, baslik, _ in MENU_SECENEKLERI:
            if numara is None:
                print(f"— {baslik} —")
            else:
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
            hata_yaz("Geçersiz seçim.")
            continue

        try:
            secilen(servis)
        except SatinAlmaError as hata:
            hata_yaz(hata)
        except Vazgecildi:
            print("Ana menüye dönülüyor.")


if __name__ == "__main__":
    menuyu_baslat()