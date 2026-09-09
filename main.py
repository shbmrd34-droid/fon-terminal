import flet as ft
import urllib.request
import urllib.parse
import json

# RENDER SUNUCU ADRESİNİZ
API_BASE = "https://fon-api.onrender.com"

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
        status_text.value = f"{query} buluttan taranıyor..."
        page.update()

        try:
            encoded_q = urllib.parse.quote(query)
            url = f"{API_BASE}/analiz?sembol={encoded_q}&period={period_dropdown.value}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            
            with urllib.request.urlopen(req, timeout=30) as response:
                ai_report = json.loads(response.read().decode())

            if "hata" in ai_report:
                status_text.value = ai_report["hata"]
                loading_ring.visible = False
                analyze_button.disabled = False
                page.update()
                return

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
            status_text.value = "Bulut bağlantı hatası oluştu."
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
            resolved = val.upper()
            if resolved not in watchlist:
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
            s_val = pf_sym_input.value.strip().upper()
            sh_val = float(pf_shares_input.value)
            pr_val = float(pf_price_input.value)
            if s_val:
                portfolio.append({"symbol": s_val, "shares": sh_val, "buy_price": pr_val})
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
                url = f"{API_BASE}/fiyat?sembol={urllib.parse.quote(p['symbol'])}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    res_data = json.loads(response.read().decode())
                
                curr_p = float(res_data['fiyat'])
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
        backtest_result_text.value = "Geçmiş veriler bulutta simüle ediliyor..."
        page.update()
        
        try:
            url = f"{API_BASE}/backtest?sembol={urllib.parse.quote(backtest_input.value.strip())}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                res = json.loads(response.read().decode())
            backtest_result_text.value = res.get("report", "Sonuç alınamadı.")
        except Exception as ex:
            backtest_result_text.value = f"Backtest hatası: {str(ex)}"
        page.update()

    backtest_button = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.HISTORY, color=ft.Colors.WHITE, size=16), ft.Text("STRATEJİYİ TEST ET (BACKTEST)", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
        on_click=on_backtest_click,
        width=350,
        style=ft.ButtonStyle(bgcolor=ft.Colors.INDIGO_700, shape=ft.RoundedRectangleBorder(radius=8))
    )

    refresh_watchlist()
    refresh_portfolio()

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
