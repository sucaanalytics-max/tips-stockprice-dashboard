import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://bfafqccvzboyfjewzvhk.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_KEY;

// CORRECT NSE SYMBOL (as of Sep 30, 2024)
const CORRECT_SYMBOL = 'TIPSMUSIC';

export default async function handler(req, res) {
    try {
        console.log('Starting stock price update...');
        
        // Fetch stock price from NSE
        const stockPrice = await fetchNSEPrice(CORRECT_SYMBOL);
        
        if (!stockPrice) {
            throw new Error('Failed to fetch stock price');
        }
        
        // Initialize Supabase
        const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
        
        const today = new Date().toISOString().split('T')[0];
        
        // Check if today's price already exists
        const { data: existing } = await supabase
            .from('stock_prices')
            .select('*')
            .eq('symbol', CORRECT_SYMBOL)
            .eq('date', today)
            .single();
        
        if (existing) {
            // Update existing record
            const { error } = await supabase
                .from('stock_prices')
                .update({
                    open: stockPrice.open,
                    high: stockPrice.high,
                    low: stockPrice.low,
                    close: stockPrice.close,
                    volume: stockPrice.volume,
                    updated_at: new Date().toISOString()
                })
                .eq('symbol', CORRECT_SYMBOL)
                .eq('date', today);
            
            if (error) throw error;
            console.log(`✅ Updated stock price for ${today}`);
        } else {
            // Insert new record
            const { error } = await supabase
                .from('stock_prices')
                .insert([{
                    symbol: CORRECT_SYMBOL,
                    date: today,
                    open: stockPrice.open,
                    high: stockPrice.high,
                    low: stockPrice.low,
                    close: stockPrice.close,
                    volume: stockPrice.volume
                }]);
            
            if (error) throw error;
            console.log(`✅ Inserted stock price for ${today}`);
        }
        
        return res.status(200).json({
            success: true,
            message: 'Stock price updated successfully',
            symbol: CORRECT_SYMBOL,
            date: today,
            price: stockPrice.close
        });
        
    } catch (error) {
        console.error('Error updating stock price:', error);
        return res.status(500).json({
            success: false,
            error: error.message
        });
    }
}

async function fetchNSEPrice(symbol) {
    try {
        // Option 1: NSE API (may require headers)
        const url = `https://www.nseindia.com/api/quote-equity?symbol=${symbol}`;
        
        const response = await fetch(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            console.log('NSE API failed, using fallback...');
            return await fetchFallbackPrice(symbol);
        }
        
        const data = await response.json();
        
        return {
            open: data.priceInfo?.open || 0,
            high: data.priceInfo?.intraDayHighLow?.max || 0,
            low: data.priceInfo?.intraDayHighLow?.min || 0,
            close: data.priceInfo?.lastPrice || 0,
            volume: data.priceInfo?.totalTradedVolume || 0
        };
        
    } catch (error) {
        console.error('Error fetching NSE price:', error);
        return await fetchFallbackPrice(symbol);
    }
}

async function fetchFallbackPrice(symbol) {
    // Fallback: Use Yahoo Finance or other provider
    try {
        const yahooSymbol = `${symbol}.NS`; // NSE suffix for Yahoo
        const url = `https://query1.finance.yahoo.com/v8/finance/chart/${yahooSymbol}?interval=1d&range=1d`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        const quote = data.chart?.result?.[0];
        if (!quote) throw new Error('No data from fallback');
        
        const meta = quote.meta;
        const indicators = quote.indicators?.quote?.[0];
        
        return {
            open: indicators?.open?.[0] || meta.previousClose,
            high: indicators?.high?.[0] || meta.regularMarketPrice,
            low: indicators?.low?.[0] || meta.regularMarketPrice,
            close: meta.regularMarketPrice || 0,
            volume: indicators?.volume?.[0] || 0
        };
        
    } catch (error) {
        console.error('Fallback also failed:', error);
        return null;
    }
}
