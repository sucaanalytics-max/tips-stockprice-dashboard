"""
Daily Stock Price Updater for Tips Music
Fetches latest stock price from Yahoo Finance and updates Supabase
Run daily at 6:30 PM IST (after market close at 3:30 PM)
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

# FIXED: Use BSE symbol instead of NSE (Yahoo Finance NSE feed is broken)
STOCK_SYMBOL = 'TIPSMUSIC.BO'  # BSE (Bombay Stock Exchange)
# Alternative: 'TIPSMUSIC.NS' for NSE (National Stock Exchange) - currently broken

COMPANY_NAME = 'Tips Music Ltd'
DB_SYMBOL = 'TIPSMUSIC'  # Symbol stored in database

# ============================================================
# FETCH LATEST STOCK PRICE
# ============================================================

def fetch_latest_stock_price(days_back=10):
    """
    Fetch last N days of stock data to ensure we don't miss any trading days
    Yahoo Finance sometimes has delays, so we fetch last 10 days and update all
    """
    print(f"📈 Fetching {COMPANY_NAME} stock data from Yahoo Finance...")
    print(f"   Symbol: {STOCK_SYMBOL} (BSE)")
    
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        print(f"   Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Fetch data with retry logic
        ticker = yf.Ticker(STOCK_SYMBOL)
        df = ticker.history(
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            interval='1d',
            auto_adjust=True,  # Adjust for splits/dividends
            actions=False      # Don't include dividends/splits columns
        )
        
        if df.empty:
            print("⚠️  No stock data returned from Yahoo Finance")
            print("   Possible reasons:")
            print("   - Market is closed (weekend/holiday)")
            print("   - Yahoo Finance API temporary issue")
            print("   - Trading suspension")
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
        
        # Keep only required columns (case-insensitive check)
        available_cols = [col.lower() for col in df.columns]
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        
        # Map columns (handle case variations)
        col_mapping = {}
        for req_col in required_cols:
            for idx, col in enumerate(df.columns):
                if col.lower() == req_col:
                    col_mapping[col] = req_col
                    break
        
        df = df.rename(columns=col_mapping)
        df = df[required_cols]
        
        # Add metadata
        df['symbol'] = DB_SYMBOL  # Use consistent symbol for database
        df['data_source'] = 'yahoo_finance_bse'
        
        # Convert date to date only (remove time)
        df['date'] = df['date'].dt.date
        
        # Remove rows with zero/null prices
        df = df[df['close'] > 0]
        
        # Remove duplicates (keep latest)
        df = df.drop_duplicates(subset=['date'], keep='last')
        
        # Sort by date
        df = df.sort_values('date')
        
        # Convert to list of dicts
        records = df.to_dict('records')
        
        print(f"✅ Fetched {len(records)} trading days")
        
        if len(records) > 0:
            print(f"   Date range: {records[0]['date']} to {records[-1]['date']}")
            latest = records[-1]
            print(f"   Latest price: ₹{latest['close']:.2f} on {latest['date']}")
            print(f"   Latest volume: {latest['volume']:,}")
        
        return records
    
    except Exception as e:
        print(f"❌ Error fetching stock data: {e}")
        import traceback
        print(traceback.format_exc())
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
        
        # Ensure all numeric values are float (not numpy types)
        for key in ['open', 'high', 'low', 'close']:
            if key in record:
                record[key] = float(record[key])
        
        if 'volume' in record:
            record['volume'] = int(record['volume'])
    
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
                print(f"   Response: {response.text[:300]}")
            
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
    
    url = f"{SUPABASE_URL}/rest/v1/stock_prices?symbol=eq.{DB_SYMBOL}&order=date.desc&limit=3"
    
    headers = {
        'apikey': SUPABASE_SERVICE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                print(f"\n🔍 Latest records in Supabase (last 3 trading days):")
                for i, record in enumerate(data[:3], 1):
                    print(f"   {i}. Date: {record['date']} | Price: ₹{record['close']:.2f} | Volume: {record['volume']:,}")
            else:
                print("⚠️  No records found in Supabase")
        else:
            print(f"⚠️  Could not verify: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"⚠️  Verification error: {e}")

# ============================================================
# BACKFILL HISTORICAL DATA (OPTIONAL)
# ============================================================

def backfill_historical_data(start_date='2023-01-01'):
    """
    One-time backfill of historical data from a specific date
    Usage: Call this manually to fill gaps in historical data
    """
    print(f"\n📅 BACKFILL MODE: Fetching data from {start_date} to today...")
    
    end_date = datetime.now()
    start = datetime.strptime(start_date, '%Y-%m-%d')
    days_back = (end_date - start).days
    
    print(f"   Total days to fetch: {days_back}")
    
    records = fetch_latest_stock_price(days_back=days_back)
    
    if records:
        print(f"   Found {len(records)} trading days")
        updated = update_supabase(records)
        print(f"   Backfilled {updated} records")
        return updated
    else:
        print("   No data to backfill")
        return 0

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
    
    # Check if backfill mode is requested (via environment variable)
    backfill_mode = os.getenv('BACKFILL_FROM_DATE')
    
    if backfill_mode:
        print("🔄 BACKFILL MODE ENABLED")
        updated = backfill_historical_data(start_date=backfill_mode)
        if updated > 0:
            verify_latest_data()
        sys.exit(0)
    
    # Normal daily update
    # Fetch last 10 days to catch up on any missed days
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
            
            print("\n📌 Next steps:")
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
            print("   (Check if BSE/NSE is open today)")
        
        # Don't fail on weekends/holidays
        print("\n   Skipping update - no error")
    
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    main()
