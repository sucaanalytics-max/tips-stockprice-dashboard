import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://bfafqccvzboyfjewzvhk.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_KEY || 'YOUR_SUPABASE_ANON_KEY'; // Replace if needed

const SYMBOL = 'TIPSMUSIC';

export default async function handler(req, res) {
    // Only allow GET requests for security
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        console.log('Starting backfill process...');
        
        const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
        
        // Get date range from query params or use defaults
        const startDate = req.query.start || '2026-01-09';
        const endDate = req.query.end || new Date().toISOString().split('T')[0];
        
        console.log(`Fetching data from ${startDate} to ${endDate}...`);
        
        // Fetch historical data from Yahoo Finance
        const historicalData = await fetchHistoricalData(startDate, endDate);
        
        if (historicalData.length === 0) {
            return res.status(404).json({
                success: false,
                message: 'No historical data found',
                startDate,
                endDate
            });
        }
        
        console.log(`Fetched ${historicalData.length} records`);
        
        // Insert/update records
        const results = {
            success: 0,
            failed: 0,
            records: []
        };
        
        for (const record of historicalData) {
            try {
                const { error } = await supabase
                    .from('stock_prices')
                    .upsert(record, { 
                        onConflict: 'symbol,date',
                        ignoreDuplicates: false 
                    });
                
                if (error) throw error;
                
                results.success++;
                results.records.push({
                    date: record.date,
                    close: record.close,
                    status: 'inserted/updated'
                });
                
                console.log(`✅ ${record.date}: ₹${record.close}`);
            } catch (error) {
                results.failed++;
                results.records.push({
                    date: record.date,
                    status: 'failed',
                    error: error.message
                });
                console.error(`❌ ${record.date}:`, error);
            }
        }
        
        return res.status(200).json({
            success: true,
            message: 'Backfill completed',
            symbol: SYMBOL,
            dateRange: { start: startDate, end: endDate },
            summary: {
                total: historicalData.length,
                successful: results.success,
                failed: results.failed
            },
            records: results.records
        });
        
    } catch (error) {
        console.error('Backfill error:', error);
        return res.status(500).json({
            success: false,
            error: error.message
        });
    }
}

async function fetchHistoricalData(startDate, endDate) {
    const symbol = `${SYMBOL}.NS`; // NSE suffix for Yahoo Finance
    const start = Math.floor(new Date(startDate).getTime() / 1000);
    const end = Math.floor(new Date(endDate).getTime() / 1000);
    
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?period1=${start}&period2=${end}&interval=1d`;
    
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
            throw new Error('No data in response');
        }
        
        const timestamps = result.timestamp || [];
        const quotes = result.indicators?.quote?.[0] || {};
        
        const historicalData = [];
        
        for (let i = 0; i < timestamps.length; i++) {
            const date = new Date(timestamps[i] * 1000).toISOString().split('T')[0];
            
            // Only add if we have valid price data
            if (quotes.close && quotes.close[i]) {
                historicalData.push({
                    symbol: SYMBOL,
                    date: date,
                    open: quotes.open?.[i] || 0,
                    high: quotes.high?.[i] || 0,
                    low: quotes.low?.[i] || 0,
                    close: quotes.close?.[i] || 0,
                    volume: quotes.volume?.[i] || 0
                });
            }
        }
        
        return historicalData;
        
    } catch (error) {
        console.error('Error fetching from Yahoo Finance:', error);
        throw error;
    }
}
