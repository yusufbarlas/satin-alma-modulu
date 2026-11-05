from dataclasses import dataclass, field
from decimal import Decimal

from para import net_fiyat_hesapla , tutar_yuvarla

from hatalar import IslemYapilamazError



SIPARIS_DURUM_GECISLERI = {"TASLAK": ["ONAYLANDI"], "ONAYLANDI": []}

FATURA_DURUM_GECISLERI = {
    "ESLESME_BEKLIYOR": ["ONAYLANDI", "BLOKE", "REDDEDILDI"],
    "BLOKE": ["SERBEST", "REDDEDILDI"],
    "ONAYLANDI": [],
    "SERBEST": [],
    "REDDEDILDI": [],
}

@dataclass
class Tedarikci:
    tedarikci_kodu: str 
    tedarikci_adi: str 
    firma_adi: str | None = None


@dataclass
class IptalBilgisi:
    iptal_edildi: bool = False  
    iptal_gerekcesi: str | None = None
    iptal_notu: str | None = None
    iptal_tarihi: str | None = None


@dataclass
class ToleransKopyasi:
    fazla_teslimat_yuzde: Decimal | None
    fazla_teslimat_tl: Decimal | None
    asiri_sinir_yuzde: Decimal | None 
    asiri_sinir_tl: Decimal | None
    fiyat_ust_yuzde: Decimal | None 
    fiyat_ust_tl: Decimal | None 
    fiyat_alt_yuzde: Decimal | None 
    fiyat_alt_tl: Decimal | None
    kucuk_fark_esigi: Decimal  

@dataclass
class SiparisKalemi:
    kalem_no: int 
    malzeme_adi: str
    miktar: Decimal
    birim: str 
    birim_fiyat: Decimal
    kategori: str 
    tolerans: ToleransKopyasi
    iskonto_turu: str = "ORAN"
    iskonto_degeri: Decimal = Decimal("0")
    miktar_tavani: Decimal | None = None

    def tutar(self):
        """Kalem tutarı: miktar × net birim fiyat; tek kez yuvarlanır (E35)."""
        net_fiyat = net_fiyat_hesapla(
            self.birim_fiyat, self.iskonto_turu, self.iskonto_degeri
        )
        return tutar_yuvarla(net_fiyat * self.miktar)

    
@dataclass
class Siparis:
    siparis_no: str
    tedarikci_kodu: str 
    siparis_kalemleri: list[SiparisKalemi]
    kayit_tarihi: str 
    durum: str = "TASLAK"
    iptal_bilgisi: IptalBilgisi = field(default_factory=IptalBilgisi)

    def genel_toplam(self):
        """Bütün kalem tutarlarının toplamı."""
        toplam = Decimal("0")
        for kalem in self.siparis_kalemleri:
            toplam += kalem.tutar()
        return toplam

    def durum_degistir(self, yeni_durum):
        """Durumu tablodaki izinli geçişe göre değiştirir; değilse hata."""
        izinli_durumlar = SIPARIS_DURUM_GECISLERI[self.durum]
        if yeni_durum not in izinli_durumlar:
            raise IslemYapilamazError(
                f"{self.siparis_no}: {self.durum} → {yeni_durum} geçişine izin yok"
            )
        self.durum = yeni_durum

           
               
@dataclass
class MalKabulKalemi:
    kalem_no: int
    siparis_kalem_no: int
    kabul_edilen_miktar: Decimal
    karantina_miktari: Decimal = Decimal("0")
    karantina_nedeni: str | None = None
    kapida_reddedilen_miktar: Decimal = Decimal("0")
    kapida_red_nedeni: str | None = None


@dataclass
class MalKabul:
    mal_kabul_no: str
    siparis_no: str 
    mal_kabul_kalemleri: list[MalKabulKalemi]
    kayit_tarihi: str 
    mal_kabul_notu: str | None = None
    iptal_bilgisi: IptalBilgisi = field(default_factory=IptalBilgisi)


@dataclass
class MalKabulDagitimi:
    mal_kabul_no: str
    miktar: Decimal


@dataclass
class FaturaKalemi:
    kalem_no: int 
    siparis_kalem_no: int 
    miktar: Decimal
    birim_fiyat: Decimal
    mal_kabul_dagitimi: list[MalKabulDagitimi]
    iskonto_turu: str = "ORAN"
    iskonto_degeri: Decimal = Decimal("0")

    def tutar(self):
            net_fiyat = net_fiyat_hesapla(
                        self.birim_fiyat, self.iskonto_turu, self.iskonto_degeri
                    )
            return tutar_yuvarla(net_fiyat * self.miktar)


@dataclass
class Fatura:
    fatura_no: str 
    tedarikci_fatura_no: str 
    siparis_no: str 
    fatura_kalemleri: list[FaturaKalemi]
    kayit_tarihi: str 
    durum: str = "ESLESME_BEKLIYOR"
    bloke_neden_kodlari: list[str] = field(default_factory=list)
    karar_gerekcesi: str | None = None
    karar_notu: str | None = None
    iptal_bilgisi: IptalBilgisi = field(default_factory=IptalBilgisi)


    def genel_toplam(self):
        """Bütün kalem tutarlarının toplamı."""
        toplam = Decimal("0")
        for kalem in self.fatura_kalemleri:
            toplam += kalem.tutar()
        return toplam 

    def durum_degistir(self , yeni_durum):
        """Durumu tablodaki izinli geçişe göre değiştirir; değilse hata."""
        durum_izinleri = FATURA_DURUM_GECISLERI[self.durum]
        if yeni_durum not in durum_izinleri:
            raise IslemYapilamazError(f"{self.fatura_no}: {self.durum}  → {yeni_durum} geçişine izin yok ")
        self.durum = yeni_durum


        






















if __name__ == "__main__":
    t = Tedarikci("TED-0001", "ABC Kırtasiye")
    print(t) 

    print(IptalBilgisi())
   
    bos_tolerans = ToleransKopyasi(
        Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
        Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
        Decimal("0"),
    )

    kalem1 = SiparisKalemi(
        10, "A4 kagit", Decimal("10"), "adet", Decimal("12.50"),
        "SARF", bos_tolerans, "ORAN", Decimal("10"),
    )
    kalem2 = SiparisKalemi(
        20, "Toner", Decimal("3"), "adet", Decimal("10.555"),
        "SARF", bos_tolerans,
    )

    print(kalem1.tutar())   # 112.50
    print(kalem2.tutar())   # 31.67

    sip1 = Siparis("sip1" , "ted1" , [kalem1 , kalem2] , "2026-10-10" ,)
    print(sip1.genel_toplam())

    kalem  = MalKabulKalemi(10 , 10 , Decimal("10"))
    Mlkbl = MalKabul("MKB-0001" , "SAS-0001" , [kalem] , "2026-11-02")
    print(kalem)
    print(Mlkbl)
    print(Mlkbl.iptal_bilgisi.iptal_edildi)


    dagitim = MalKabulDagitimi("MKB-0001", Decimal("10"))
    deneme3 = FaturaKalemi(10 , 10 , Decimal("10") , Decimal("12.50") , [dagitim] , "ORAN" , Decimal("10"))
    deneme4 =  FaturaKalemi(11 , 12 , Decimal("10") , Decimal("18.90") , [dagitim] , "ORAN" , Decimal("10"))
    print(deneme3)
    print(dagitim)
    print(deneme3.tutar()) # 112.50

    fatura = Fatura("FTR-0001", "A-123", "SAS-0001", [deneme3,deneme4], "2026-11-02")
    print(fatura.genel_toplam()) # 282.60
    print(fatura.durum) # ESLESME_BEKLİYOR
    print(fatura.bloke_neden_kodlari) # []
    fatura.durum_degistir('ONAYLANDI')
    print(fatura.durum)  # ONAYLANDI

    try:
        fatura.durum_degistir("BLOKE")
    except IslemYapilamazError as hata:
        print(hata)   # FTR-001: ONAYLANDI => BLOKE geçişine izin yok.


    

