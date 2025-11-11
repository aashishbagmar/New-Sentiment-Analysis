"""
Stock Correlation & Impact Analysis Engine

This module provides comprehensive correlation analysis between stocks,
including sector peers, supply chain relationships, and impact scoring.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import requests
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

class StockCorrelationEngine:
    def __init__(self):
        self.sector_mapping = {
            'Technology': ['AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'CRM', 'ORCL', 'ADBE', 'INTC', 'AMD'],
            'Financial Services': ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'USB', 'PNC', 'TFC', 'COF'],
            'Healthcare': ['JNJ', 'PFE', 'UNH', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'BMY', 'AMGN'],
            'Consumer Cyclical': ['AMZN', 'TSLA', 'HD', 'MCD', 'DIS', 'NKE', 'SBUX', 'LOW', 'TJX', 'BKNG'],
            'Energy': ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'PSX', 'VLO', 'MPC', 'OXY', 'HAL'],
            'Industrials': ['BA', 'CAT', 'GE', 'HON', 'UNP', 'LMT', 'MMM', 'FDX', 'UPS', 'RTX'],
            'Basic Materials': ['LIN', 'APD', 'ECL', 'DD', 'DOW', 'FCX', 'NEM', 'VMC', 'MLM', 'PPG'],
            'Real Estate': ['AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'SPG', 'O', 'WELL', 'DLR', 'EXR'],
            'Utilities': ['NEE', 'DUK', 'SO', 'AEP', 'EXC', 'XEL', 'SRE', 'D', 'PEG', 'PCG'],
            'Consumer Defensive': ['PG', 'KO', 'PEP', 'WMT', 'COST', 'CL', 'KMB', 'GIS', 'K', 'CPB']
        }
        
        # Indian stock sector mapping
        self.indian_sectors = {
            'Technology': ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'LTI.NS', 'MINDTREE.NS'],
            'Financial Services': ['HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'AXISBANK.NS', 'KOTAKBANK.NS', 'INDUSINDBK.NS'],
            'Energy': ['RELIANCE.NS', 'ONGC.NS', 'IOC.NS', 'BPCL.NS', 'HINDPETRO.NS', 'GAIL.NS'],
            'Consumer Cyclical': ['MARUTI.NS', 'BAJAJ-AUTO.NS', 'M&M.NS', 'EICHERMOT.NS', 'HEROMOTOCO.NS'],
            'Healthcare': ['SUNPHARMA.NS', 'DRREDDY.NS', 'CIPLA.NS', 'LUPIN.NS', 'BIOCON.NS', 'CADILAHC.NS'],
            'Industrials': ['LT.NS', 'ULTRACEMCO.NS', 'ADANIENT.NS', 'ADANIPORTS.NS', 'TATASTEEL.NS'],
            'Consumer Defensive': ['HINDUUNILV.NS', 'ITC.NS', 'NESTLEIND.NS', 'GODREJCP.NS', 'DABUR.NS']
        }
    
    def get_stock_price_data(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Fetch historical price data for a stock."""
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period=period)
            if data.empty:
                return None
            return data
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return None
    
    def calculate_correlation(self, ticker1: str, ticker2: str, period: str = "1y") -> Dict:
        """Calculate correlation between two stocks."""
        try:
            # Fetch data for both stocks
            data1 = self.get_stock_price_data(ticker1, period)
            data2 = self.get_stock_price_data(ticker2, period)
            
            if data1 is None or data2 is None:
                return {"correlation": 0.0, "strength": "No Data", "p_value": 1.0}
            
            # Align dates and calculate returns
            combined_data = pd.DataFrame({
                'stock1': data1['Close'],
                'stock2': data2['Close']
            }).dropna()
            
            if len(combined_data) < 30:  # Need enough data points
                return {"correlation": 0.0, "strength": "Insufficient Data", "p_value": 1.0}
            
            # Calculate daily returns
            returns1 = combined_data['stock1'].pct_change().dropna()
            returns2 = combined_data['stock2'].pct_change().dropna()
            
            # Calculate correlation
            correlation = returns1.corr(returns2)
            
            # Interpret correlation strength
            abs_corr = abs(correlation)
            if abs_corr >= 0.8:
                strength = "Very Strong"
            elif abs_corr >= 0.6:
                strength = "Strong"
            elif abs_corr >= 0.4:
                strength = "Moderate"
            elif abs_corr >= 0.2:
                strength = "Weak"
            else:
                strength = "Very Weak"
            
            return {
                "correlation": round(correlation, 3),
                "strength": strength,
                "direction": "Positive" if correlation > 0 else "Negative",
                "data_points": len(returns1)
            }
            
        except Exception as e:
            print(f"Error calculating correlation between {ticker1} and {ticker2}: {e}")
            return {"correlation": 0.0, "strength": "Error", "p_value": 1.0}
    
    def find_sector_peers(self, ticker: str, sector: str) -> List[str]:
        """Find sector peer stocks."""
        peers = []
        
        # Check if it's an Indian stock
        if ticker.endswith('.NS') or ticker.endswith('.BO'):
            sector_stocks = self.indian_sectors.get(sector, [])
        else:
            sector_stocks = self.sector_mapping.get(sector, [])
        
        # Remove the original ticker from peers
        peers = [stock for stock in sector_stocks if stock != ticker]
        return peers[:8]  # Limit to top 8 peers
    
    def get_related_stocks(self, ticker: str, sector: str, industry: str) -> Dict[str, List[str]]:
        """Get related stocks categorized by relationship type."""
        relationships = {
            "sector_peers": [],
            "industry_peers": [],
            "competitors": []
        }
        
        # Get sector peers
        sector_peers = self.find_sector_peers(ticker, sector)
        relationships["sector_peers"] = sector_peers[:5]
        
        # For industry peers, we'll use a subset of sector peers
        # In a real implementation, you might want to use industry-specific data
        relationships["industry_peers"] = sector_peers[2:6] if len(sector_peers) > 2 else sector_peers
        
        # Competitors can be the same as sector peers for simplicity
        relationships["competitors"] = sector_peers[:4]
        
        return relationships
    
    def analyze_stock_impact(self, primary_ticker: str, sector: str) -> Dict:
        """Comprehensive impact analysis for a stock."""
        try:
            # Get related stocks
            related_stocks = self.get_related_stocks(primary_ticker, sector, "")
            
            # Calculate correlations with each related stock
            correlation_results = []
            
            # Process all related stocks
            all_related = []
            for category, stocks in related_stocks.items():
                for stock in stocks:
                    if stock not in all_related:
                        all_related.append((stock, category))
            
            # Calculate correlations concurrently for faster processing
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for stock, category in all_related:
                    future = executor.submit(self.calculate_correlation, primary_ticker, stock)
                    futures.append((future, stock, category))
                
                for future, stock, category in futures:
                    try:
                        correlation_data = future.result(timeout=10)
                        if correlation_data["correlation"] != 0.0:
                            correlation_results.append({
                                "ticker": stock,
                                "relationship_type": category,
                                "correlation": correlation_data["correlation"],
                                "strength": correlation_data["strength"],
                                "direction": correlation_data.get("direction", "Neutral"),
                                "impact_score": abs(correlation_data["correlation"]) * 100
                            })
                    except Exception as e:
                        print(f"Error processing {stock}: {e}")
                        continue
            
            # Sort by correlation strength
            correlation_results.sort(key=lambda x: abs(x["correlation"]), reverse=True)
            
            # Calculate overall impact metrics
            if correlation_results:
                avg_correlation = np.mean([abs(r["correlation"]) for r in correlation_results])
                max_correlation = max([abs(r["correlation"]) for r in correlation_results])
                
                # Determine overall market influence
                if avg_correlation >= 0.6:
                    market_influence = "High"
                elif avg_correlation >= 0.4:
                    market_influence = "Moderate"
                else:
                    market_influence = "Low"
            else:
                avg_correlation = 0
                max_correlation = 0
                market_influence = "Unknown"
            
            return {
                "primary_ticker": primary_ticker,
                "related_stocks": correlation_results,
                "summary": {
                    "total_analyzed": len(correlation_results),
                    "average_correlation": round(avg_correlation, 3),
                    "max_correlation": round(max_correlation, 3),
                    "market_influence": market_influence
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error in impact analysis for {primary_ticker}: {e}")
            return {
                "primary_ticker": primary_ticker,
                "related_stocks": [],
                "summary": {
                    "total_analyzed": 0,
                    "average_correlation": 0,
                    "max_correlation": 0,
                    "market_influence": "Error"
                },
                "error": str(e)
            }
    
    def get_impact_network_data(self, correlation_results: List[Dict]) -> Dict:
        """Generate network visualization data for impact analysis."""
        nodes = []
        edges = []
        
        # Add primary node (will be set by caller)
        
        # Add related stock nodes
        for result in correlation_results:
            # Color based on correlation strength
            if abs(result["correlation"]) >= 0.6:
                color = "#e74c3c"  # Red for strong correlation
            elif abs(result["correlation"]) >= 0.4:
                color = "#f39c12"  # Orange for moderate
            else:
                color = "#3498db"  # Blue for weak
            
            nodes.append({
                "id": result["ticker"],
                "label": result["ticker"],
                "color": color,
                "size": abs(result["correlation"]) * 50 + 10,
                "relationship": result["relationship_type"]
            })
            
            edges.append({
                "from": "primary",  # Will be replaced with actual primary ticker
                "to": result["ticker"],
                "width": abs(result["correlation"]) * 5,
                "color": color,
                "correlation": result["correlation"]
            })
        
        return {"nodes": nodes, "edges": edges}

# Test function
if __name__ == "__main__":
    engine = StockCorrelationEngine()
    
    # Test with Apple
    result = engine.analyze_stock_impact("AAPL", "Technology")
    print("=== APPLE IMPACT ANALYSIS ===")
    print(f"Total stocks analyzed: {result['summary']['total_analyzed']}")
    print(f"Average correlation: {result['summary']['average_correlation']}")
    print(f"Market influence: {result['summary']['market_influence']}")
    
    print("\nTop correlations:")
    for stock in result["related_stocks"][:5]:
        print(f"{stock['ticker']}: {stock['correlation']} ({stock['strength']})")
    
    # Test with Indian stock
    result_indian = engine.analyze_stock_impact("TCS.NS", "Technology")
    print("\n=== TCS IMPACT ANALYSIS ===")
    print(f"Total stocks analyzed: {result_indian['summary']['total_analyzed']}")
    print(f"Average correlation: {result_indian['summary']['average_correlation']}")