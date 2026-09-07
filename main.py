import flet as ft
import yfinance as yf
import pandas as pd
from google import genai
from google.genai import types
import json
import urllib.request
import urllib.parse
import os
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri sisteme yükler
load_dotenv() 

# API anahtarını çevre değişkenlerinden güvenle çeker
API_KEY = os.getenv("GEMINI_API_KEY")

def get_gemini_analysis(quant_data_text, company_name):
    """Yeni nesil google.genai kütüphanesi ve Google Search aracı ile canlı veriye bağlanır."""
    client = genai.Client(api_key=API_KEY)
    
    system_instruction = """
    Sen kurumsal bir fonun kantitatif (nicel) analiz ve risk yönetimi uzmanısın.
    Görevin: Sana Python tabanlı algoritmik motordan gelen sayısal verileri analiz etmek ve Google Arama aracını kullanarak şirketle ilgili güncel KAP haberlerini, özel durum açıklamalarını ve son dakika gelişmelerini rapora yansıtmaktır.
    Kurallar:
    1. Verilen sayısal verilerin dışına çıkma, varsayım yapma.
    2. Google arama sonucunda bulduğun güncel KAP haberlerini veya önemli kurumsal gelişmeleri "Risk Uyarıları" veya ilgili alanlara mutlaka ekle.
    3. Fiyat SMA200'ün altındaysa trend "Negatif (Ayı)" olarak değerlendirilmelidir.
    4. Hacim, 20 günlük ortalamanın altındaysa yükselişleri "Teyitsiz/Fake" olarak uyar.
    5. Analiz sonucunda mutlaka Stop-Loss (ATR) seviyesini belirt.
    """

    prompt = f"""
    Şirket/Varlık: {company_name}
    Aşağıdaki kantitatif verileri ve güncel KAP/piyasa haberlerini web'de aratarak analiz et, tam olarak şu JSON formatında yanıt dön:
    {{
      "trend_analizi": "Trend durumu ve güncel teknik özet",
      "hacim_ve_istatistik": "Hacim, değerleme ve güncel haber/KAP durumu",
      "risk_uyarilari": "KAP bildirimleri, bilanço ve ATR Stop-Loss riskleri",
      "nihai_karar": "GÜÇLÜ AL, KADEMELİ AL, TUT veya UZAK DUR şeklinde kararını belirt ve yanına bir cümlelik teknik/temel gerekçeni yaz."
    }}
    
    TEKNİK VERİLER:
    {quant_data_text}
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            tools=[{"google_search": {}}]
        )
    )
    return json.loads(response.text)


# ==========================================
# 2. EVRENSEL ŞİRKET/KOD ARAMA VE VERİ MOTORU
# ==========================================
def resolve_ticker(user_input):
    """Kullanıcının yazdığı herhangi bir şirket adını veya kodu Yahoo arama motoruyla borsa koduna çevirir."""
    query = user_input.strip()
    if not query:
        return None

    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            quotes = data.get('quotes', [])
            if quotes:
                for q in quotes:
                    sym = q.get('symbol', '')
                    if sym.endswith('.IS'):
                        return sym
                return quotes[0].get('symbol')
    except Exception as e:
        print(f"Arama motoru hatası: {e}")

    text = query.upper()
    if "." not in text and "-" not in text:
        return text + ".IS"
    return text


def fetch_quant_data(user_query, period_val="1y"):
    """yfinance üzerinden ham verileri çeker ve hesaplar."""
    try:
        ticker = resolve_ticker(user_query)
        if not ticker:
            return None, None, "Lütfen geçerli bir şirket adı veya kod yazın."

        df = yf.download(ticker, period=period_val, progress=False)
        
        if df.empty and ticker.endswith(".IS"):
            ticker = user_query.strip().upper()
            df = yf.download(ticker, period=period_val, progress=False)
            
        if df.empty:
            return None, None, f"Veri bulunamadı: '{user_query}' için piyasa verisi eşleşmedi."
        
        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, axis=1, level=1)
            
        close_data = df['Close']
        vol_data = df['Volume']
        high_data = df['High']
        low_data = df['Low']

        current_price = float(close_data.iloc[-1])
        sma50 = float(close_data.tail(50).mean()) if len(close_data) >= 50 else float(close_data.mean())
        sma200 = float(close_data.tail(200).mean()) if len(close_data) >= 200 else float(close_data.mean())
        
        current_vol = float(vol_data.iloc[-1])
        vol_20g_avg = float(vol_data.tail(20).mean()) if len(vol_data) >= 20 else float(vol_data.mean())
        
        l252 = close_data.tail(252)
        pct_52h = ((current_price - l252.min()) / (l252.max() - l252.min())) * 100 if l252.max() != l252.min() else 50.0
        
        tr1 = high_data - low_data
        tr2 = (high_data - close_data.shift(1)).abs()
        tr3 = (low_data - close_data.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_14 = float(tr.tail(14).mean())
        stop_loss = current_price - (1.5 * atr_14)

        info = yf.Ticker(ticker).info
        pe_ratio = info.get("trailingPE", "Bilinmiyor")

        quant_text = f"""
        Varlık: {ticker.upper()}
        Güncel Fiyat: {current_price:.2f}
        SMA50: {sma50:.2f}
        SMA200: {sma200:.2f}
        Güncel Hacim: {current_vol:,.0f}
        20 Günlük Hacim Ort.: {vol_20g_avg:,.0f}
        52 Haftalık Konum: %{pct_52h:.1f}
        ATR (14) Değeri: {atr_14:.2f}
        Hesaplanan Stop-Loss (1.5x ATR): {stop_loss:.2f}
        F/K Oranı (Temel): {pe_ratio}
        """
        return quant_text, ticker, None
    except Exception as e:
        return None, None, f"Veri çekme hatası: {str(e)}"


# ==========================================
# 3. BACKTEST (GEÇMİŞ PERFORMANS) HESAPLAYICI
# ==========================================
def run_backtest_simulation(user_query):
    """SMA50 Kesişim Stratejisi ile Geçmiş Test (Backtest) Yapar"""
    try:
        ticker = resolve_ticker(user_query)
        df = yf.download(ticker, period="1y", progress=False)
        if df.empty and ticker.endswith(".IS"):
            ticker = user_query.strip().upper()
            df = yf.download(ticker, period="1y", progress=False)
        if df.empty or len(df) < 60:
            return "Yetersiz veri nedeniyle backtest yapılamadı."

        if isinstance(df.columns, pd.MultiIndex):
            df = df.xs(ticker, axis=1, level=1)

        close = df['Close']
        sma50 = close.rolling(window=50).mean()

        trades = 0
        wins = 0
        in_position = False
        entry_price = 0.0
        total_return = 0.0

        for i in range(50, len(close)):
            p = float(close.iloc[i])
            s50 = float(sma50.iloc[i])

            if not in_position and p > s50:
                in_position = True
                entry_price = p
                trades += 1
            elif in_position and p < s50:
                in_position = False
                ret = ((p - entry_price) / entry_price) * 100
                total_return += ret
                if ret > 0:
                    wins += 1

        win_rate = (wins / trades * 100) if trades > 0 else 0
        report = f"Varlık: {ticker}\nToplam Sinyal Sayısı: {trades}\nBaşarılı İşlem: {wins}\nKazanma Oranı (Win Rate): %{win_rate:.1f}\nToplam Strateji Getirisi: %{total_return:.1f}"
        return report
    except Exception as e:
        return f"Backtest hatası: {str(e)}"


# ==========================================
# 4. FLET MOBİL ARAYÜZ (UI)
# ==========================================
def main(page: ft.Page):
    page.title = "Master Fon Yöneticisi v11.1"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 410
    page.window.height = 800
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.padding = 15

    watchlist = ["THYAO.IS", "GARAN.IS", "EREGL.IS", "TSLA", "BTC-USD"]
    portfolio = [
        {"symbol": "THYAO.IS", "shares": 500, "buy_price": 250.0},
        {"symbol": "EREGL.IS", "shares": 1000, "buy_price": 45.0}
    ]

    title = ft.Text("Kantitatif Fon Terminali", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
    
    ticker_input = ft.TextField(label="Şirket Adı veya Kod (Örn: Tüpraş, Tesla)", width=240, border_color=ft.Colors.BLUE_200)
    
    period_dropdown = ft.Dropdown(
        label="Periyot",
        width=100,
        value="1y",
        options=[
            ft.dropdown.Option("6mo", "6 Ay"),
            ft.dropdown.Option("1y", "1 Yıl"),
            ft.dropdown.Option("2y", "2 Yıl"),
        ]
    )

    loading_ring = ft.ProgressRing(visible=False, width=20, height=20)
    status_text = ft.Text("", color=ft.Colors.YELLOW_400, italic=True, size=12)

    result_column = ft.Column(visible=False, spacing=12)
    trend_text = ft.Text(size=13)
    vol_text = ft.Text(size=13)
    risk_text = ft.Text(size=13, color=ft.Colors.RED_300)
    decision_text = ft.Text(size=15, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)

    backtest_input = ft.TextField(label="Backtest Varlık (Örn: THY, AAPL)", width=240, border_color=ft.Colors.BLUE_200)
    backtest_result_text = ft.Text(size=13, color=ft.Colors.GREEN_300)

    def run_analysis(query):
        switch_view("analiz")
        ticker_input.value = query
        page.update()
        
        analyze_button.disabled = True
        loading_ring.visible = True
        result_column.visible = False
        status_text.value = f"{query} taranıyor..."
        page.update()

        quant_data, ticker, error = fetch_quant_data(query, period_dropdown.value)
        
        if error:
            status_text.value = error
            loading_ring.visible = False
            analyze_button.disabled = False
            page.update()
            return

        status_text.value = "Yapay Zeka ve Canlı KAP taranıyor..."
        page.update()
        
        try:
            ai_report = get_gemini_analysis(quant_data, ticker)
            
            trend_text.value = ai_report.get("trend_analizi", "Bilgi yok.")
            vol_text.value = ai_report.get("hacim_ve_istatistik", "Bilgi yok.")
            risk_text.value = ai_report.get("risk_uyarilari", "Bilgi yok.")
            
            karar = ai_report.get("nihai_karar", "")
            decision_text.value = f"KARAR: {karar}"
            
            if "GÜÇLÜ AL" in karar: decision_text.color = ft.Colors.GREEN_400
            elif "KADEMELİ AL" in karar: decision_text.color = ft.Colors.YELLOW_400
            elif "AYI" in karar or "UZAK DUR" in karar: decision_text.color = ft.Colors.RED_400
            else: decision_text.color = ft.Colors.WHITE

            result_column.visible = True
            status_text.value = "Analiz Tamamlandı."
        except Exception as err:
            status_text.value = "AI Hatası oluştu."
            print(err)

        loading_ring.visible = False
        analyze_button.disabled = False
        page.update()

    def on_analyze_click(e):
        if not ticker_input.value:
            status_text.value = "Lütfen bir değer girin!"
            page.update()
            return
        run_analysis(ticker_input.value.strip())

    analyze_button = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.ANALYTICS, color=ft.Colors.WHITE, size=16), ft.Text("ANALİZ ET", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
        on_click=on_analyze_click,
        width=350,
        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, shape=ft.RoundedRectangleBorder(radius=8))
    )

    # --- İZLEME LİSTESİ YÖNETİMİ ---
    watchlist_input = ft.TextField(label="Yeni Favori Ekle (Örn: ASELS)", width=230, border_color=ft.Colors.BLUE_200)
    watchlist_column = ft.Column(spacing=8)

    def add_to_watchlist(e):
        val = watchlist_input.value.strip()
        if val:
            resolved = resolve_ticker(val)
            if resolved and resolved not in watchlist:
                watchlist.append(resolved)
                watchlist_input.value = ""
                refresh_watchlist()

    def remove_from_watchlist(item):
        if item in watchlist:
            watchlist.remove(item)
            refresh_watchlist()

    def refresh_watchlist():
        watchlist_column.controls.clear()
        for item in watchlist:
            watchlist_column.controls.append(
                ft.Row([
                    ft.Text(item, width=120, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Button(content=ft.Text("İncele", size=11), on_click=lambda e, q=item: run_analysis(q), height=28),
                        ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_400, icon_size=18, on_click=lambda e, q=item: remove_from_watchlist(q))
                    ])
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            )
        page.update()

    add_watchlist_button = ft.Button(
        content=ft.Text("Ekle", color=ft.Colors.WHITE),
        on_click=add_to_watchlist,
        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, shape=ft.RoundedRectangleBorder(radius=6))
    )

    # --- PORTFÖY YÖNETİMİ ---
    pf_sym_input = ft.TextField(label="Sembol/Ad", width=110, border_color=ft.Colors.BLUE_200)
    pf_shares_input = ft.TextField(label="Adet", width=85, border_color=ft.Colors.BLUE_200)
    pf_price_input = ft.TextField(label="Maliyet", width=95, border_color=ft.Colors.BLUE_200)
    portfolio_column = ft.Column(spacing=8)

    def add_to_portfolio(e):
        try:
            s_val = pf_sym_input.value.strip()
            sh_val = float(pf_shares_input.value)
            pr_val = float(pf_price_input.value)
            if s_val:
                resolved = resolve_ticker(s_val)
                portfolio.append({"symbol": resolved, "shares": sh_val, "buy_price": pr_val})
                pf_sym_input.value = ""
                pf_shares_input.value = ""
                pf_price_input.value = ""
                refresh_portfolio()
        except:
            pass

    def remove_from_portfolio(index):
        if 0 <= index < len(portfolio):
            portfolio.pop(index)
            refresh_portfolio()

    def refresh_portfolio():
        portfolio_column.controls.clear()
        for idx, p in enumerate(portfolio):
            try:
                df = yf.download(p["symbol"], period="1d", progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df = df.xs(p["symbol"], axis=1, level=1)
                curr_p = float(df['Close'].iloc[-1])
                val = curr_p * p["shares"]
                cost = p["buy_price"] * p["shares"]
                pnl = val - cost
                pnl_pct = (pnl / cost) * 100 if cost > 0 else 0
                
                color = ft.Colors.GREEN_400 if pnl >= 0 else ft.Colors.RED_400
                portfolio_column.controls.append(
                    ft.Container(
                        padding=10, bgcolor=ft.Colors.SURFACE_CONTAINER, border_radius=8,
                        content=ft.Column([
                            ft.Row([ft.Text(p["symbol"], weight=ft.FontWeight.BOLD), ft.Text(f"{curr_p:.2f} TL")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([
                                ft.Text(f"Adet: {p['shares']} | K/Z: %{pnl_pct:.1f}", color=color, size=12, weight=ft.FontWeight.BOLD),
                                ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_400, icon_size=16, on_click=lambda e, i=idx: remove_from_portfolio(i))
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        ])
                    )
                )
            except:
                pass
        page.update()

    add_portfolio_button = ft.Button(
        content=ft.Text("Portföye Ekle", color=ft.Colors.WHITE, size=12),
        on_click=add_to_portfolio,
        style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, shape=ft.RoundedRectangleBorder(radius=6))
    )

    def on_backtest_click(e):
        if not backtest_input.value:
            backtest_result_text.value = "Lütfen varlık adı yazın!"
            page.update()
            return
        backtest_result_text.value = "Geçmiş veriler simüle ediliyor..."
        page.update()
        res = run_backtest_simulation(backtest_input.value.strip())
        backtest_result_text.value = res
        page.update()

    backtest_button = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.HISTORY, color=ft.Colors.WHITE, size=16), ft.Text("STRATEJİYİ TEST ET (BACKTEST)", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
        on_click=on_backtest_click,
        width=350,
        style=ft.ButtonStyle(bgcolor=ft.Colors.INDIGO_700, shape=ft.RoundedRectangleBorder(radius=8))
    )

    refresh_watchlist()
    refresh_portfolio()

    # Görünüm Alanları (Views)
    result_column.controls.extend([
        ft.Divider(),
        ft.Card(content=ft.Container(padding=12, content=ft.Column([ft.Text("📈 Trend Durumu", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_200), trend_text]))),
        ft.Card(content=ft.Container(padding=12, content=ft.Column([ft.Text("📊 Hacim ve İstatistik", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_200), vol_text]))),
        ft.Card(content=ft.Container(padding=12, content=ft.Column([ft.Text("⚠️ Risk Uyarıları (KAP / Stop-Loss)", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_300), risk_text]))),
        ft.Container(padding=15, bgcolor=ft.Colors.ON_INVERSE_SURFACE, border_radius=10, content=decision_text)
    ])

    analiz_view = ft.Column([
        ft.Container(height=5),
        ft.Row([ticker_input, period_dropdown], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        analyze_button,
        ft.Row([loading_ring, status_text], alignment=ft.MainAxisAlignment.CENTER),
        result_column
    ], scroll=ft.ScrollMode.ADAPTIVE)

    watchlist_view = ft.Column([
        ft.Container(height=5),
        ft.Text("Favori Varlıklar Yönetimi", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_200),
        ft.Row([watchlist_input, add_watchlist_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(),
        watchlist_column
    ], scroll=ft.ScrollMode.ADAPTIVE)

    portfolio_view = ft.Column([
        ft.Container(height=5),
        ft.Text("Portföy ve Maliyet Yönetimi", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_200),
        ft.Row([pf_sym_input, pf_shares_input, pf_price_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        add_portfolio_button,
        ft.Divider(),
        portfolio_column
    ], scroll=ft.ScrollMode.ADAPTIVE)

    backtest_view = ft.Column([
        ft.Container(height=5),
        ft.Text("Geçmiş Sinyal Başarı Testi", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_200),
        backtest_input,
        backtest_button,
        ft.Container(height=10),
        ft.Card(content=ft.Container(padding=15, content=backtest_result_text))
    ], scroll=ft.ScrollMode.ADAPTIVE)

    content_area = ft.Container(content=analiz_view, expand=True)

    def switch_view(view_name):
        if view_name == "analiz":
            content_area.content = analiz_view
        elif view_name == "watchlist":
            refresh_watchlist()
            content_area.content = watchlist_view
        elif view_name == "portfolio":
            refresh_portfolio()
            content_area.content = portfolio_view
        elif view_name == "backtest":
            content_area.content = backtest_view
        page.update()

    nav_bar = ft.Row([
        ft.ElevatedButton("Analiz", on_click=lambda e: switch_view("analiz")),
        ft.ElevatedButton("İzleme", on_click=lambda e: switch_view("watchlist")),
        ft.ElevatedButton("Portföy", on_click=lambda e: switch_view("portfolio")),
        ft.ElevatedButton("Backtest", on_click=lambda e: switch_view("backtest")),
    ], alignment=ft.MainAxisAlignment.SPACE_AROUND)

    page.add(
        ft.Column([
            title,
            ft.Text("Gelişmiş Kantitatif Terminal ve Portföy Yöneticisi", color=ft.Colors.GREY_400, size=11),
            ft.Divider(),
            nav_bar,
            ft.Divider(),
            content_area
        ], expand=True)
    )

if __name__ == "__main__":
    ft.run(main)