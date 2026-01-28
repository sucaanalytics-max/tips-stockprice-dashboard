import { createClient } from '@supabase/supabase-js';

// IMPORTANT: Replace with your actual Supabase key
const SUPABASE_URL = 'https://bfafqccvzboyfjewzvhk.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJmYWZxY2N2emJveWZqZXd6dmhrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzc1MjYxNzAsImV4cCI6MjA1MzEwMjE3MH0.0EYg4KZP_rrABx0zk6xECZAh-JWG_4qJy5nJWqYOQhU';

const SYMBOL = 'TIPSMUSIC';

async function fetchHistoricalData(startDate, endDate) {
    const symbol = `${SYMBOL}.NS`;
    const start = Math.floor(new Date(startDate).getTime() / 1000);
    const end = Math.floor(new Date(endDate).getTime() / 1000);
    
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?period1=${start}&period2=${end}&interval=1d`;
    
    console.log(`Fetching data from Yahoo Finance for ${startDate} to ${endDate}...`);
    
    try {
        const response = await fetch(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        const result = data.chart?.result?.[0];
        
        if (!result) {
            throw new Error('No data returned from Yahoo Finance');
        }
        
        const timestamps = result.timestamp;
        const quotes = result.indicators?.quote?.[0];
        
        if (!timestamps || !quotes) {
            throw new Error('Invalid data structure');
        }
        
        const historicalData = [];
        
        for (let i = 0; i < timestamps.length; i++) {
            const date = new Date(timestamps[i] * 1000).toISOString().split('T')[0];
            
            // Skip weekends (Yahoo sometimes includes them with null values)
            if (quotes.close[i] === null || quotes.close[i] === 0) {
                continue;
            }
            
            historicalData.push({
                symbol: SYMBOL,
                date: date,
                open: quotes.open[i] || quotes.close[i],
                high: quotes.high[i] || quotes.close[i],
                low: quotes.low[i] || quotes.close[i],
                close: quotes.close[i],
                volume: quotes.volume[i] || 0
            });
        }
        
        return historicalData;
        
    } catch (error) {
        console.error('❌ Error fetching historical data:', error);
        return [];
    }
}

async function backfillData() {
    console.log('🚀 Starting backfill process...\n');
    
    const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
    
    // Backfill from January 9 to today
    const startDate = '2026-01-09';
    const endDate = new Date().toISOString().split('T')[0];
    
    console.log(`📅 Date range: ${startDate} to ${endDate}\n`);
    
    const historicalData = await fetchHistoricalData(startDate, endDate);
    
    if (historicalData.length === 0) {
        console.log('❌ No data fetched. Exiting.');
        return;
    }
    
    console.log(`\n✅ Fetched ${historicalData.length} trading days\n`);
    console.log('📝 Inserting into Supabase...\n');
    
    let successCount = 0;
    let errorCount = 0;
    
    for (const record of historicalData) {
        try {
            const { error } = await supabase
                .from('stock_prices')
                .upsert(record, { 
                    onConflict: 'symbol,date',
                    ignoreDuplicates: false 
                });
            
            if (error) {
                console.error(`❌ ${record.date}: ${error.message}`);
                errorCount++;
            } else {
                console.log(`✅ ${record.date}: ₹${record.close.toFixed(2)} (Vol: ${record.volume.toLocaleString()})`);
                successCount++;
            }
            
            // Small delay to avoid rate limiting
            await new Promise(resolve => setTimeout(resolve, 100));
            
        } catch (err) {
            console.error(`❌ ${record.date}: ${err.message}`);
            errorCount++;
        }
    }
    
    console.log('\n' + '='.repeat(60));
    console.log(`📊 Backfill Summary:`);
    console.log(`   ✅ Success: ${successCount} records`);
    console.log(`   ❌ Errors: ${errorCount} records`);
    console.log('='.repeat(60));
    console.log('\n✨ Backfill complete!\n');
}

// Run the backfill
backfillData().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
});
