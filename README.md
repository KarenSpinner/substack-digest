# substack-digest
Substack Newsletter Digest Generator

Automatically generate curated digests of your favorite Substack newsletters with AI-powered summaries and intelligent article ranking.

*This doc was created with help from Claude

## What it does
This tool collects articles from your subscribed newsletters, scores them based on content quality and engagement, then uses Claude AI to create summaries of the most interesting pieces. You get a formatted HTML digest with:

Featured articles with AI summaries (top 7 by default)

Additional articles organized by category with links

Quality scores based on word count and comment engagement

Paywall detection so you know what's freely accessible (needs work)

## Quick start

### Clone the repository
git clone https://github.com/KarenSpinner/substack-digest.git
cd substack-digest

### Install dependencies
pip install -r requirements.txt

### Set up your Claude API key
Create a .env file in the project root
echo "CLAUDE_API_KEY=your_api_key_here" > .env

### Run the script
python create_digest.py

The script will generate an HTML file with your digest and save it with a timestamp (e.g., ai_digest_20241201_143022.html).

## Requirements

Python 3.8+
Claude API key (get one at console.anthropic.com)
Internet connection for RSS feeds and article scraping

## Python dependencies
feedparser>=6.0.10
requests>=2.31.0
beautifulsoup4>=4.12.2
anthropic>=0.7.0
python-dotenv>=1.0.0

## Configuration

### Add your newsletters
Edit the newsletter_feeds list in create_digest.py:
pythonCopyself.newsletter_feeds = [
    "https://yournewsletter.substack.com/feed",
    "https://another-newsletter.substack.com/feed",
    # Add more RSS feed URLs here
]

Finding RSS feeds: Most Substack newsletters have RSS feeds at newsletter-name.substack.com/feed

### Adjusting parameters
In the main execution section, modify these parameters:
digest.run_digest(
    days_back=7,        # How many days to look back
    featured_count=7    # Number of articles to feature with summaries
)

### Customizing scoring
The quality scoring algorithm weighs two factors equally (0-100 total):

Content length (0-50 points): Optimal range 500-2000 words
Comment engagement (0-50 points): 5 points per comment, capped at 50

Modify calculate_quality_score() to adjust these weights or add new factors.

## How it works

Fetches articles from RSS feeds for your specified time period

Extracts content and scrapes engagement metrics (comments)

Scores articles based on length and engagement

Selects top articles for AI summarization

Generates summaries using Claude API

Creates HTML digest with featured articles and categorized additional reading

Tracks processed articles to avoid duplicates on future runs

### Output
The script generates a timestamped HTML file containing:

Clean, readable formatting optimized for web and print

Featured articles with 2-3 sentence AI summaries

Quality scores and engagement metrics
Additional articles grouped by category (AI News, Strategy & Business, etc.)

Paywall indicators for restricted content

Direct links to all original articles

### File structure
substack-digest-generator/
├── orchestrator.py           # Main script
├── requirements.txt          # Python dependencies
├── .env                     # API keys (create this)
├── processed_articles.json  # Tracking file (auto-generated)
├── ai_digest_*.html         # Generated digests
└── README.md


## Contributing
Pull requests welcome! Areas for improvement:

Content-based categorization using AI
Support for non-Substack newsletters
Web interface (see HTML mockup in /ui-mockup/)

Scheduled automation

Additional scoring factors (author reputation, keyword matching)

License
MIT License - feel free to use this for personal or commercial projects.
Support

Open an issue for bugs or feature requests

Check the Anthropic documentation for Claude API questions

See the example output for what the generated digests look like


Built with: Python, Claude AI, RSS feeds, and a healthy obsession with newsletter efficiency.
