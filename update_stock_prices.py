"""
Daily Stock Price Updater for Tips Music
Fetches latest stock price from Yahoo Finance and updates Supabase
Run daily at 6:30 PM IST (after NSE market close at 3:30 PM)
"""

import yfinance as yf
import requests
from datetime import datetime, timedelta
import os
import time
import sys

# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://bfafqccvzboyfjewzvhk.supabase.co')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')  # Use service_role key, not anon
STOCK_SYMBOL = 'TIPSMUSIC.NS'  # Yahoo Finance symbol for Tips Music NSE
COMPANY_NAME = 'Tips Music Ltd'

# ============================================================
# FETCH LATEST STOCK PRICE
# ============================================================

def fetch_latest_stock_price(days_back=10):
    """
    Fetch last N days of stock data to ensure we don't miss any trading days
    Yahoo Finance sometimes has delays, so we fetch last 10 days and update all
    """
    print(f"📈 Fetching {COMPANY_NAME} stock data from Yahoo Finance...")
    print(f"   Symbol: {STOCK_SYMBOL}")
    
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Fetch data
        ticker = yf.Ticker(STOCK_SYMBOL)
        df = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            interval='1d'
        )
        
        if df.empty:
            print("⚠️  No stock data returned from Yahoo Finance")
            return []
        
        # Process data
        df = df.reset_index()
        
        # Handle both 'Date' and 'Datetime' column names
        if 'Datetime' in df.columns:
            df = df.rename(columns={'Datetime': 'Date'})
        
        df = df.rename(columns={
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        
        # Keep only required columns
        df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
        
        # Add metadata
        df['symbol'] = 'TIPSMUSIC'
        df['data_source'] = 'yahoo_finance'
        
        # Convert date to date only (remove time)
        df['date'] = df['date'].dt.date
        
        # Remove rows with zero/null prices
        df = df[df['close'] > 0]
        
        # Convert to list of dicts
        records = df.to_dict('records')
        
        print(f"✅ Fetched {len(records)} trading days")
        print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
        
        if len(records) > 0:
            latest = records[-1]
            print(f"   Latest price: ₹{latest['close']:.2f} on {latest['date']}")
        
        return records
    
    except Exception as e:
        print(f"❌ Error fetching stock data: {e}")
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
        'Prefer': 'resolution=merge-duplicates'  # Upsert: update if exists, insert if new
    }
    
    print(f"\n💾 Updating Supabase with {len(records)} records...")
    
    # Convert date objects to strings for JSON serialization
    for record in records:
        if hasattr(record['date'], 'isoformat'):
            record['date'] = record['date'].isoformat()
        else:
            record['date'] = str(record['date'])
    
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
            
            time.sleep(0.5)  # Rate limiting
        
        except Exception as e:
            print(f"   ❌ Batch {i//batch_size + 1} error: {e}")
            continue
    
    print(f"\n✅ Successfully updated {total_updated}/{len(records)} records in Supabase")
    return total_updated

# ============================================================
# VERIFY UPDATE IN SUPABASE
# ============================================================

def verify_latest_data():
    """
    Verify that the latest data was successfully written to Supabase
    """
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
            else:
                print("⚠️  No records found in Supabase")
        else:
            print(f"⚠️  Could not verify: HTTP {response.status_code}")
    
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
    
    # Fetch latest stock prices (last 10 days to catch up on any missed days)
    records = fetch_latest_stock_price(days_back=10)
    
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
            
            # Verify the update
            verify_latest_data()
            
            print("📌 Next steps:")
            print("   1. Verify data in Supabase → stock_prices table")
            print("   2. Dashboard will auto-refresh with new data")
        else:
            print("\n❌ Update failed - no records were updated")
            sys.exit(1)
    else:
        print("\n⚠️  No stock data fetched - possible market holiday or API issue")
        # Check if today is a weekend
        today = datetime.now().weekday()
        if today >= 5:  # Saturday=5, Sunday=6
            print("   (This is expected on weekends)")
        else:
            print("   (Check if NSE is open today)")
    
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()
