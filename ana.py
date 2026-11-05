from para import tutara_cevir
from hatalar import GecersizGirisError, KayitBulunamadiError, DepolamaError, SatinAlmaError
from servis import SatinAlmaServisi
from ayarlar import VERI_DOSYASI


def tutar_sor(soru):
    """Kullanıcıdan tutar alır; geçerli sayı yazılana kadar tekrar sorar.

    Metni tutara_cevir çevirir (virgül kabul edilir). Çevrilemezse hata
    mesajı gösterilir ve aynı soru yeniden sorulur. Eksi ya da sıfır
    kontrolü burada yapılmaz; o servisin işidir.

    Args:
        soru: Ekrana yazılacak soru, ör. "Miktar: ".

    Returns:
        Girilen tutar (Decimal).
    """
    while True:
        try:
            gelen_soru = input(soru)
            cevirme = tutara_cevir(gelen_soru)
            return cevirme
        except GecersizGirisError as hata:
            print(hata)


def menu_tedarikci_ekle(servis):
    """Yeni tedarikçiyi kullanıcıdan alıp kaydettirir ve kodunu gösterir.

    Firma adı isteğe bağlıdır; boş bırakılırsa None gönderilir. Tedarikçi
    kodu sorulmaz, servis üretir. Ad boşsa servis GecersizGirisError
    fırlatır; mesaj gösterilir ve bilgiler yeniden sorulur.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    while True:
        try:
            tedarikci_adi = input("Tedarikçi adı: ")
            firma_adi = input("Firma adı (boş bırakılabilir): ")
            if firma_adi == "":
                firma_adi = None
            tedarikci = servis.tedarikci_ekle(tedarikci_adi=tedarikci_adi,
                                              firma_adi=firma_adi)
            print(f"Tedarikçi eklendi: {tedarikci.tedarikci_kodu}")
            return
        except GecersizGirisError as hata:
            print(hata)


def menu_siparis_ac(servis):
    """Kullanıcıdan tedarikçi ve kalemleri alıp yeni sipariş açtırır.

    Tedarikçiler listelenir, kod sorulur; kalemler malzeme adı boş
    bırakılana kadar tek tek sorulur. Servis hata verirse (tedarikçi
    yok, kalem yok, kategori geçersiz) mesaj gösterilir ve giriş baştan
    başlar. Kalem no, tolerans ve tarih servisten gelir.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    while True:
        for tedarikci in servis.tedarikciler.values():
            ted_kod = tedarikci.tedarikci_kodu
            ted_adi = tedarikci.tedarikci_adi
            print(f"{ted_kod} - {ted_adi}")
        ted_kodu_sor = input("Tedarikçi kodu: ")

        kalemler = []
        while True:
            malzeme_adi = input("Malzeme adı (bitirmek için boş Enter): ")
            if not malzeme_adi:
                break
            miktar = tutar_sor("Miktar: ")
            birim = input("Birim: ")
            birim_fiyat = tutar_sor("Birim fiyat: ")
            kategori = input("Kategori (SARF / STRATEJIK): ")
            soru_sozlugu = {"malzeme_adi": malzeme_adi, "miktar": miktar,
                            "birim": birim, "birim_fiyat": birim_fiyat,
                            "kategori": kategori}
            kalemler.append(soru_sozlugu)

        try:
            siparis = servis.siparis_ac(ted_kodu_sor, kalemler)
            print(f"Sipariş açıldı: {siparis.siparis_no} · {siparis.durum} "
                  f"· toplam {siparis.genel_toplam()}")
            return
        except KayitBulunamadiError as hata:
            print(hata)
        except GecersizGirisError as hata:
            print(hata)


def menu_siparis_onayla(servis):
    """Sipariş numarasını alıp siparişi onaylatır.

    Numara bulunamazsa mesaj gösterilir ve numara tekrar sorulur.
    Sipariş zaten onaylıysa servisin hatası (IslemYapilamazError)
    burada yakalanmaz; ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    while True:
        try:
            numara_al = input("Sipariş numarası: ")
            servis.siparis_onayla(numara_al)
            print(f"Sipariş onaylandı: {numara_al}")
            return
        except KayitBulunamadiError as hata:
            print(hata)


def menu_mal_kabul(servis):
    """Siparişin satırlarını gösterip gelen miktarları alır, mal kabul kaydettirir.

    Sipariş numarası bulunamazsa tekrar sorulur. Satırlar siparişten
    sırayla gelir (kalem no sistemden, E3). Hiç miktar girilmezse satırlar
    yeniden sorulur. Sonuçta her satırın kabul / karantina / kapıda red
    miktarı ve belirleyici sınır gösterilir (E75). Sipariş onaylı değilse
    servisin hatası burada yakalanmaz; ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    while True:
        siparis_no = input("Sipariş numarası: ")
        try:
            siparis = servis.siparis_bul(siparis_no)
            break
        except KayitBulunamadiError as hata:
            print(hata)

    while True:
        kalemler = []
        for siparis_kalemi in siparis.siparis_kalemleri:
            gelen_miktar = tutar_sor(
                f"Kalem {siparis_kalemi.kalem_no} · {siparis_kalemi.malzeme_adi} "
                f"(sipariş {siparis_kalemi.miktar} {siparis_kalemi.birim}) "
                f"gelen miktar: ")
            kalemler.append({"siparis_kalem_no": siparis_kalemi.kalem_no,
                             "gelen_miktar": gelen_miktar})
        try:
            sonuc = servis.mal_kabul_kaydet(siparis_no, kalemler)
            break
        except GecersizGirisError as hata:
            print(hata)

    print(f"Mal kabul kaydedildi: {sonuc.mal_kabul.mal_kabul_no}")
    for kalem_no, kova in sonuc.kova_sonuclari.items():
        satir = (f"Kalem {kalem_no}: kabul {kova.kabul} · karantina "
                 f"{kova.karantina} · kapıda red {kova.kapida_red}")
        if kova.belirleyici_sinir is not None:
            satir += f" · sınır: {kova.belirleyici_sinir}"
        print(satir)


def menu_fatura(servis):
    """Siparişin satırlarını gösterip faturadaki miktar ve fiyatları alır, fatura kaydettirir.

    Sipariş numarası bulunamazsa tekrar sorulur. Satırlar siparişten
    sırayla gelir (E3); miktarı 0 girilen satırın fiyatı sorulmaz ve satır
    oluşmaz (E10). Hiç satır kalmazsa satırlar yeniden sorulur. Mal kabul
    varsa servis faturayı hemen eşleştirir; sonuçta durum, toplam ve varsa
    bloke nedenleri gösterilir. Sipariş onaylı değilse servisin hatası
    burada yakalanmaz; ana menü yakalar.

    Args:
        servis: Açık SatinAlmaServisi nesnesi.
    """
    while True:
        siparis_no = input("Sipariş numarası: ")
        try:
            siparis = servis.siparis_bul(siparis_no)
            break
        except KayitBulunamadiError as hata:
            print(hata)

    tedarikci_fatura_no = input("Tedarikçinin fatura numarası: ")

    while True:
        kalemler = []
        for siparis_kalemi in siparis.siparis_kalemleri:
            print(f"Kalem {siparis_kalemi.kalem_no} · "
                  f"{siparis_kalemi.malzeme_adi} (sipariş "
                  f"{siparis_kalemi.miktar} {siparis_kalemi.birim} × "
                  f"{siparis_kalemi.birim_fiyat})")
            miktar = tutar_sor("  Faturadaki miktar: ")
            if miktar == 0:
                continue
            birim_fiyat = tutar_sor("  Faturadaki birim fiyat: ")
            kalemler.append({"siparis_kalem_no": siparis_kalemi.kalem_no,
                             "miktar": miktar,
                             "birim_fiyat": birim_fiyat})
        try:
            fatura = servis.fatura_kaydet(siparis_no, tedarikci_fatura_no,
                                          kalemler)
            break
        except GecersizGirisError as hata:
            print(hata)

    print(f"Fatura kaydedildi: {fatura.fatura_no} · {fatura.durum} "
          f"· toplam {fatura.genel_toplam()}")
    if fatura.bloke_neden_kodlari:
        print(f"Bloke nedeni: {', '.join(fatura.bloke_neden_kodlari)}")
    if fatura.durum == "ESLESME_BEKLIYOR":
        print("Mal kabul bekleniyor; mal gelince eşleştirilecek.")


def menuyu_baslat():
    """Programı açar ve ana menüyü "0" seçilene kadar döndürür.

    Açılışta veri dosyası okunamazsa (DepolamaError) mesaj verip durur.
    Menü fonksiyonlarının yakalamadığı bütün hatalar (ör. sipariş zaten
    onaylı) tek except SatinAlmaError ile yakalanır; mesaj gösterilir ve
    menüye dönülür (E99).
    """
    try:
        servis = SatinAlmaServisi(VERI_DOSYASI)
    except DepolamaError as hata:
        print(hata)
        return
    while True:
        menu_secenekleri = input(
            "1-Tedarikçi ekle\n"
            "2-Sipariş aç\n"
            "3-Sipariş onayla\n"
            "4-Mal kabul\n"
            "5-Fatura\n"
            "0-Çıkış\n"
            "Seçiminiz: "
        ).strip()
        try:
            if menu_secenekleri == "1":
                menu_tedarikci_ekle(servis=servis)
            elif menu_secenekleri == "2":
                menu_siparis_ac(servis=servis)
            elif menu_secenekleri == "3":
                menu_siparis_onayla(servis=servis)
            elif menu_secenekleri == "4":
                menu_mal_kabul(servis=servis)
            elif menu_secenekleri == "5":
                menu_fatura(servis=servis)
            elif menu_secenekleri == "0":
                print("Çıkış yapılıyor...")
                return
            else:
                print("Geçersiz seçim.")
        except SatinAlmaError as hata:
            print(hata)


if __name__ == "__main__":
    menuyu_baslat()    