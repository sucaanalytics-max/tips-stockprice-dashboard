// api/update-stock-price.js
// Vercel Serverless Function to update TIPS stock price daily

import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

// Multiple stock price data sources
async function fetchStockPrice() {
  const symbol = 'TIPSMUSIC';
  
  // Option 1: Yahoo Finance (Most reliable for NSE stocks)
  try {
    const response = await fetch(
      `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}.NS?interval=1d&range=1d`,
      {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
      }
    );
    
    if (response.ok) {
      const data = await response.json();
      const quote = data.chart.result[0];
      const meta = quote.meta;
      
      return {
        date: new Date().toISOString().split('T')[0],
        open: meta.regularMarketPrice || meta.previousClose,
        high: meta.regularMarketDayHigh || meta.regularMarketPrice,
        low: meta.regularMarketDayLow || meta.regularMarketPrice,
        close: meta.regularMarketPrice,
        volume: meta.regularMarketVolume || 0,
        source: 'yahoo_finance'
      };
    }
  } catch (error) {
    console.error('Yahoo Finance failed:', error);
  }
  
  // Option 2: Alpha Vantage (Fallback)
  if (process.env.ALPHA_VANTAGE_API_KEY) {
    try {
      const response = await fetch(
        `https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=${symbol}.BSE&apikey=${process.env.ALPHA_VANTAGE_API_KEY}`
      );
      
      if (response.ok) {
        const data = await response.json();
        const quote = data['Global Quote'];
        
        if (quote && quote['05. price']) {
          return {
            date: new Date().toISOString().split('T')[0],
            open: parseFloat(quote['02. open']),
            high: parseFloat(quote['03. high']),
            low: parseFloat(quote['04. low']),
            close: parseFloat(quote['05. price']),
            volume: parseInt(quote['06. volume']),
            source: 'alpha_vantage'
          };
        }
      }
    } catch (error) {
      console.error('Alpha Vantage failed:', error);
    }
  }
  
  // Option 3: Twelve Data (Another fallback)
  if (process.env.TWELVE_DATA_API_KEY) {
    try {
      const response = await fetch(
        `https://api.twelvedata.com/quote?symbol=${symbol}&exchange=NSE&apikey=${process.env.TWELVE_DATA_API_KEY}`
      );
      
      if (response.ok) {
        const data = await response.json();
        
        if (data.close) {
          return {
            date: new Date().toISOString().split('T')[0],
            open: parseFloat(data.open),
            high: parseFloat(data.high),
            low: parseFloat(data.low),
            close: parseFloat(data.close),
            volume: parseInt(data.volume),
            source: 'twelve_data'
          };
        }
      }
    } catch (error) {
      console.error('Twelve Data failed:', error);
    }
  }
  
  throw new Error('All stock price sources failed');
}

// Main handler
export default async function handler(req, res) {
  // Verify cron secret for security
  if (req.headers.authorization !== `Bearer ${process.env.CRON_SECRET}`) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  
  try {
    // Check if it's a trading day (Monday-Friday)
    const today = new Date();
    const dayOfWeek = today.getDay();
    if (dayOfWeek === 0 || dayOfWeek === 6) {
      return res.status(200).json({ 
        message: 'Weekend - no trading', 
        skipped: true 
      });
    }
    
    // Fetch current stock price
    const stockData = await fetchStockPrice();
    
    // Check if today's data already exists
    const { data: existing, error: checkError } = await supabase
      .from('stock_prices')
      .select('*')
      .eq('date', stockData.date)
      .single();
    
    if (checkError && checkError.code !== 'PGRST116') {
      throw checkError;
    }
    
    let result;
    
    if (existing) {
      // Update existing record
      const { data, error } = await supabase
        .from('stock_prices')
        .update({
          open: stockData.open,
          high: stockData.high,
          low: stockData.low,
          close: stockData.close,
          volume: stockData.volume,
          source: stockData.source,
          updated_at: new Date().toISOString()
        })
        .eq('date', stockData.date)
        .select();
      
      if (error) throw error;
      result = { updated: data, action: 'updated' };
    } else {
      // Insert new record
      const { data, error } = await supabase
        .from('stock_prices')
        .insert([{
          date: stockData.date,
          open: stockData.open,
          high: stockData.high,
          low: stockData.low,
          close: stockData.close,
          volume: stockData.volume,
          source: stockData.source,
          created_at: new Date().toISOString()
        }])
        .select();
      
      if (error) throw error;
      result = { inserted: data, action: 'inserted' };
    }
    
    // Log success
    console.log('Stock price updated successfully:', result);
    
    return res.status(200).json({
      success: true,
      ...result,
      stockData
    });
    
  } catch (error) {
    console.error('Error updating stock price:', error);
    
    // Log to Supabase for monitoring
    try {
      await supabase
        .from('error_logs')
        .insert([{
          error_type: 'stock_price_update',
          error_message: error.message,
          error_details: JSON.stringify(error),
          created_at: new Date().toISOString()
        }]);
    } catch (logError) {
      console.error('Failed to log error:', logError);
    }
    
    return res.status(500).json({
      success: false,
      error: error.message
    });
  }
}
