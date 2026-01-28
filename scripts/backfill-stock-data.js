import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://bfafqccvzboyfjewzvhk.supabase.co';
const SUPABASE_KEY = 'YOUR_SUPABASE_KEY'; // Replace with your key

const SYMBOL = 'TIPSMUSIC';

async function fetchHistoricalData(startDate, endDate) {
    const symbol = `${SYMBOL}.NS`;
    const start = Math.floor(new Date(startDate).getTime() / 1000);
    const end = Math.floor(new Date(endDate).getTime() / 1000);
    
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?period1=${start}&period2=${end}&interval=1d`;
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        const result = data.chart?.result?.[0];
        if (!result) throw new Error('No data returned');
        
        const timestamps = result.timestamp;
        const quotes = result.indicators?.quote?.[0];
        
        const historicalData = [];
        
        for (let i = 0; i < timestamps.length; i++) {
            const date = new Date(timestamps[i] * 1000).toISOString().split('T')[0];
            historicalData.push({
                symbol: SYMBOL,
                date: date,
                open: quotes.open[i] || 0,
                high: quotes.high[i] || 0,
                low: quotes.low[i] || 0,
                close: quotes.close[i] || 0,
                volume: quotes.volume[i] || 0
            });
        }
        
        return historicalData;
    } catch (error) {
        console.error('Error fetching historical data:', error);
        return [];
    }
}

async function backfillData() {
    console.log('Starting backfill...');
    
    const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
    
    // Fetch data from 08-01-2026 to today
    const startDate = '2026-01-08';
    const endDate = new Date().toISOString().split('T')[0];
    
    console.log(`Fetching data from ${startDate} to ${endDate}...`);
    
    const historicalData = await fetchHistoricalData(startDate, endDate);
    
    if (historicalData.length === 0) {
        console.log('❌ No data fetched');
        return;
    }
    
    console.log(`✅ Fetched ${historicalData.length} records`);
    
    // Insert/update each record
    for (const record of historicalData) {
        const { error } = await supabase
            .from('stock_prices')
            .upsert(record, { onConflict: 'symbol,date' });
        
        if (error) {
            console.error(`❌ Error inserting ${record.date}:`, error);
        } else {
            console.log(`✅ Inserted/Updated ${record.date}: ₹${record.close}`);
        }
    }
    
    console.log('Backfill complete!');
}

backfillData();
