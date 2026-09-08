import flet as ft
import urllib.request
import json

# BURAYA RENDER'IN SANA VERDİĞİ LİNKİ YAPIŞTIR (Sonundaki /analiz?sembol= kısmına dikkat et)
API_URL = "https://fon-api.onrender.com/analiz?sembol="

def main(page: ft.Page):
    page.title = "Fon Terminali"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 400
    page.window_height = 800
    
    sonuc_metni = ft.Text("Veri bekleniyor...", size=16)
    
    def veri_getir(e):
        sonuc_metni.value = "Buluttan veri çekiliyor..."
        page.update()
        
        try:
            # Bulut sunucumuza bağlanıyoruz (Sadece saf metin çekiyoruz)
            url = API_URL + "THYAO.IS"
            istek = urllib.request.urlopen(url)
            veri = json.loads(istek.read().decode())
            
            if "hata" in veri:
                sonuc_metni.value = f"Hata: {veri['hata']}"
            else:
                sonuc_metni.value = (
                    f"Sembol: {veri['sembol']}\n"
                    f"Fiyat: {veri['fiyat']} TL\n"
                    f"SMA200: {veri['sma200']}\n"
                    f"Trend: {veri['trend']}"
                )
        except Exception as ex:
            sonuc_metni.value = f"Bağlantı hatası: {str(ex)}"
        
        page.update()

    buton = ft.ElevatedButton("THYAO Analiz Et", on_click=veri_getir)
    
    page.add(
        ft.Text("Kantitatif Fon Terminali", size=24, weight="bold"),
        buton,
        sonuc_metni
    )

ft.app(target=main)
