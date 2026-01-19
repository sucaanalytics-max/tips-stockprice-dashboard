"""
Daily Stock Price Updater for Tips Music
Fetches latest stock price from NSE India website and updates Supabase
Run daily at 6:30 PM IST (after NSE market close at 3:30 PM)
"""

import requests
from datetime import datetime, timedelta
import os
import time
import json
import sys

# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://bfafqccvzboyfjewzvhk.supabase.co')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
STOCK_SYMBOL = 'TIPSMUSIC'  # NSE symbol
COMPANY_NAME = 'Tips Music Ltd'

# ============================================================
# FETCH FROM NSE INDIA
# ============================================================

def fetch_nse_stock_data(symbol='TIPSMUSIC', days_back=10):
    """
    Fetch stock data from NSE India website
    NSE provides free historical data through their website
    """
    print(f"📈 Fetching {COMPANY_NAME} stock data from NSE India...")
    print(f"   Symbol: {symbol}")
    
    # NSE requires proper headers to prevent blocking
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://www.nseindia.com/',
    }
    
    # Create session to maintain cookies
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        # Step 1: Visit homepage to get cookies
        print("   → Initializing NSE session...")
        home_url = 'https://www.nseindia.com/'
        session.get(home_url, timeout=10)
        time.sleep(1)  # Small delay
        
        # Step 2: Fetch historical data
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Format dates for NSE API (DD-MM-YYYY)
        from_date = start_date.strftime('%d-%m-%Y')
        to_date = end_date.strftime('%d-%m-%Y')
        
        print(f"   → Fetching data from {from_date} to {to_date}...")
        
        # NSE Historical Data API endpoint
        api_url = f'https://www.nseindia.com/api/historical/cm/equity?symbol={symbol}&series=[%22EQ%22]&from={from_date}&to={to_date}'
        
        response = session.get(api_url, timeout=15)
        
        if response.status_code != 200:
            print(f"   ❌ NSE API returned status: {response.status_code}")
            return []
        
        data = response.json()
        
        if not data or 'data' not in data or not data['data']:
            print("   ⚠️  No data returned from NSE")
            return []
        
        # Parse NSE response
        records = []
        for item in data['data']:
            # NSE date format: "17-Jan-2026"
            date_str = item.get('CH_TIMESTAMP', '')
            if not date_str:
                continue
            
            # Parse date
            date_obj = datetime.strptime(date_str, '%d-%b-%Y').date()
            
            # Extract OHLCV data
            record = {
                'date': date_obj.isoformat(),
                'open': float(item.get('CH_OPENING_PRICE', 0)),
                'high': float(item.get('CH_TRADE_HIGH_PRICE', 0)),
                'low': float(item.get('CH_TRADE_LOW_PRICE', 0)),
                'close': float(item.get('CH_CLOSING_PRICE', 0)),
                'volume': int(item.get('CH_TOT_TRADED_QTY', 0)),
                'symbol': 'TIPSMUSIC',
                'data_source': 'nse_india'
            }
            
            # Only include records with valid prices
            if record['close'] > 0:
                records.append(record)
        
        # Sort by date (oldest to newest)
        records.sort(key=lambda x: x['date'])
        
        print(f"✅ Fetched {len(records)} trading days from NSE India")
        if records:
            print(f"   Date range: {records[0]['date']} to {records[-1]['date']}")
            print(f"   Latest price: ₹{records[-1]['close']:.2f} on {records[-1]['date']}")
        
        return records
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error fetching NSE data: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing NSE response: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return []

# ============================================================
# UPDATE SUPABASE
# ============================================================

def update_supabase(records):
    """
    Insert/update stock prices in Supabase using REST API
    Uses 'upsert' to handle duplicates (update if exists, insert if new)
    """
    if not records:
        print("⚠️  No records to update")
        return 0
    
    if not SUPABASE_SERVICE_KEY:
        print("❌ SUPABASE_SERVICE_KEY not set in environment variables")
        print("   Add it to GitHub Secrets!")
        return 0
    
    url = f"{SUPABASE_URL}/rest/v1/stock_prices"
    
    headers = {
        'apikey': SUPABASE_SERVICE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates'
    }
    
    print(f"\n💾 Updating Supabase with {len(records)} records...")
    
    # Insert in batches
    batch_size = 100
    total_updated = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        
        try:
            response = requests.post(url, json=batch, headers=headers, timeout=30)
            
            if response.status_code in [200, 201, 204]:
                total_updated += len(batch)
                print(f"   ✅ Batch {i//batch_size + 1}: {len(batch)} records updated")
            else:
                print(f"   ❌ Batch {i//batch_size + 1} failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
            
            time.sleep(0.5)
        
        except Exception as e:
            print(f"   ❌ Batch {i//batch_size + 1} error: {e}")
            continue
    
    print(f"\n✅ Successfully updated {total_updated}/{len(records)} records in Supabase")
    return total_updated

# ============================================================
# VERIFY UPDATE
# ============================================================

def verify_latest_data():
    """Verify latest data was successfully written to Supabase"""
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
                print(f"   Volume: {latest['volume']:,}")
                print(f"   Source: {latest['data_source']}")
            else:
                print("⚠️  No records found in Supabase")
    
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
    
    # Check environment variables
    if not SUPABASE_URL:
        print("❌ SUPABASE_URL not set!")
        sys.exit(1)
    
    if not SUPABASE_SERVICE_KEY:
        print("❌ SUPABASE_SERVICE_KEY not set!")
        print("   Add it to GitHub Secrets: Settings → Secrets → Actions")
        sys.exit(1)
    
    # Fetch from NSE India
    records = fetch_nse_stock_data(symbol='TIPSMUSIC', days_back=10)
    
    if records:
        # Update Supabase
        updated = update_supabase(records)
        
        if updated > 0:
            print("\n" + "=" * 70)
            print("✅ DAILY UPDATE COMPLETE!")
            print("=" * 70)
            print(f"Total records updated: {updated}")
            print(f"Latest trading date: {records[-1]['date']}")
            print(f"Latest price: ₹{records[-1]['close']:.2f}")
            print()
            
            # Verify
            verify_latest_data()
            
            print("📌 Next steps:")
            print("   1. Verify data in Supabase → stock_prices table")
            print("   2. Dashboard will auto-refresh with new data")
        else:
            print("\n❌ Update failed - no records were updated")
            sys.exit(1)
    else:
        print("\n⚠️  No stock data fetched - possible market holiday or NSE issue")
        today = datetime.now().weekday()
        if today >= 5:
            print("   (This is expected on weekends)")
        else:
            print("   (Check if NSE is open today)")
    
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()
