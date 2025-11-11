"""
Stock Information Module
Fetches sector, industry, and other stock details using yfinance
"""
import yfinance as yf
import requests
import json
from typing import Dict, Optional, List

def get_ticker_symbol(company_name: str) -> str:
    """
    Try to find a ticker symbol given a company name.
    Uses Yahoo Finance search API.
    """
    try:
        # Clean company name
        clean_name = company_name.strip().replace(" ", "%20")
        
        # Yahoo Finance search endpoint
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={clean_name}&quotesCount=5&enableFuzzyQuery=false"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            quotes = data.get('quotes', [])
            
            # Find the best match
            for quote in quotes:
                symbol = quote.get('symbol', '')
                quote_name = quote.get('longname', '') or quote.get('shortname', '')
                
                # Check if it's a good match
                if symbol and quote_name:
                    # Simple matching logic
                    if company_name.lower() in quote_name.lower() or quote_name.lower() in company_name.lower():
                        return symbol
            
            # If no good match, return first symbol
            if quotes and quotes[0].get('symbol'):
                return quotes[0]['symbol']
                
    except Exception as e:
        print(f"Error searching for ticker: {e}")
    
    # Fallback: try common company-to-ticker mapping
    return get_ticker_from_mapping(company_name)

def get_ticker_from_mapping(company_name: str) -> str:
    """
    Fallback method using common company name to ticker mapping
    """
    # Common mappings for well-known companies
    mapping = {
        'apple': 'AAPL',
        'microsoft': 'MSFT',
        'google': 'GOOGL',
        'alphabet': 'GOOGL',
        'amazon': 'AMZN',
        'tesla': 'TSLA',
        'meta': 'META',
        'facebook': 'META',
        'netflix': 'NFLX',
        'nvidia': 'NVDA',
        'tcs': 'TCS.NS',
        'infosys': 'INFY.NS',
        'reliance': 'RELIANCE.NS',
        'hdfc bank': 'HDFCBANK.NS',
        'hdfc': 'HDFCBANK.NS',
        'icici bank': 'ICICIBANK.NS',
        'icici': 'ICICIBANK.NS',
        'wipro': 'WIPRO.NS',
        'bharti airtel': 'BHARTIARTL.NS',
        'airtel': 'BHARTIARTL.NS',
        'maruti suzuki': 'MARUTI.NS',
        'maruti': 'MARUTI.NS'
    }
    
    name_lower = company_name.lower().strip()
    return mapping.get(name_lower, '')

def get_stock_sector(company_name: str) -> Dict:
    """
    Get comprehensive stock information including sector and industry.
    Returns a dictionary with ticker, sector, industry, and other details.
    """
    if not company_name or not company_name.strip():
        return {
            "ticker": "",
            "sector": "Unknown",
            "industry": "Unknown",
            "market_cap": 0,
            "country": "Unknown",
            "website": "",
            "business_summary": "",
            "employee_count": 0
        }
    
    # Get ticker symbol
    ticker_symbol = get_ticker_symbol(company_name)
    
    if not ticker_symbol:
        return {
            "ticker": "",
            "sector": "Unknown",
            "industry": "Unknown",
            "market_cap": 0,
            "country": "Unknown",
            "website": "",
            "business_summary": "",
            "employee_count": 0
        }
    
    try:
        # Create yfinance ticker object
        stock = yf.Ticker(ticker_symbol)
        
        # Get stock info
        info = stock.info
        
        if not info:
            # If info is empty, try alternative approach
            return {
                "ticker": ticker_symbol,
                "sector": "Unknown",
                "industry": "Unknown",
                "market_cap": 0,
                "country": "Unknown",
                "website": "",
                "business_summary": "",
                "employee_count": 0
            }
        
        # Extract information with fallbacks
        sector = info.get('sector', 'Unknown')
        industry = info.get('industry', 'Unknown')
        market_cap = info.get('marketCap', 0)
        country = info.get('country', 'Unknown')
        website = info.get('website', '')
        business_summary = info.get('longBusinessSummary', '')
        employee_count = info.get('fullTimeEmployees', 0)
        
        # If sector is still unknown, try to infer from industry
        if sector == 'Unknown' and industry != 'Unknown':
            sector = infer_sector_from_industry(industry)
        
        return {
            "ticker": ticker_symbol,
            "sector": sector,
            "industry": industry,
            "market_cap": market_cap,
            "country": country,
            "website": website,
            "business_summary": business_summary[:500] + '...' if len(business_summary) > 500 else business_summary,
            "employee_count": employee_count
        }
        
    except Exception as e:
        print(f"Error fetching stock info for {ticker_symbol}: {e}")
        return {
            "ticker": ticker_symbol,
            "sector": "Unknown",
            "industry": "Unknown",
            "market_cap": 0,
            "country": "Unknown",
            "website": "",
            "business_summary": "",
            "employee_count": 0
        }

def infer_sector_from_industry(industry: str) -> str:
    """
    Infer sector from industry when sector information is not available
    """
    industry_lower = industry.lower()
    
    # Technology sectors
    if any(keyword in industry_lower for keyword in ['software', 'technology', 'internet', 'computer', 'semiconductor', 'electronics']):
        return 'Technology'
    
    # Financial sectors
    elif any(keyword in industry_lower for keyword in ['bank', 'financial', 'insurance', 'credit', 'investment']):
        return 'Financial Services'
    
    # Healthcare sectors
    elif any(keyword in industry_lower for keyword in ['pharmaceutical', 'biotechnology', 'medical', 'healthcare', 'drug']):
        return 'Healthcare'
    
    # Energy sectors
    elif any(keyword in industry_lower for keyword in ['oil', 'gas', 'energy', 'petroleum', 'renewable']):
        return 'Energy'
    
    # Consumer sectors
    elif any(keyword in industry_lower for keyword in ['retail', 'consumer', 'food', 'beverage', 'restaurant']):
        return 'Consumer Cyclical'
    
    # Industrial sectors
    elif any(keyword in industry_lower for keyword in ['manufacturing', 'industrial', 'aerospace', 'defense', 'transportation']):
        return 'Industrials'
    
    # Real Estate
    elif any(keyword in industry_lower for keyword in ['real estate', 'property', 'reit']):
        return 'Real Estate'
    
    # Utilities
    elif any(keyword in industry_lower for keyword in ['utility', 'utilities', 'electric', 'water', 'power']):
        return 'Utilities'
    
    # Materials
    elif any(keyword in industry_lower for keyword in ['mining', 'materials', 'chemicals', 'steel', 'aluminum']):
        return 'Basic Materials'
    
    else:
        return 'Unknown'

def format_market_cap(market_cap: int) -> str:
    """
    Format market cap into readable format (B for billions, M for millions)
    """
    if market_cap >= 1_000_000_000:
        return f"${market_cap / 1_000_000_000:.2f}B"
    elif market_cap >= 1_000_000:
        return f"${market_cap / 1_000_000:.2f}M"
    elif market_cap > 0:
        return f"${market_cap:,}"
    else:
        return "N/A"

def format_employee_count(count: int) -> str:
    """
    Format employee count into readable format
    """
    if count >= 1000:
        return f"{count:,}"
    elif count > 0:
        return str(count)
    else:
        return "N/A"

# Test function
if __name__ == "__main__":
    # Test with a few companies
    test_companies = ["Apple", "Microsoft", "TCS", "HDFC Bank", "Tesla"]
    
    for company in test_companies:
        print(f"\n--- {company} ---")
        info = get_stock_sector(company)
        print(f"Ticker: {info['ticker']}")
        print(f"Sector: {info['sector']}")
        print(f"Industry: {info['industry']}")
        print(f"Market Cap: {format_market_cap(info['market_cap'])}")
        print(f"Country: {info['country']}")
        print(f"Employees: {format_employee_count(info['employee_count'])}")