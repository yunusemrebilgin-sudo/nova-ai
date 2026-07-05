# NOVA v1.2

NOVA AI

Professional Trading Terminal

## v1.2 Yenilikleri

- `🔥 Smart Scanner` sayfası
- BIST hisseleri için filtrelenebilir profesyonel tarama
- Smart Scanner filtreleri:
  - Trend
  - Momentum
  - Nova Score
  - Nova AI Güven Endeksi
  - EMA20 > EMA50
  - MACD
  - RSI
  - Hacim
  - Volatilite
- Smart Scanner sonuç tablosu:
  - Sıra
  - Hisse
  - Şirket
  - Nova Score
  - AI Güven Endeksi
  - Beklenen Getiri %
  - Beklenen Taşıma Süresi
  - Alım Uygunluğu %
  - Sat Riski %
  - Trend
  - Sonuç
- `🔥 Bugünün En Güçlü 10 Hissesi` kartları
- Decision Center 2.0 premium görünüm
- Circular Nova AI Güven Endeksi
- Progress bar skorları
- Radar Chart
- AI Yorumu kartı
- Grafikte EMA20, EMA50, destek, direnç, stop, hedef 1 ve hedef 2 çizgileri
- Final fix: Decision Center kart taşmaları düzeltildi
- Final fix: Beklenen Taşıma Süresi özel büyük kart olarak öne çıkarıldı
- Final fix: Sol dikey karar kutucukları eklendi
- Final fix: Dar ekranlarda metinlerin kesilmeden alt satıra inmesi iyileştirildi

## Modüler Kod Yapısı

Yeni altyapı dosyaları:

- `analytics.py`
- `scanner.py`
- `decision_center.py`
- `theme.py`
- `portfolio.py`
- `news.py`
- `signals.py`
- `utils.py`

## Korunan Özellikler

- Dashboard
- Piyasa Tarayıcı
- BIST 500+ yerel CSV listesi
- Dark / Light tema
- Nova Skoru
- Vade bazlı karar merkezi
- Streamlit cache kullanımı

## Kurulum

```powershell
py -m pip install -r requirements.txt
```

## Çalıştırma

```powershell
py -m streamlit run app.py
```

## Uyarı

Bu platform yalnızca karar destek amaçlıdır. Kesin yatırım tavsiyesi vermez.
