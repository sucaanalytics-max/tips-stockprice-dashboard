"""
Daily Stock Price Updater for Tips Music
Fetches latest stock price from multiple sources and updates Supabase
Priority: Screener.in → MoneyControl → NSE (fallback)
"""

import requests
from datetime import datetime, timedelta
import os
import time
import json
import sys
from bs4 import BeautifulSoup

# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://bfafqccvzboyfjewzvhk.supabase.co')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
STOCK_SYMBOL = 'TIPSMUSIC'
COMPANY_NAME = 'Tips Music Ltd'

# ============================================================
# METHOD 1: SCREENER.IN (BEST - Historical Data Available)
# ============================================================

def fetch_from_screener(days_back=30):
    """
    Fetch from Screener.in - most reliable source for Indian stocks
    URL: https://www.screener.in/company/TIPSMUSIC/
    """
    print(f"📈 Fetching {COMPANY_NAME} data from Screener.in...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        # Screener.in stock page
        url = 'https://www.screener.in/company/TIPSMUSIC/'
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"   ❌ Screener.in returned status: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find current stock price
        price_element = soup.find('span', class_='number')
        if not price_element:
            print("   ❌ Could not find price on Screener.in")
            return []
        
        current_price = float(price_element.text.strip().replace(',', ''))
        today = datetime.now().date()
        
        print(f"✅ Fetched current price from Screener.in")
        print(f"   Current price: ₹{current_price:.2f}")
        print(f"   Date: {today}")
        
        # Create record for today
        record = {
            'date': today.isoformat(),
            'open': current_price,  # Screener doesn't provide OHLC, use close for all
            'high': current_price,
            'low': current_price,
            'close': current_price,
            'volume': 0,  # Not available from Screener
            'symbol': 'TIPSMUSIC',
            'data_source': 'screener_in'
        }
        
        return [record]
    
    except Exception as e:
        print(f"❌ Screener.in error: {e}")
        return []

# ============================================================
# METHOD 2: MONEYCONTROL (Backup - Full OHLCV Data)
# ============================================================

def fetch_from_moneycontrol():
    """
    Fetch from MoneyControl - has detailed OHLCV data
    URL: https://www.moneycontrol.com/india/stockpricequote/film-production-distributionentertainment/tipsmusic/TI25
    """
    print(f"📈 Fetching {COMPANY_NAME} data from MoneyControl...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        # MoneyControl stock page
        url = 'https://www.moneycontrol.com/india/stockpricequote/film-production-distributionentertainment/tipsmusic/TI25'
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"   ❌ MoneyControl returned status: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find price data in the page
        price_div = soup.find('div', class_='pcstkspr')
        if not price_div:
            print("   ❌ Could not find price section")
            return []
        
        # Extract current price
        current_price_elem = price_div.find('span', class_='nseprice')
        if not current_price_elem:
            print("   ❌ Could not find current price")
            return []
        
        current_price = float(current_price_elem.text.strip().replace(',', ''))
        
        # Try to get OHLC from the data section
        data_div = soup.find('div', class_='oview_table')
        
        open_price = current_price
        high_price = current_price
        low_price = current_price
        volume = 0
        
        if data_div:
            # Find Open, High, Low, Volume
            for row in data_div.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].text.strip()
                    value_text = cells[1].text.strip().replace(',', '')
                    
                    try:
                        if 'Open' in label:
                            open_price = float(value_text)
                        elif 'High' in label:
                            high_price = float(value_text)
                        elif 'Low' in label:
                            low_price = float(value_text)
                        elif 'Volume' in label:
                            volume = int(value_text)
                    except:
                        pass
        
        today = datetime.now().date()
        
        print(f"✅ Fetched data from MoneyControl")
        print(f"   O: ₹{open_price:.2f}, H: ₹{high_price:.2f}, L: ₹{low_price:.2f}, C: ₹{current_price:.2f}")
        print(f"   Volume: {volume:,}")
        
        record = {
            'date': today.isoformat(),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': current_price,
            'volume': volume,
            'symbol': 'TIPSMUSIC',
            'data_source': 'moneycontrol'
        }
        
        return [record]
    
    except Exception as e:
        print(f"❌ MoneyControl error: {e}")
        return []

# ============================================================
# METHOD 3: GROWW (Backup)
# ============================================================

def fetch_from_groww():
    """
    Fetch from Groww - simple and fast
    URL: https://groww.in/stocks/tips-industries-ltd
    """
    print(f"📈 Fetching {COMPANY_NAME} data from Groww...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    try:
        url = 'https://groww.in/v1/api/stocks_data/v1/accord/search_slug/tips-industries-ltd'
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"   ❌ Groww returned status: {response.status_code}")
            return []
        
        data = response.json()
        
        if 'livePrice' in data:
            current_price = float(data['livePrice'])
            today = datetime.now().date()
            
            print(f"✅ Fetched current price from Groww")
            print(f"   Current price: ₹{current_price:.2f}")
            
            record = {
                'date': today.isoformat(),
                'open': current_price,
                'high': current_price,
                'low': current_price,
                'close': current_price,
                'volume': 0,
                'symbol': 'TIPSMUSIC',
                'data_source': 'groww'
            }
            
            return [record]
        
        print("   ❌ No price data found in Groww response")
        return []
    
    except Exception as e:
        print(f"❌ Groww error: {e}")
        return []

# ============================================================
# MAIN FETCH FUNCTION (Try Multiple Sources)
# ============================================================

def fetch_stock_data():
    """
    Try multiple sources in order of preference:
    1. MoneyControl (best OHLCV data)
    2. Screener.in (reliable)
    3. Groww (fastest)
    """
    print("=" * 70)
    print("🔍 TRYING MULTIPLE DATA SOURCES...")
    print("=" * 70)
    
    # Try MoneyControl first (has OHLCV)
    records = fetch_from_moneycontrol()
    if records:
        return records
    
    print("\n⚠️  MoneyControl failed, trying Screener.in...\n")
    time.sleep(1)
    
    # Try Screener.in
    records = fetch_from_screener()
    if records:
        return records
    
    print("\n⚠️  Screener.in failed, trying Groww...\n")
    time.sleep(1)
    
    # Try Groww
    records = fetch_from_groww()
    if records:
        return records
    
    print("\n❌ All data sources failed!")
    return []

# ============================================================
# UPDATE SUPABASE
# ============================================================

def update_supabase(records):
    """Insert/update stock prices in Supabase"""
    if not records:
        print("⚠️  No records to update")
        return 0
    
    if not SUPABASE_SERVICE_KEY:
        print("❌ SUPABASE_SERVICE_KEY not set in environment variables")
        return 0
    
    url = f"{SUPABASE_URL}/rest/v1/stock_prices"
    
    headers = {
        'apikey': SUPABASE_SERVICE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates'
    }
    
    print(f"\n💾 Updating Supabase with {len(records)} records...")
    
    try:
        response = requests.post(url, json=records, headers=headers, timeout=30)
        
        if response.status_code in [200, 201, 204]:
            print(f"   ✅ Successfully updated {len(records)} records")
            return len(records)
        else:
            print(f"   ❌ Update failed: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return 0
    
    except Exception as e:
        print(f"   ❌ Update error: {e}")
        return 0

# ============================================================
# VERIFY UPDATE
# ============================================================

def verify_latest_data():
    """Verify latest data in Supabase"""
    if not SUPABASE_SERVICE_KEY:
        return
    
    url = f"{SUPABASE_URL}/rest/v1/stock_prices?symbol=eq.TIPSMUSIC&order=date.desc&limit=1"
    
    headers = {
        'apikey': SUPABASE_SERVICE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                latest = data[0]
                print(f"\n🔍 Latest record in Supabase:")
                print(f"   Date: {latest['date']}")
                print(f"   Price: ₹{latest['close']:.2f}")
                print(f"   Source: {latest['data_source']}")
    
    except Exception as e:
        print(f"⚠️  Verification error: {e}")

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    print("=" * 70)
    print(f"📊 TIPS MUSIC STOCK PRICE DAILY UPDATE")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    # Check environment
    if not SUPABASE_URL:
        print("❌ SUPABASE_URL not set!")
        sys.exit(1)
    
    if not SUPABASE_SERVICE_KEY:
        print("❌ SUPABASE_SERVICE_KEY not set!")
        sys.exit(1)
    
    # Fetch stock data (tries multiple sources)
    records = fetch_stock_data()
    
    if records:
        # Update Supabase
        updated = update_supabase(records)
        
        if updated > 0:
            print("\n" + "=" * 70)
            print("✅ DAILY UPDATE COMPLETE!")
            print("=" * 70)
            print(f"Records updated: {updated}")
            print(f"Latest price: ₹{records[-1]['close']:.2f}")
            print(f"Data source: {records[-1]['data_source']}")
            
            verify_latest_data()
            
            print("\n📌 Dashboard will auto-refresh with new data")
        else:
            print("\n❌ Update failed")
            sys.exit(1)
    else:
        print("\n❌ No stock data fetched from any source")
        today = datetime.now().weekday()
        if today >= 5:
            print("   (Market closed - weekend)")
        else:
            print("   (Check if NSE is open today)")
        
        # Don't fail on weekends
        if today < 5:
            sys.exit(1)
    
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()
