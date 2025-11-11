"""
Enhanced Stock Information Module

Integrates with correlation engine and provides comprehensive stock analysis
including sector information, related stocks, and impact analysis.
"""

import yfinance as yf
import requests
import json
from typing import Dict, Optional, List
from correlation_engine import StockCorrelationEngine

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

def get_comprehensive_stock_info(company_name: str) -> Dict:
    """
    Get comprehensive stock information including sector, industry, and correlation analysis.
    Returns a dictionary with all stock details including related stocks impact analysis.
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
            "employee_count": 0,
            "correlation_analysis": None,
            "related_stocks": [],
            "error": "No company name provided"
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
            "employee_count": 0,
            "correlation_analysis": None,
            "related_stocks": [],
            "error": "Could not find ticker symbol"
        }
    
    try:
        # Create yfinance ticker object
        stock = yf.Ticker(ticker_symbol)
        
        # Get stock info
        info = stock.info
        
        if not info:
            # If info is empty, return basic structure
            return {
                "ticker": ticker_symbol,
                "sector": "Unknown",
                "industry": "Unknown", 
                "market_cap": 0,
                "country": "Unknown",
                "website": "",
                "business_summary": "",
                "employee_count": 0,
                "correlation_analysis": None,
                "related_stocks": [],
                "error": "Could not fetch stock information"
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
        
        # Initialize correlation analysis
        correlation_analysis = None
        related_stocks = []
        
        # Perform correlation analysis if we have a valid sector
        if sector != 'Unknown':
            try:
                correlation_engine = StockCorrelationEngine()
                impact_analysis = correlation_engine.analyze_stock_impact(ticker_symbol, sector)
                
                correlation_analysis = {
                    "total_analyzed": impact_analysis['summary']['total_analyzed'],
                    "average_correlation": impact_analysis['summary']['average_correlation'],
                    "max_correlation": impact_analysis['summary']['max_correlation'],
                    "market_influence": impact_analysis['summary']['market_influence']
                }
                
                # Get top related stocks
                related_stocks = impact_analysis.get('related_stocks', [])[:8]  # Top 8
                
            except Exception as e:
                print(f"Error in correlation analysis: {e}")
                correlation_analysis = {
                    "total_analyzed": 0,
                    "average_correlation": 0,
                    "max_correlation": 0,
                    "market_influence": "Error"
                }
        
        return {
            "ticker": ticker_symbol,
            "sector": sector,
            "industry": industry,
            "market_cap": market_cap,
            "country": country,
            "website": website,
            "business_summary": business_summary[:500] + '...' if len(business_summary) > 500 else business_summary,
            "employee_count": employee_count,
            "correlation_analysis": correlation_analysis,
            "related_stocks": related_stocks
        }
        
    except Exception as e:
        print(f"Error fetching comprehensive stock info for {ticker_symbol}: {e}")
        return {
            "ticker": ticker_symbol,
            "sector": "Unknown",
            "industry": "Unknown", 
            "market_cap": 0,
            "country": "Unknown",
            "website": "",
            "business_summary": "",
            "employee_count": 0,
            "correlation_analysis": None,
            "related_stocks": [],
            "error": str(e)
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

def format_correlation_strength(correlation: float) -> Dict[str, str]:
    """
    Format correlation value with color coding and description
    """
    abs_corr = abs(correlation)
    
    if abs_corr >= 0.8:
        strength = "Very Strong"
        color = "#e74c3c"  # Red
    elif abs_corr >= 0.6:
        strength = "Strong" 
        color = "#f39c12"  # Orange
    elif abs_corr >= 0.4:
        strength = "Moderate"
        color = "#f1c40f"  # Yellow
    elif abs_corr >= 0.2:
        strength = "Weak"
        color = "#3498db"  # Blue
    else:
        strength = "Very Weak"
        color = "#95a5a6"  # Gray
    
    return {
        "strength": strength,
        "color": color,
        "direction": "Positive" if correlation > 0 else "Negative" if correlation < 0 else "Neutral"
    }

# Legacy function for backward compatibility
def get_stock_sector(company_name: str) -> Dict:
    """
    Legacy function - calls the new comprehensive function but returns limited data
    for backward compatibility with existing code.
    """
    full_info = get_comprehensive_stock_info(company_name)
    
    return {
        "ticker": full_info["ticker"],
        "sector": full_info["sector"],
        "industry": full_info["industry"],
        "market_cap": full_info["market_cap"],
        "country": full_info["country"],
        "website": full_info["website"],
        "business_summary": full_info["business_summary"],
        "employee_count": full_info["employee_count"]
    }

# Test function
if __name__ == "__main__":
    # Test with a few companies
    test_companies = ["Apple", "Microsoft", "TCS", "HDFC Bank", "Tesla"]
    
    for company in test_companies:
        print(f"\n--- {company} ---")
        info = get_comprehensive_stock_info(company)
        print(f"Ticker: {info['ticker']}")
        print(f"Sector: {info['sector']}")
        print(f"Industry: {info['industry']}")
        print(f"Market Cap: {format_market_cap(info['market_cap'])}")
        print(f"Country: {info['country']}")
        print(f"Employees: {format_employee_count(info['employee_count'])}")
        
        if info['correlation_analysis']:
            print(f"Market Influence: {info['correlation_analysis']['market_influence']}")
            print(f"Average Correlation: {info['correlation_analysis']['average_correlation']}")
            print(f"Related Stocks: {len(info['related_stocks'])}")
        
        if info['related_stocks']:
            print("Top correlations:")
            for stock in info['related_stocks'][:3]:
                print(f"  {stock['ticker']}: {stock['correlation']} ({stock['strength']})")