#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np
import os
import pytz
import logging
import json
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static_water', template_folder='templates_water')
CORS(app)

US_TIMEZONE = pytz.timezone('America/New_York')
cache = {}
CACHE_DURATION = 30

# ============================================================
# 🌊 DONNÉES EAU
# ============================================================

WATER_DATA = {
    'PHO': {'name': 'Invesco Water ETF', 'exchange': 'NASDAQ', 'category': 'ETF'},
    'FIW': {'name': 'First Trust Water ETF', 'exchange': 'NASDAQ', 'category': 'ETF'},
    'CGW': {'name': 'Invesco S&P Water ETF', 'exchange': 'NYSE', 'category': 'ETF'},
    'PIO': {'name': 'Invesco Global Water ETF', 'exchange': 'NASDAQ', 'category': 'ETF'},
    'EVX': {'name': 'VanEck Water ETF', 'exchange': 'NASDAQ', 'category': 'ETF'},
    'AWK': {'name': 'American Water Works', 'exchange': 'NYSE', 'category': 'Action'},
    'XYL': {'name': 'Xylem Inc.', 'exchange': 'NYSE', 'category': 'Action'},
    'AWR': {'name': 'American States Water', 'exchange': 'NYSE', 'category': 'Action'},
    'WTRG': {'name': 'Essential Utilities', 'exchange': 'NYSE', 'category': 'Action'},
    'MSEX': {'name': 'Middlesex Water Co.', 'exchange': 'NASDAQ', 'category': 'Action'},
    'CWT': {'name': 'California Water Service', 'exchange': 'NYSE', 'category': 'Action'},
    'SJW': {'name': 'SJW Group', 'exchange': 'NYSE', 'category': 'Action'},
    'ARTNA': {'name': 'Artesian Resources', 'exchange': 'NASDAQ', 'category': 'Action'},
    'YORW': {'name': 'York Water Co.', 'exchange': 'NASDAQ', 'category': 'Action'},
    'VE': {'name': 'Veolia Environnement', 'exchange': 'NYSE', 'category': 'Action'},
    'SUEZ': {'name': 'Suez Environnement', 'exchange': 'NYSE', 'category': 'Action'},
    'WAT': {'name': 'Waters Corporation', 'exchange': 'NYSE', 'category': 'Action'},
    'ECL': {'name': 'Ecolab Inc.', 'exchange': 'NYSE', 'category': 'Action'},
    'TTC': {'name': 'Toro Company', 'exchange': 'NYSE', 'category': 'Action'},
}

WATER_WATCHLIST = list(WATER_DATA.keys())

# ============================================================
# FONCTIONS
# ============================================================

def safe_float(v, default=0.0):
    try:
        if pd.isna(v) or v is None:
            return default
        return float(v)
    except:
        return default

def safe_int(v, default=0):
    try:
        if pd.isna(v) or v is None:
            return default
        return int(v)
    except:
        return default

def get_cached(key):
    if key in cache:
        data, ts = cache[key]
        if (datetime.now() - ts).seconds < CACHE_DURATION:
            return data
    return None

def set_cached(key, data):
    cache[key] = (data, datetime.now())

# ============================================================
# ROUTES STATIQUES
# ============================================================

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static_water', filename)

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/api/clear-cache')
def clear_cache():
    cache.clear()
    return jsonify({'status': 'ok'})

# ============================================================
# 🌊 ROUTES API EAU
# ============================================================

@app.route('/api/water/<symbol>')
def get_water_trading(symbol):
    try:
        cached = get_cached(f"water_trading_{symbol}")
        if cached:
            return jsonify(cached)

        logger.info(f"Fetching water stock: {symbol}")
        ticker = yf.Ticker(symbol)

        hist_test = ticker.history(period='1d')
        if hist_test.empty:
            return jsonify({'error': f'Symbole {symbol} non trouvé'}), 404

        periods = {
            '1d': '1m',
            '5d': '5m',
            '1mo': '15m',
            '3mo': '1h',
            '6mo': '1d',
            '1y': '1d',
        }

        water_info = WATER_DATA.get(symbol, {})

        result = {
            'symbol': symbol,
            'name': water_info.get('name', symbol),
            'exchange': water_info.get('exchange', 'Water Stock'),
            'currency': 'USD',
            'category': water_info.get('category', 'Action'),
            'data': {}
        }

        for period, interval in periods.items():
            try:
                hist = ticker.history(period=period, interval=interval)
                if hist.empty:
                    continue

                if hist.index.tz is None:
                    hist.index = hist.index.tz_localize('UTC').tz_convert(US_TIMEZONE)
                else:
                    hist.index = hist.index.tz_convert(US_TIMEZONE)

                close = hist['Close'].values
                high = hist['High'].values
                low = hist['Low'].values

                candles = []
                for idx, row in hist.iterrows():
                    candles.append({
                        'time': int(idx.timestamp()),
                        'open': safe_float(row['Open']),
                        'high': safe_float(row['High']),
                        'low': safe_float(row['Low']),
                        'close': safe_float(row['Close']),
                        'volume': safe_int(row['Volume'])
                    })

                if not candles:
                    continue

                result['data'][period] = {
                    'candles': candles,
                    'stats': {
                        'current_price': safe_float(close[-1]),
                        'change': safe_float(close[-1] - close[-2]) if len(close) > 1 else 0,
                        'change_percent': safe_float(((close[-1] - close[-2]) / close[-2] * 100)) if len(close) > 1 and close[-2] != 0 else 0,
                        'high': safe_float(max(high)),
                        'low': safe_float(min(low)),
                        'volume': safe_int(hist['Volume'].sum()),
                        'open': safe_float(close[0]) if len(close) > 0 else 0
                    }
                }

            except Exception as e:
                logger.error(f"Erreur {period} {symbol}: {e}")
                continue

        if not result['data']:
            return jsonify({'error': f'Aucune donnée pour {symbol}'}), 404

        set_cached(f"water_trading_{symbol}", result)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Erreur {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/water-watchlist')
def get_water_watchlist():
    try:
        results = []
        for symbol in WATER_WATCHLIST:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                hist = ticker.history(period='1d')

                current = safe_float(info.get('regularMarketPrice', 0))
                if current == 0 and not hist.empty:
                    current = safe_float(hist['Close'].iloc[-1])

                prev = safe_float(info.get('regularMarketPreviousClose', 0))
                if prev == 0 and len(hist) > 1:
                    prev = safe_float(hist['Close'].iloc[-2])

                change_pct = ((current - prev) / prev * 100) if prev else 0

                water_info = WATER_DATA.get(symbol, {})

                results.append({
                    'symbol': symbol,
                    'name': water_info.get('name', symbol),
                    'price': current,
                    'changePercent': change_pct,
                    'change': current - prev,
                    'currency': 'USD',
                    'category': water_info.get('category', 'Action'),
                    'exchange': water_info.get('exchange', 'N/A')
                })
            except Exception as e:
                logger.warning(f"Erreur watchlist water {symbol}: {e}")
                results.append({'symbol': symbol, 'error': str(e)})

        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/water-top-performers')
def get_water_top_performers():
    try:
        performers = []
        for symbol in WATER_WATCHLIST:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                hist = ticker.history(period='1d')

                current = safe_float(info.get('regularMarketPrice', 0))
                if current == 0 and not hist.empty:
                    current = safe_float(hist['Close'].iloc[-1])

                prev = safe_float(info.get('regularMarketPreviousClose', 0))
                if prev == 0 and len(hist) > 1:
                    prev = safe_float(hist['Close'].iloc[-2])

                change_pct = ((current - prev) / prev * 100) if prev else 0

                performers.append({
                    'symbol': symbol,
                    'name': WATER_DATA.get(symbol, {}).get('name', symbol),
                    'price': current,
                    'changePercent': change_pct,
                    'currency': 'USD',
                    'category': WATER_DATA.get(symbol, {}).get('category', 'Action')
                })
            except:
                continue

        performers.sort(key=lambda x: x['changePercent'], reverse=True)
        return jsonify(performers)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/water-index')
def get_water_index():
    try:
        prices = []
        changes = []
        components = []

        for symbol in WATER_WATCHLIST[:10]:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                hist = ticker.history(period='1d')

                current = safe_float(info.get('regularMarketPrice', 0))
                if current == 0 and not hist.empty:
                    current = safe_float(hist['Close'].iloc[-1])

                prev = safe_float(info.get('regularMarketPreviousClose', 0))
                if prev == 0 and len(hist) > 1:
                    prev = safe_float(hist['Close'].iloc[-2])

                change_pct = ((current - prev) / prev * 100) if prev else 0
                prices.append(current)
                changes.append(change_pct)
                components.append({
                    'symbol': symbol,
                    'name': WATER_DATA.get(symbol, {}).get('name', symbol),
                    'price': current,
                    'changePercent': change_pct
                })

            except Exception as e:
                continue

        if not prices:
            return jsonify({'error': 'Aucune donnée eau'}), 404

        avg_change = np.mean(changes)
        avg_price = np.mean(prices)

        best = max(components, key=lambda x: x['changePercent']) if components else None
        worst = min(components, key=lambda x: x['changePercent']) if components else None

        return jsonify({
            'index': 'WATER',
            'name': 'Indice Synthétique Eau',
            'value': avg_price,
            'changePercent': avg_change,
            'change': avg_price * avg_change / 100 if avg_change != 0 else 0,
            'components': len(prices),
            'components_detail': components,
            'best_performer': best,
            'worst_performer': worst,
            'lastUpdate': datetime.now(US_TIMEZONE).isoformat()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/water-insights/<symbol>')
def get_water_insights(symbol):
    try:
        cached = get_cached(f"water_insights_{symbol}")
        if cached:
            return jsonify(cached)

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='3mo')

        if hist.empty or len(hist) < 30:
            return jsonify({'error': 'Pas assez de données'}), 404

        close = hist['Close'].values
        high = hist['High'].values
        low = hist['Low'].values
        current = safe_float(close[-1])

        returns = np.diff(close) / close[:-1]
        vol = safe_float(np.std(returns) * np.sqrt(252) * 100) if len(returns) > 0 else 0

        support = safe_float(np.percentile(low[-30:], 20)) if len(low) >= 30 else safe_float(min(low))
        resistance = safe_float(np.percentile(high[-30:], 80)) if len(high) >= 30 else safe_float(max(high))

        momentum = safe_float((close[-1] - close[-20]) / close[-20] * 100) if len(close) >= 20 else 0

        try:
            from sklearn.linear_model import LinearRegression
            from sklearn.preprocessing import PolynomialFeatures
            from sklearn.pipeline import make_pipeline
            x = np.arange(len(close)).reshape(-1, 1)
            y = close.reshape(-1, 1)
            model = make_pipeline(PolynomialFeatures(2), LinearRegression())
            model.fit(x, y)
            future = np.arange(len(close), len(close) + 5).reshape(-1, 1)
            predictions = model.predict(future).flatten()
            predictions = [safe_float(p) for p in predictions]
        except:
            predictions = [current] * 5

        rsi = 50
        if len(returns) >= 14:
            gains = [r for r in returns[-14:] if r > 0]
            losses = [abs(r) for r in returns[-14:] if r < 0]
            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0
            if avg_loss > 0:
                rsi = 100 - (100 / (1 + avg_gain / avg_loss))

        signals = []
        if rsi > 70:
            signals.append({'type': 'sell', 'indicator': 'RSI', 'value': f'{rsi:.1f}', 'message': 'Surachat'})
        elif rsi < 30:
            signals.append({'type': 'buy', 'indicator': 'RSI', 'value': f'{rsi:.1f}', 'message': 'Survente'})

        if current > 0 and support > 0 and (current - support) / current < 0.015:
            signals.append({'type': 'buy', 'indicator': 'Support', 'value': f'{support:.2f}', 'message': 'Proche support'})

        if current > 0 and resistance > 0 and (resistance - current) / current < 0.015:
            signals.append({'type': 'sell', 'indicator': 'Résistance', 'value': f'{resistance:.2f}', 'message': 'Proche résistance'})

        if signals:
            buy_count = sum(1 for s in signals if s['type'] == 'buy')
            sell_count = sum(1 for s in signals if s['type'] == 'sell')
            if buy_count > sell_count:
                rec = 'ACHAT'
                conf = min(90, 50 + buy_count * 15)
            elif sell_count > buy_count:
                rec = 'VENTE'
                conf = min(90, 50 + sell_count * 15)
            else:
                rec = 'NEUTRE'
                conf = 50
        else:
            rec = 'NEUTRE'
            conf = 50

        result = {
            'current_price': current,
            'volatility': vol,
            'momentum': momentum,
            'supports': [support],
            'resistances': [resistance],
            'predictions': predictions,
            'signals': signals,
            'recommendation': rec,
            'confidence': conf,
            'stop_loss': safe_float(current * 0.975),
            'take_profit': safe_float(current * 1.05),
            'rsi': rsi,
            'macd': 0
        }

        set_cached(f"water_insights_{symbol}", result)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Erreur insights water {symbol}: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# ROUTE PRINCIPALE
# ============================================================

@app.route('/')
def index():
    return render_template('water.html')

# ============================================================
# LANCEMENT
# ============================================================

if __name__ == '__main__':
    os.makedirs('templates_water', exist_ok=True)
    os.makedirs('static_water/js', exist_ok=True)

    print("=" * 70)
    print("🌊 WATER TRADER - Marché de l'Eau")
    print("=" * 70)
    print("🌐 http://localhost:5006")
    print("=" * 70)
    print("📈 Actifs disponibles:")
    for sym, info in WATER_DATA.items():
        print(f"   {sym} - {info['name']} ({info['exchange']})")
    print("=" * 70)
    print("📁 Dossiers:")
    print(f"   Templates: {os.path.abspath('templates_water')}")
    print(f"   Static: {os.path.abspath('static_water')}")
    print("=" * 70)

    app.run(host='0.0.0.0', port=5006, debug=True)
