"""
AI Newsletter Digest Generator
============================

This script automatically generates a curated digest of AI newsletter articles by:
1. Fetching articles from RSS feeds of AI newsletters
2. Extracting content and engagement metrics (comments)
3. Scoring articles based on word count and comment engagement
4. Selecting top articles for AI-powered summarization
5. Generating an HTML digest with featured articles and additional reading

Requirements:
- Claude API key (stored in .env file as CLAUDE_API_KEY)
- Internet connection for RSS feeds and article scraping
- Python packages: see requirements.txt

Usage:
    python orchestrator.py

Output:
- HTML file with timestamped filename (ai_digest_YYYYMMDD_HHMMSS.html)
- JSON tracking file to avoid reprocessing articles (processed_articles.json)

Author: [Your Name]
Last Updated: August 2025
"""

import feedparser
import json
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from pathlib import Path
import re
import anthropic
from urllib.parse import urljoin
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass
class Article:
    """Data structure for storing article information"""
    title: str
    link: str
    published: datetime
    author: str
    content: str
    source: str
    word_count: int = 0
    comments: int = 0
    quality_score: float = 0.0
    summary: str = ""
    is_paywalled: bool = False

class SubstackDigest:
    """
    Main class for generating AI newsletter digests
    
    Handles RSS feed parsing, content extraction, article scoring,
    AI summarization, and HTML digest generation.
    """
    
    def __init__(self, processed_articles_file: str = "processed_articles.json"):
        """
        Initialize the digest generator
        
        Args:
            processed_articles_file: JSON file to track previously processed articles
        """
        # Get Claude API key from environment variable
        claude_api_key = os.getenv('CLAUDE_API_KEY')
        if not claude_api_key:
            raise ValueError("CLAUDE_API_KEY not found in environment variables. Please set it in your .env file.")
        
        self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
        self.processed_file = Path(processed_articles_file)
        self.processed_articles = self.load_processed_articles()
        
        # AI Newsletter feeds - expand this list as needed
        self.newsletter_feeds = [
            "https://karozieminski.substack.com/feed",
            "https://designwithai.substack.com/feed",
            "https://thestrategystack.substack.com/feed",
            "https://www.lennysnewsletter.com/feed",
            "https://kp.substack.com/feed",
            "https://inferencebysequoia.substack.com/feed",
            "https://aimaker.substack.com/feed",
            "https://www.buildtolaunch.ai/feed",
            "https://leadershipinchange10.substack.com/feed",
            "https://aiblewmymind.substack.com/feed",
            "https://ileanamarcut.substack.com/feed",
            "https://sixpeas.substack.com/feed",
            "https://aigovernancelead.substack.com/feed",
            "https://aihumanity.substack.com/feed",
            "https://ab2ai.substack.com/feed",
            "https://aicadence.co/feed",
            "https://betteconnects.substack.com/feed",
            "https://www.sabrina.dev/feed",
            "https://businessengineer.ai/feed",
            "https://www.thealgorithmicbridge.com/feed",
            "https://nlp.elvissaravia.com/feed",
            "https://www.4ir.news/feed",
            "https://techtiff.substack.com/feed",
            "https://www.luizasnewsletter.com/feed",
            "https://www.productcompass.pm/feed",
            "https://www.the-founders-corner.com/feed",
            "https://newsletter.techworld-with-milan.com/feed",
            "https://learn.thedesignsystem.guide/feed",
        ]
    
    def load_processed_articles(self) -> Dict:
        """Load previously processed articles from JSON file to avoid duplicates"""
        if self.processed_file.exists():
            with open(self.processed_file, 'r') as f:
                return json.load(f)
        return {"featured": [], "reviewed": []}
    
    def save_processed_articles(self):
        """Save processed articles to JSON file"""
        with open(self.processed_file, 'w') as f:
            json.dump(self.processed_articles, f, indent=2, default=str)
    
    def detect_paywall(self, content: str, title: str) -> bool:
        """
        Detect if an article is likely paywalled based on content indicators
        
        Args:
            content: Article content text
            title: Article title
            
        Returns:
            True if article appears to be paywalled
        """
        paywall_indicators = [
            "subscribe to continue reading",
            "this post is for paid subscribers",
            "upgrade to paid",
            "become a paid subscriber",
            "this content is for subscribers only",
            "premium subscribers only",
            "subscribe now to read more",
            "paywall",
            "members only",
            "paid tier"
        ]
        
        content_lower = content.lower()
        title_lower = title.lower()
        
        # Check for paywall indicators in content or title
        for indicator in paywall_indicators:
            if indicator in content_lower or indicator in title_lower:
                return True
        
        # Check for very short content (often indicates paywall cutoff)
        if len(content.split()) < 50:  # Less than 50 words might indicate paywall
            return True
            
        return False
    
    def fetch_recent_articles(self, days_back: int = 7) -> List[Article]:
        """
        Fetch articles from all RSS feeds within specified timeframe
        
        Args:
            days_back: Number of days to look back for articles
            
        Returns:
            List of Article objects
        """
        articles = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        for i, feed_url in enumerate(self.newsletter_feeds):
            try:
                print(f"Fetching from {feed_url} ({i+1}/{len(self.newsletter_feeds)})")
                feed = feedparser.parse(feed_url)
                source_name = feed.feed.get('title', feed_url)
                
                for entry in feed.entries:
                    # Parse publication date
                    pub_date = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') else datetime.now()
                    
                    if pub_date < cutoff_date:
                        continue
                    
                    # Skip if already processed
                    if entry.link in [art['link'] for art in self.processed_articles.get('featured', [])] + \
                       [art['link'] for art in self.processed_articles.get('reviewed', [])]:
                        continue
                    
                    # Extract content
                    content = self.extract_content(entry)
                    
                    # Get engagement metrics (comments only)
                    print(f"  Scraping metrics for: {entry.title[:50]}...")
                    comments = self.scrape_comments(entry.link)
                    
                    # Detect paywall
                    is_paywalled = self.detect_paywall(content, entry.title)
                    
                    article = Article(
                        title=entry.title,
                        link=entry.link,
                        published=pub_date,
                        author=entry.get('author', 'Unknown'),
                        content=content,
                        source=source_name,
                        word_count=len(content.split()),
                        comments=comments,
                        is_paywalled=is_paywalled
                    )
                    
                    articles.append(article)
                    time.sleep(1.5)  # Be respectful to servers
                    
            except Exception as e:
                print(f"Error fetching {feed_url}: {e}")
                continue
            
            # Delay between feeds
            time.sleep(2)
        
        return articles
    
    def extract_content(self, entry) -> str:
        """Extract article content from RSS entry"""
        content = ""
        if hasattr(entry, 'content'):
            content = entry.content[0].value
        elif hasattr(entry, 'summary'):
            content = entry.summary
        elif hasattr(entry, 'description'):
            content = entry.description
        
        # Clean HTML tags
        soup = BeautifulSoup(content, 'html.parser')
        return soup.get_text().strip()
    
    def scrape_comments(self, url: str) -> int:
        """
        Scrape comment count from article URL - optimized version
        
        Args:
            url: Article URL
            
        Returns:
            Number of comments found
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get all text content and search for comment patterns
            page_text = soup.get_text()
            
            # Try different comment patterns
            comment_patterns = [
                r'(\d+)\s+comments?(?:\s|$)',  # "5 comments"
                r'(\d+)\s+replies?(?:\s|$)',   # "3 replies"
                r'comments?\s*\((\d+)\)',      # "Comments (7)"
                r'replies?\s*\((\d+)\)',       # "Replies (2)"
            ]
            
            for pattern in comment_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    comments = max(int(match) for match in matches)  # Take highest number found
                    print(f"    Found comments: {comments}")
                    return comments
            
            # Fallback: look in href attributes
            comment_links = soup.find_all('a', href=re.compile(r'#?comments?', re.IGNORECASE))
            for link in comment_links:
                link_text = link.get_text()
                match = re.search(r'(\d+)', link_text)
                if match:
                    comments = int(match.group(1))
                    print(f"    Found comments in link: {comments}")
                    return comments
            
            return 0
            
        except Exception as e:
            print(f"    Error scraping comments for {url}: {e}")
            return 0

    def categorize_newsletter(self, source: str) -> str:
        """Simple source-based categorization"""
        
        # Direct source mapping - most reliable approach
        source_categories = {
            # News & Industry Updates
            '4IR - Daily AI News': 'AI News & Updates',
            
            # Strategy & Business  
            'The Strategy Stack': 'Strategy & Business',
            'The Business Engineer': 'Strategy & Business',
            'AI Cadence': 'Strategy & Business',
            'Inference by Sequoia Capital': 'AI Research & Technical',
            
            # Governance & Ethics
            'AI Governance, Ethics and Leadership': 'AI Governance & Ethics',
            'Luiza\'s Newsletter': 'AI Governance & Ethics',
            'AI For Humanity': 'AI Governance & Ethics',
            
            # Research & Technical
            'AI Newsletter': 'AI Research & Technical',
            'The Algorithmic Bridge': 'AI Research & Technical', 
            
            # Product & Entrepreneurship
            'Lenny\'s Newsletter': 'Product & Entrepreneurship',
            'The Founders Corner®': 'Product & Entrepreneurship',
            'Design with AI': 'Product & Entrepreneurship',
            'The Product Compass': 'Product & Entrepreneurship',
            'Build to Launch': 'Product & Entrepreneurship',
            'Product with Attitude': 'Product & Entrepreneurship',
            
            # Leadership & Career
            'Leadership in Change': 'Leadership & Career',
            'AI Can Do That? 🔍': 'Leadership & Career', 
            'KP\'s Column': 'Leadership & Career',
            
            # Development & Tools
            'The AI Creator Drop': 'Development & Tools',
            'Sabrina Ramonov 🍄': 'Development & Tools',
            'Tech World With Milan Newsletter': 'Development & Tools',
            'The Design System Guide': 'Development & Tools',
            'AI blew my mind': 'AI Research & Technical',
            'The AI Maker': 'AI Research & Technical',
            
            # General Insights
            '6 \'P\'s in AI Pods (AI6P)': 'AI Analysis & Insights'
        }
        
        return source_categories.get(source, 'Other')

    def generate_digest_html(self, featured_articles: List[Article], other_articles: List[Article]) -> str:
        """Generate HTML digest with improved formatting and categorization"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI Newsletter Digest - {datetime.now().strftime('%B %d, %Y')}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }}
                .header {{ border-bottom: 2px solid #333; margin-bottom: 30px; padding-bottom: 20px; }}
                .featured {{ background: #f8f9fa; padding: 25px; margin: 25px 0; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .article {{ margin-bottom: 25px; }}
                .title {{ font-size: 20px; font-weight: bold; margin-bottom: 12px; }}
                .title a {{ text-decoration: none; color: #333; }}
                .title a:hover {{ color: #007acc; }}
                .meta {{ color: #666; font-size: 14px; margin-bottom: 15px; }}
                .summary {{ line-height: 1.6; margin-bottom: 15px; font-size: 16px; }}
                .metrics {{ font-size: 13px; color: #888; background: #f0f0f0; padding: 10px; border-radius: 5px; }}
                .paywall-indicator {{ color: #ff6b35; font-weight: bold; font-size: 12px; }}
                .other-articles {{ margin-top: 50px; }}
                .category-section {{ margin-bottom: 35px; }}
                .category-title {{ font-size: 22px; font-weight: bold; color: #333; margin-bottom: 15px; border-bottom: 2px solid #007acc; padding-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; }}
                .category-articles {{ display: grid; gap: 12px; }}
                .other-article-item {{ padding: 15px; background: #f8f9fa; border-radius: 6px; }}
                .other-article-item:hover {{ background: #f0f0f0; }}
                .other-title {{ font-weight: bold; margin-bottom: 5px; }}
                .other-title a {{ text-decoration: none; color: #333; }}
                .other-title a:hover {{ color: #007acc; }}
                .other-meta {{ font-size: 12px; color: #666; }}
                .footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 14px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🤖 AI Newsletter Digest</h1>
                <p><strong>{datetime.now().strftime('%B %d, %Y')}</strong> | {len(featured_articles)} Featured Articles | {len(other_articles)} Additional Articles</p>
                <p><small>Automatically curated from leading AI newsletters based on content quality and engagement</small></p>
            </div>
        """
        
        # Featured articles with summaries
        html += "<h2>📚 Featured Articles</h2>"
        for i, article in enumerate(featured_articles, 1):
            paywall_indicator = '<span class="paywall-indicator">🔒 PAYWALLED</span>' if article.is_paywalled else ''
            html += f"""
            <div class="featured">
                <div class="article">
                    <div class="title"><a href="{article.link}" target="_blank">{article.title}</a> {paywall_indicator}</div>
                    <div class="meta">By {article.author} | {article.source} | {article.published.strftime('%B %d, %Y')}</div>
                    <div class="summary">{article.summary}</div>
                    <div class="metrics">Quality Score: {article.quality_score} | Words: {article.word_count:,} | 💬 {article.comments} comments</div>
                </div>
            </div>
            """
        
        # Categorized other articles
        if other_articles:
            # Group articles by category
            categorized = {}
            for article in other_articles:
                category = self.categorize_newsletter(article.source)
                if category not in categorized:
                    categorized[category] = []
                categorized[category].append(article)
            
            html += """
            <div class="other-articles">
                <h2>📝 Additional Articles by Category</h2>
            """
            
            # Sort categories by number of articles (descending)
            sorted_categories = sorted(categorized.items(), key=lambda x: len(x[1]), reverse=True)
            
            for category, articles in sorted_categories:
                html += f"""
                <div class="category-section">
                    <div class="category-title">{category} ({len(articles)} articles)</div>
                    <div class="category-articles">
                """
                
                # Sort articles within category by quality score
                articles.sort(key=lambda x: x.quality_score, reverse=True)
                
                for article in articles:
                    paywall_indicator = ' 🔒' if article.is_paywalled else ''
                    html += f"""
                    <div class="other-article-item">
                        <div class="other-title"><a href="{article.link}" target="_blank">{article.title}</a>{paywall_indicator}</div>
                        <div class="other-meta">{article.author} | {article.source} | 💬 {article.comments} comments</div>
                    </div>
                    """
                
                html += "</div></div>"
            
            html += "</div>"
        
        html += """
        <div class="footer">
            <p>Generated automatically by AI Newsletter Digest</p>
            <p><small>Quality scoring based on content length and community engagement</small></p>
        </div>
        </body>
        </html>
        """
        
        return html
    
    def calculate_quality_score(self, article: Article) -> float:
        """
        Calculate quality score based on content length and comment engagement
        
        Args:
            article: Article to score
            
        Returns:
            Quality score (0-100 scale)
        """
        # Content length score (0-50 points)
        # Ideal range: 500-2000 words
        length_score = min(article.word_count / 2000, 1.0) * 50
        
        # Comment engagement score (0-50 points)
        # Comments are heavily weighted as requested
        comment_score = min(article.comments * 5, 50) if article.comments > 0 else 0
        
        total_score = length_score + comment_score
        return round(total_score, 2)
    
    def select_top_articles(self, articles: List[Article], count: int = 7) -> tuple[List[Article], List[Article]]:
        """Select highest quality articles for featured section"""
        # Calculate quality scores
        for article in articles:
            article.quality_score = self.calculate_quality_score(article)
        
        # Sort by quality score
        sorted_articles = sorted(articles, key=lambda x: x.quality_score, reverse=True)
        
        featured = sorted_articles[:count]
        others = sorted_articles[count:]
        
        return featured, others
    
    def summarize_article(self, article: Article) -> str:
        """
        Generate AI summary using Claude API
        
        Args:
            article: Article to summarize
            
        Returns:
            2-3 sentence summary
        """
        try:
            prompt = f"""
            Please provide a concise 2-3 sentence summary of this AI/tech article:
            
            Title: {article.title}
            Author: {article.author}
            Source: {article.source}
            
            Content: {article.content[:4000]}...
            
            Focus on the key insights, developments, or arguments presented.
            """
            
            message = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return message.content[0].text
            
        except Exception as e:
            print(f"Error summarizing article {article.title}: {e}")
            return "Summary unavailable."
    
    def run_digest(self, days_back: int = 7, featured_count: int = 7):
        """
        Main execution function - generates complete digest
        
        Args:
            days_back: Number of days to look back for articles
            featured_count: Number of articles to feature with summaries
        """
        print(f"🚀 Starting digest generation for past {days_back} days...")
        
        # Fetch articles
        articles = self.fetch_recent_articles(days_back)
        print(f"📥 Found {len(articles)} new articles")
        
        if not articles:
            print("No new articles found.")
            return
        
        # Select top articles
        featured, others = self.select_top_articles(articles, featured_count)
        print(f"⭐ Selected {len(featured)} featured articles")
        
        # Generate summaries for featured articles
        print("🤖 Generating summaries...")
        for article in featured:
            article.summary = self.summarize_article(article)
            time.sleep(1)  # Rate limiting for API calls
        
        # Generate HTML digest
        html_digest = self.generate_digest_html(featured, others)
        
        # Save digest to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        digest_filename = f"ai_digest_{timestamp}.html"
        
        with open(digest_filename, 'w', encoding='utf-8') as f:
            f.write(html_digest)
        
        print(f"💾 Digest saved to {digest_filename}")
        
        # Update processed articles tracking
        for article in featured:
            self.processed_articles['featured'].append({
                'title': article.title,
                'link': article.link,
                'date_processed': datetime.now().isoformat(),
                'quality_score': article.quality_score
            })
        
        for article in others:
            self.processed_articles['reviewed'].append({
                'title': article.title,
                'link': article.link,
                'date_processed': datetime.now().isoformat(),
                'quality_score': article.quality_score
            })
        
        self.save_processed_articles()
        print("✅ Digest generation complete!")
        
        return digest_filename

# Main execution
if __name__ == "__main__":
    """
    Run the digest generator
    
    Make sure you have:
    1. Created a .env file with CLAUDE_API_KEY=your_key_here
    2. Installed required packages: pip install -r requirements.txt
    """
    # Initialize digest generator (API key loaded from .env)
    digest = SubstackDigest()
    
    # Run weekly digest
    digest.run_digest(days_back=7, featured_count=7)