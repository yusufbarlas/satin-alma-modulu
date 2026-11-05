from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ayarlar import KALEM_NO_ARTISI, KUCUK_FARK_ESIGI, ONEKLER, TOLERANSLAR
from depolama import kaydet, yukle
from eslestirme import KovaSonucu, kovalara_ayir, kurallari_uygula
from hatalar import GecersizGirisError, IslemYapilamazError, KayitBulunamadiError
from modeller import (MalKabul, MalKabulKalemi, Siparis, SiparisKalemi,
                      Tedarikci, ToleransKopyasi,FaturaKalemi,Fatura,MalKabulDagitimi)
from para import net_fiyat_hesapla                                               



@dataclass
class MalKabulSonucu:
    """mal_kabul_kaydet'in sonucu; saklanmaz.

    Attributes:
        mal_kabul: Kaydedilen MalKabul.
        kova_sonuclari: {sipariş kalem no: KovaSonucu}; menü belirleyici
            sınırı buradan gösterir.
        eslesen_faturalar: Mal kabulden sonra eşleşen bekleyen faturaların
            numaraları; R2 kodlanana kadar boş.
    """

    mal_kabul: MalKabul
    kova_sonuclari: dict[int, KovaSonucu]
    eslesen_faturalar: list[str] = field(default_factory=list)




class SatinAlmaServisi:

    def __init__(self, dosya_yolu):
        self.dosya_yolu = dosya_yolu
        cevir = yukle(dosya_yolu)

        self.veri_surumu = cevir["veri_surumu"]
        self.sayaclar = cevir["sayaclar"]
        self.karantina_kararlari = cevir["karantina_kararlari"]

        tedarikci_sozluk = {}
        for tedarikci in cevir["tedarikciler"]:
            tedarikci_sozluk[tedarikci.tedarikci_kodu] = tedarikci
        self.tedarikciler = tedarikci_sozluk

        siparis_sozluk = {}
        for siparis in cevir["siparisler"]:
            siparis_sozluk[siparis.siparis_no] = siparis
        self.siparisler = siparis_sozluk

        mal_kabul_sozluk = {}
        for mal_kabul in cevir["mal_kabuller"]:
            mal_kabul_sozluk[mal_kabul.mal_kabul_no] = mal_kabul
        self.mal_kabuller = mal_kabul_sozluk

        fatura_sozluk = {}
        for fatura in cevir["faturalar"]:
            fatura_sozluk[fatura.fatura_no] = fatura
        self.faturalar = fatura_sozluk


    def _kaydet(self):
        veri = {}
        veri["veri_surumu"] = self.veri_surumu
        veri["sayaclar"] = self.sayaclar

        tedarikci_listem = []
        for degerler in self.tedarikciler.values():
            tedarikci_listem.append(degerler)
        veri["tedarikciler"] = tedarikci_listem

        siparis_listem = []
        for degerler in self.siparisler.values():
            siparis_listem.append(degerler)
        veri["siparisler"] = siparis_listem

        mal_kabul_listem = []
        for degerler in self.mal_kabuller.values():
             mal_kabul_listem.append(degerler)
        veri["mal_kabuller"] = mal_kabul_listem

        fatura_listem = []
        for degerler in self.faturalar.values():
            fatura_listem.append(degerler)
        veri["faturalar"] = fatura_listem

        veri["karantina_kararlari"] = self.karantina_kararlari

        kaydet(veri, self.dosya_yolu)

    
    
    def _numara_ver(self, onek):
        """Önekin sayacını bir artırır ve sıradaki belge numarasını döndürür.

        Sayaç önce artar, sonra numara üretilir (sayaç 0 ise ilk numara
        "SAS-0001"). Dosyaya yazmaz; işlemi yapan metot sonunda _kaydet'i
        çağırır.

        Args:
            onek: "TED", "SAS", "MKB" ya da "FTR".

        Returns:
            "SAS-0002" biçiminde numara.
        """
        self.sayaclar[onek] += 1
        return f"{onek}-{self.sayaclar[onek]:04d}"


    def _kayit_bul(self, kayitlar, numara):
        """Numarası verilen belgeyi verilen sözlükte bulur.

        Dört belge türü için tek yardımcı: hangi sözlükte aranacağını
        çağıran söyler (ör. self.siparisler).

        Args:
            kayitlar: Numarayla anahtarlı belge sözlüğü.
            numara: Aranan numara, ör. "SAS-0001".

        Returns:
            Bulunan belge nesnesi.

        Raises:
            KayitBulunamadiError: Numara sözlükte yoksa.
        """
        if numara not in kayitlar:
            raise KayitBulunamadiError(f"{numara} numaralı kayıt bulunamadı")
        return kayitlar[numara]

    
    def _aktif_mal_kabuller(self, siparis_no):
        """Siparişin iptal edilmemiş mal kabullerini verir.

        Args:
            siparis_no: Sipariş numarası, ör. "SAS-0001".

        Returns:
            MalKabul listesi, kayıt sırasıyla; yoksa boş liste.
        """
        aktif_mal_kabuller = []
        for mal_kabul in self.mal_kabuller.values():
            if (mal_kabul.siparis_no == siparis_no
                    and not mal_kabul.iptal_bilgisi.iptal_edildi):
                aktif_mal_kabuller.append(mal_kabul)
        return aktif_mal_kabuller


    
    def tedarikci_ekle(self, tedarikci_adi, firma_adi=None):
        """Yeni tedarikçiyi kaydeder ve döndürür.

        Kod kullanıcıdan alınmaz, sayaçtan üretilir. Ad kontrolü numara
        alınmadan önce yapılır; hatalı girişte sayaç artmaz.

        Args:
            tedarikci_adi: Zorunlu; boş ya da sadece boşluk olamaz.
            firma_adi: İsteğe bağlı.

        Returns:
            Oluşturulan Tedarikci.

        Raises:
            GecersizGirisError: Ad boşsa.
        """
        if not tedarikci_adi or not tedarikci_adi.strip():
            raise GecersizGirisError("Tedarikçi adı boş olamaz")

        tedarikci_kodu = self._numara_ver(ONEKLER["tedarikci"])
        yeni_tedarikci = Tedarikci(
            tedarikci_kodu=tedarikci_kodu,
            tedarikci_adi=tedarikci_adi.strip(),
            firma_adi=firma_adi,
        )
        self.tedarikciler[tedarikci_kodu] = yeni_tedarikci
        self._kaydet()
        return yeni_tedarikci

        
    
    def siparis_ac(self, tedarikci_kodu, kalemler, tolerans=None, tarih=None):
        """Yeni siparişi TASLAK olarak açar, kaydeder ve döndürür.

        Kalem numarasını ve tolerans kopyasını servis verir. Sipariş
        numarası bütün kalemler hatasız kurulduktan sonra alınır; hatalı
        girişte sayaç artmaz.

        Args:
            tedarikci_kodu: Kayıtlı tedarikçi kodu, ör. "TED-0001".
            kalemler: Kalem sözlüklerinin listesi. Zorunlu anahtarlar:
                malzeme_adi, miktar, birim, birim_fiyat, kategori.
                İsteğe bağlı: iskonto_turu, iskonto_degeri, miktar_tavani.
            tolerans: Verilirse bütün kalemlere bu ToleransKopyasi
                kopyalanır; None ise kategorinin ayarları kullanılır.
            tarih: "2026-11-02" biçiminde; None ise bugün.

        Returns:
            Oluşturulan Siparis.

        Raises:
            KayitBulunamadiError: Tedarikçi kayıtlı değilse.
            GecersizGirisError: Kalem yoksa ya da kategori geçersizse.
        """
        self._kayit_bul(self.tedarikciler, tedarikci_kodu)
        if not kalemler:
            raise GecersizGirisError("Siparişte en az bir kalem olmalı")
        if tarih is None:
            tarih = date.today().isoformat()

        siparis_kalemleri = []
        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            if kalem["kategori"] not in TOLERANSLAR:
                raise GecersizGirisError(
                    f"Geçersiz kategori: {kalem['kategori']}"
                )
            if tolerans is not None:
                kalem_toleransi = tolerans
            else:
                kalem_toleransi = ToleransKopyasi(
                    **TOLERANSLAR[kalem["kategori"]],
                    kucuk_fark_esigi=KUCUK_FARK_ESIGI,
                )

            siparis_kalemi = SiparisKalemi(
                kalem_no=kalem_no,
                malzeme_adi=kalem["malzeme_adi"],
                miktar=kalem["miktar"],
                birim=kalem["birim"],
                birim_fiyat=kalem["birim_fiyat"],
                kategori=kalem["kategori"],
                tolerans=kalem_toleransi,
                iskonto_turu=kalem.get("iskonto_turu", "ORAN"),
                iskonto_degeri=kalem.get("iskonto_degeri", Decimal("0")),
                miktar_tavani=kalem.get("miktar_tavani", None),
            )
            siparis_kalemleri.append(siparis_kalemi)
            kalem_no += KALEM_NO_ARTISI

        siparis_no = self._numara_ver(ONEKLER["siparis"])
        yeni_siparis = Siparis(
            siparis_no=siparis_no,
            tedarikci_kodu=tedarikci_kodu,
            siparis_kalemleri=siparis_kalemleri,
            kayit_tarihi=tarih,
        )
        self.siparisler[siparis_no] = yeni_siparis
        self._kaydet()
        return yeni_siparis
               
    
    def siparis_onayla(self, siparis_no):
        """TASLAK siparişi onaylar ve kaydeder.

        Durum elle değil durum_degistir ile değişir; izinli geçiş kontrolü
        orada yapılır. Hata çıkarsa kaydedilmez.

        Args:
            siparis_no: Onaylanacak siparişin numarası, ör. "SAS-0001".

        Raises:
            KayitBulunamadiError: Numara yoksa.
            IslemYapilamazError: Sipariş TASLAK değilse (zaten onaylıysa).
        """
        siparis_bul = self._kayit_bul(self.siparisler, siparis_no)
        siparis_bul.durum_degistir("ONAYLANDI")
        self._kaydet()

    def siparis_bul(self, siparis_no):
        """Siparişi numarasıyla bulur ve döndürür; hiçbir şeyi değiştirmez.

            Menü (ve v3'te API) siparişin satırlarını göstermek için kullanır;
            servisin iç sözlüğüne doğrudan dokunmaz (E100).

            Args:
                siparis_no: Sipariş numarası, ör. "SAS-0001".

            Returns:
                Bulunan Siparis.

            Raises:
                KayitBulunamadiError: Numara yoksa.
            """
        return self._kayit_bul(self.siparisler, siparis_no)



   
    def mal_kabul_kaydet(self, siparis_no, kalemler, tir_kapida=True,
                         mal_kabul_notu=None, tarih=None):
        """Onaylı siparişe mal kabul kaydeder ve sonucu döndürür.

        Her kalemde yanlış ürün gelen miktardan düşülür, kalan miktar
        kovalara_ayir ile kabul / karantina / kapıda red olarak bölünür;
        yanlış ürün kapıda red miktarına eklenir. Gelen ve yanlış ürünü 0
        olan kalem oluşturulmaz. Numara kontrollerden sonra alınır; hatalı
        girişte sayaç artmaz.

        Args:
            siparis_no: Onaylı siparişin numarası, ör. "SAS-0001".
            kalemler: Sözlük listesi. Her sözlükte "siparis_kalem_no" (int)
                ve "gelen_miktar" (Decimal); isteğe bağlı
                "yanlis_urun_miktari" (Decimal, yoksa 0).
            tir_kapida: Aşırı fazlalık kapıda geri verilebilir mi.
            mal_kabul_notu: İsteğe bağlı not.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Returns:
            MalKabulSonucu: kaydedilen MalKabul ve
            {sipariş kalem no: KovaSonucu}.

        Raises:
            KayitBulunamadiError: Sipariş yoksa.
            IslemYapilamazError: Sipariş onaylı değilse ya da kalem
                siparişte yoksa.
            GecersizGirisError: Hiç kalem oluşmadıysa.
        """
        siparis = self._kayit_bul(self.siparisler, siparis_no)
        if siparis.durum != "ONAYLANDI":
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş onaylı değil, mal kabul yapılamaz"
            )
        if tarih is None:
            tarih = date.today().isoformat()

        sip_sozluk = {}
        for sip in siparis.siparis_kalemleri:
            sip_sozluk[sip.kalem_no] = sip

        mal_kabul_kalemleri = []
        kova_sonuclari = {}
        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            gelen_miktar = kalem["gelen_miktar"]
            yanlis_urun_miktari = kalem.get("yanlis_urun_miktari", Decimal("0"))
            if gelen_miktar == 0 and yanlis_urun_miktari == 0:
                continue
            if kalem["siparis_kalem_no"] not in sip_sozluk:
                raise IslemYapilamazError(
                    f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                    f"kalem siparişte yok"
                )

            kalem_numarasi = sip_sozluk[kalem["siparis_kalem_no"]]
            fiyat_hesapla = net_fiyat_hesapla(
                birim_fiyat=kalem_numarasi.birim_fiyat,
                iskonto_turu=kalem_numarasi.iskonto_turu,
                iskonto_degeri=kalem_numarasi.iskonto_degeri,
            )
            kova = kovalara_ayir(
                siparis_miktari=kalem_numarasi.miktar,
                gelen_miktar=gelen_miktar - yanlis_urun_miktari,
                tolerans=kalem_numarasi.tolerans,
                miktar_tavani=kalem_numarasi.miktar_tavani,
                birim=kalem_numarasi.birim,
                net_birim_fiyat=fiyat_hesapla,
                tir_kapida=tir_kapida,
            )
            mal_kabul_kalemi = MalKabulKalemi(
                kalem_no=kalem_no,
                siparis_kalem_no=kalem["siparis_kalem_no"],
                kabul_edilen_miktar=kova.kabul,
                karantina_miktari=kova.karantina,
                kapida_reddedilen_miktar=kova.kapida_red + yanlis_urun_miktari,
            )
            mal_kabul_kalemleri.append(mal_kabul_kalemi)
            kova_sonuclari[kalem["siparis_kalem_no"]] = kova
            kalem_no += KALEM_NO_ARTISI

        if not mal_kabul_kalemleri:
            raise GecersizGirisError("Mal kabulde en az bir kalem olmalı")

        mal_kabul_no = self._numara_ver(ONEKLER["mal_kabul"])
        mal_kabul = MalKabul(
            mal_kabul_no=mal_kabul_no,
            siparis_no=siparis_no,
            mal_kabul_kalemleri=mal_kabul_kalemleri,
            kayit_tarihi=tarih,
            mal_kabul_notu=mal_kabul_notu,
        )
        self.mal_kabuller[mal_kabul_no] = mal_kabul
        self._kaydet()

        mal_kabul_sonucu = MalKabulSonucu(
            mal_kabul=mal_kabul,
            kova_sonuclari=kova_sonuclari,
        )
        return mal_kabul_sonucu

    def fatura_kaydet(self, siparis_no, tedarikci_fatura_no, kalemler,
                      tarih=None):
        """Onaylı siparişe fatura kaydeder; mal geldiyse eşleştirir.

        Miktarı 0 olan kalem oluşturulmaz. Numara kontrollerden sonra
        alınır; hatalı girişte sayaç artmaz. Siparişin aktif mal kabulü
        varsa eslestir çağrılır (o kaydeder); yoksa fatura
        ESLESME_BEKLIYOR olarak bekler.

        Args:
            siparis_no: Onaylı siparişin numarası, ör. "SAS-0001".
            tedarikci_fatura_no: Tedarikçinin kendi fatura numarası.
            kalemler: Sözlük listesi. Her sözlükte "siparis_kalem_no" (int),
                "miktar" ve "birim_fiyat" (Decimal); isteğe bağlı
                "iskonto_turu" ve "iskonto_degeri".
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Returns:
            Oluşturulan Fatura.

        Raises:
            KayitBulunamadiError: Sipariş yoksa.
            IslemYapilamazError: Sipariş onaylı değilse ya da kalem
                siparişte yoksa.
            GecersizGirisError: Hiç kalem oluşmadıysa.
        """
        siparis = self._kayit_bul(self.siparisler, siparis_no)
        if siparis.durum != "ONAYLANDI":
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş onaylı değil, fatura kaydedilemez"
            )
        if tarih is None:
            tarih = date.today().isoformat()

        sip_fatura_sozluk = {}
        for sip in siparis.siparis_kalemleri:
            sip_fatura_sozluk[sip.kalem_no] = sip

        fatura_kalemleri = []
        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            if kalem["miktar"] == 0:
                continue
            if kalem["siparis_kalem_no"] not in sip_fatura_sozluk:
                raise IslemYapilamazError(
                    f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                    f"kalem siparişte yok"
                )
            fatura_kalemi = FaturaKalemi(
                kalem_no=kalem_no,
                siparis_kalem_no=kalem["siparis_kalem_no"],
                miktar=kalem["miktar"],
                birim_fiyat=kalem["birim_fiyat"],
                mal_kabul_dagitimi=[],
                iskonto_turu=kalem.get("iskonto_turu", "ORAN"),
                iskonto_degeri=kalem.get("iskonto_degeri", Decimal("0")),
            )
            fatura_kalemleri.append(fatura_kalemi)
            kalem_no += KALEM_NO_ARTISI

        if not fatura_kalemleri:
            raise GecersizGirisError("Faturada en az bir kalem olmalı")

        fatura_no = self._numara_ver(ONEKLER["fatura"])
        fatura = Fatura(
            fatura_no=fatura_no,
            tedarikci_fatura_no=tedarikci_fatura_no,
            siparis_no=siparis_no,
            fatura_kalemleri=fatura_kalemleri,
            kayit_tarihi=tarih,
        )
        self.faturalar[fatura_no] = fatura

        if self._aktif_mal_kabuller(siparis_no):
            self.eslestir(fatura_no)
        else:
            self._kaydet()
        return fatura
    
    
    
    def _eslestirme_sonucu_hesapla(self, fatura):
        """Faturanın eşleştirme sonucunu hesaplar; hiçbir şeyi değiştirmez.

        Faturadaki her sipariş kalemi için aktif mal kabullerde kabul
        edilen ve aktif faturalarda faturalanan toplamları kurar, sonra
        kurallari_uygula'yı çağırır. Aktif mal kabul: iptal edilmemiş;
        aktif fatura: iptal edilmemiş ve REDDEDILDI olmayan.

        Args:
            fatura: Eşleştirilecek Fatura nesnesi.

        Returns:
            EslestirmeSonucu.
        """
        siparis_bul = self._kayit_bul(self.siparisler, fatura.siparis_no)
        kabul_toplamlari = {}
        faturalanan_toplamlar = {}

        for kalem in fatura.fatura_kalemleri:
            kabul_toplamlari[kalem.siparis_kalem_no] = Decimal("0")
            faturalanan_toplamlar[kalem.siparis_kalem_no] = Decimal("0")

        for deger in self._aktif_mal_kabuller(fatura.siparis_no):
            for kalemler in deger.mal_kabul_kalemleri:
                if kalemler.siparis_kalem_no in kabul_toplamlari:
                    kabul_toplamlari[kalemler.siparis_kalem_no] += (
                        kalemler.kabul_edilen_miktar)

        for deger in self.faturalar.values():
            if (deger.siparis_no == fatura.siparis_no
                    and not deger.iptal_bilgisi.iptal_edildi
                    and deger.durum != "REDDEDILDI"):
                for kalemler in deger.fatura_kalemleri:
                    if kalemler.siparis_kalem_no in faturalanan_toplamlar:
                        faturalanan_toplamlar[kalemler.siparis_kalem_no] += (
                            kalemler.miktar)

        kurallar = kurallari_uygula(
            siparis=siparis_bul,
            fatura=fatura,
            kabul_toplamlari=kabul_toplamlari,
            faturalanan_toplamlar=faturalanan_toplamlar,
        )
        return kurallar
    
    
    def eslestir(self, fatura_no):
        """Faturayı eşleştirir; sonucu faturaya yazar ve kaydeder.

        Hesabı _eslestirme_sonucu_hesapla yapar. Durum önce değiştirilir;
        fatura zaten eşleşmişse hata verir ve hiçbir şey yazılmaz. v1a'da
        siparişin tek aktif mal kabulü olduğu için her fatura kalemi o
        mal kabulden kendi miktarı kadar kapanır (mal kabul dağıtımı).

        Args:
            fatura_no: Eşleştirilecek faturanın numarası, ör. "FTR-0001".

        Returns:
            EslestirmeSonucu.

        Raises:
            KayitBulunamadiError: Fatura yoksa.
            IslemYapilamazError: Fatura ESLESME_BEKLIYOR değilse.
        """
        fatura = self._kayit_bul(self.faturalar, fatura_no)
        sonuc = self._eslestirme_sonucu_hesapla(fatura)

        fatura.durum_degistir(sonuc.durum())
        fatura.bloke_neden_kodlari = sonuc.neden_kodlari()

        mal_kabul = self._aktif_mal_kabuller(fatura.siparis_no)[0]
        for kalem in fatura.fatura_kalemleri:
            kalem.mal_kabul_dagitimi = [
                MalKabulDagitimi(
                    mal_kabul_no=mal_kabul.mal_kabul_no,
                    miktar=kalem.miktar,
                )
            ]

        self._kaydet()
        return sonuc
