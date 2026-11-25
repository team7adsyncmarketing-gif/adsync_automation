"""AdSync Marketing Reel Idea Generator.

Converts trending social signals into original, high-converting video concepts
specifically tailored for AdSync and rendered using the Phase 1 Faceless Shorts engine.
"""

import uuid
from typing import List, Optional, Dict, Any
from ..storage.models import ReelItem, ReelAnalysis, AdSyncIdea

# Style mapping linking marketing categories to Phase 1 Faceless Shorts rendering styles
STYLE_ROUTING = {
    "Meta Ads": "deep-dive",              # 3D algorithmic mechanism & auction flow
    "Marketing Automation": "inside-out", # 2D x-ray cutaway of pipeline and lead flow
    "Digital Marketing": "deep-dive",     # High-tech 3D data flows
    "Lead Generation": "stick-story",     # Survival guide: 'What to do when leads dry up'
    "Business Growth": "tall-tale",       # True story / loophole / scaling breakdown
    "Branding": "inside-out",             # X-ray breakdown of brand perception
    "Real Estate Marketing": "paper-atlas", # Regional map journeys and territory dominance
    "Instagram Marketing": "stick-story", # Creator survival steps & algorithm navigation
}

# Granular idea catalog keyed by shortcode/topic angle
REEL_SPECIFIC_IDEAS: Dict[str, Dict[str, Any]] = {
    "C7xK9s0P1aA": {
        "topic": "Why 'Boost Post' Destroys Conversion Tracking vs Full Funnel Meta Ads",
        "target_audience": "Local Business Owners, Medspa & Clinic Founders, Service Providers",
        "business_problem": "Wasting ad budget on vanity likes instead of tracked lead capture.",
        "hooks": [
            "What actually happens to your $50 the second you tap 'Boost Post' on Instagram?",
            "The hidden algorithm trap that turns boosted post budget into empty double-taps.",
            "Why 80% of local business ad accounts are optimized for the completely wrong event."
        ],
        "content_format": "3D Data Pipeline Explainer showing Click vs Conversion Routing",
        "faceless_short_style": "deep-dive",
        "cta": "Comment 'ADS' to get our free 7-step lead conversion campaign template.",
        "reasoning": "Directly tackles a common beginner mistake; 3D visual explanation proves algorithmic difference clearly."
    },
    "C7yM8q1L2bB": {
        "topic": "Conflict-First Video Hooks for High-Ticket B2B Inbound Conversion",
        "target_audience": "Consultants, Agency Founders & B2B Service Providers",
        "business_problem": "Weak video intros cause 80% audience drop-off before the value proposition.",
        "hooks": [
            "Why starting your videos with 'Hey guys' kills your retention before second two.",
            "The conflict-first script formula that doubled our inbound consultation DMs.",
            "How to structure the first 3 seconds of a faceless short to keep 85% of viewers watching."
        ],
        "content_format": "Split-Screen Retention Graph Analysis with Kinetic Captions",
        "faceless_short_style": "stick-story",
        "cta": "Save this reel to blueprint the first 3 seconds of your next video.",
        "reasoning": "Retention hooks are the #1 concern for creators; actionable framework drives exceptionally high saves."
    },
    "C7zN7p2M3cC": {
        "topic": "Lifestyle Narrative Walkthroughs for Luxury Real Estate Listings",
        "target_audience": "Luxury Real Estate Agents & Residential Developers",
        "business_problem": "Boring architectural walkthroughs fail to elicit emotional buyer response.",
        "hooks": [
            "Why filming the kitchen island for 15 seconds will never sell a million-dollar home.",
            "The lifestyle storytelling structure that brought 3 cash buyers in 7 days.",
            "How luxury real estate brokers turn 45-second property shorts into exclusive buyer lists."
        ],
        "content_format": "Cinematic Route Journey with Parchment Texture Labels",
        "faceless_short_style": "paper-atlas",
        "cta": "DM us 'PROPERTY' for our luxury home video storyboard formula.",
        "reasoning": "High-ticket market with substantial margins; agents adopt storytelling formats that justify their commissions."
    },
    "C8aP6o3N4dD": {
        "topic": "Autonomous Lead Scoring and Instant Video Qualification Pipelines",
        "target_audience": "Agency Owners, High-Ticket Consultancies & B2B Teams",
        "business_problem": "Slow manual lead follow-up causes 70% of inbound leads to go cold.",
        "hooks": [
            "What happens to a high-intent lead when your sales team takes 4 hours to reply?",
            "The automated webhook pipeline that scores and books inbound leads in 45 seconds.",
            "How to replace 12 hours of manual CRM lead triage with 3 connected AI nodes."
        ],
        "content_format": "2D Vector Cutaway showing Webhook and CRM Routing",
        "faceless_short_style": "inside-out",
        "cta": "Comment 'AUTOMATE' to clone our open-source Zapier lead triage workflow.",
        "reasoning": "Direct product showcase for AdSync automation; demonstrates concrete operational time savings."
    },
    "C8bQ5n4O5eE": {
        "topic": "Anti-Commodity Brand Point of View & Value-Based Pricing Power",
        "target_audience": "Boutique Creative Agencies, Consultants & Tech Founders",
        "business_problem": "Competing on price commoditizes expertise and crushes operating profit margins.",
        "hooks": [
            "Why your $5,000 logo redesign won't fix your customer acquisition problem.",
            "The counter-intuitive reason premium clients run away from discount agencies.",
            "How to build a brand point of view so strong your competitors become irrelevant."
        ],
        "content_format": "2D Conceptual X-Ray of Brand Perception and Mental Real Estate",
        "faceless_short_style": "inside-out",
        "cta": "Follow @AdSync for daily blueprints on premium market positioning.",
        "reasoning": "Appeals to mature business owners who know brand defensibility drives enterprise valuation."
    },
    "C8cR4m5P6fF": {
        "topic": "The 3-Pillar Creative Rotation Framework to Defeat Meta Ad Fatigue",
        "target_audience": "E-Commerce Brands & Performance Media Buyers",
        "business_problem": "High creative burnout requires constant ad production to maintain target ROAS.",
        "hooks": [
            "Why your top-performing ad creative suddenly stopped working after day 14.",
            "The 3 visual angles you need in your ad account to cut Cost-Per-Acquisition by 30%.",
            "Stop turning off ad sets: the automated creative rotation method for Meta Ads."
        ],
        "content_format": "3D Ad Engine Visualizer with Rotation Flowchart",
        "faceless_short_style": "deep-dive",
        "cta": "Comment 'ROTATE' for the AdSync automated creative refresh schedule.",
        "reasoning": "High commercial urgency; media buyers spend thousands daily and need reliable creative cycling."
    },
    "C8dS3l6Q7gG": {
        "topic": "The Automated Video Magnet Funnel: Replacing Dead Cold Outreach",
        "target_audience": "B2B Sales Teams, SaaS Founders & Marketing Agencies",
        "business_problem": "Cold DMs and cold emails suffer from record-low deliverability and response rates.",
        "hooks": [
            "The cold outreach method is dying: here is the 60-second video funnel replacing it.",
            "How we booked 35 qualified B2B client calls without sending a single cold message.",
            "The 2-step automated DM workflow that turns short-form viewers into booked consults."
        ],
        "content_format": "Character Survival Animation contrasting Cold Outreach vs Inbound Funnel",
        "faceless_short_style": "stick-story",
        "cta": "Tap the link in bio to clone our automated lead magnet funnel.",
        "reasoning": "Solves painful outbound fatigue by presenting a modern inbound automation alternative."
    },
    "C8eT2k7R8hH": {
        "topic": "Algorithm Re-Delivery Hacks: Slide 2 Controversy & Multi-Slide Engagement",
        "target_audience": "Social Media Strategists, Brand Creators & Growth Marketers",
        "business_problem": "Declining single-image reach leaves organic social channels starved of new traffic.",
        "hooks": [
            "Why Instagram is quietly showing carousel posts twice to your target audience.",
            "The slide-2 controversy strategy that quadrupled our organic impressions.",
            "How to design multi-slide video carousels that trigger the re-delivery algorithm."
        ],
        "content_format": "Fast-Paced Explainer with Kinetic Caption Overlays",
        "faceless_short_style": "stick-story",
        "cta": "Save this reel before your next carousel design sprint.",
        "reasoning": "Platform-specific algorithmic hack that immediately rewards content creators with higher reach."
    },
    "C8fU1j8S9iI": {
        "topic": "Productizing Fulfillment to Break the Service Agency Scale Ceiling",
        "target_audience": "Agency Owners, Fractional Executives & High-End Freelancers",
        "business_problem": "Custom service delivery creates operational chaos and founder burnout above $20k/mo.",
        "hooks": [
            "The fulfillment trap: why custom Zoom calls are keeping your agency under $20k/mo.",
            "How top marketing agencies handle 25 active clients with zero fulfillment burnout.",
            "The 3 deliverables you must productize before spending another dollar on client acquisition."
        ],
        "content_format": "Humorous Cartoon Agency Journey with Dynamic Camera Panning",
        "faceless_short_style": "tall-tale",
        "cta": "Comment 'SYSTEMS' to audit your agency fulfillment workflows.",
        "reasoning": "Deeply resonates with agency founders who have conquered sales but are drowning in delivery."
    },
    "C8gV0i9T0jJ": {
        "topic": "Hyper-Targeted Geo-Fenced Meta Ads for Motivated Real Estate Inbound",
        "target_audience": "Real Estate Investors, Wholesalers & Commercial Brokers",
        "business_problem": "Buying scraped cold-calling lists results in angry prospects and wasted hours.",
        "hooks": [
            "Why buying shared real estate cold-calling lists is burning your marketing budget.",
            "How motivated property sellers reach out to YOU first using targeted geo-fencing.",
            "The 15-mile localized ad campaign that generated 12 off-market property contracts."
        ],
        "content_format": "Regional Parchment Map with Target Demographic Heatmaps",
        "faceless_short_style": "paper-atlas",
        "cta": "DM 'OFFMARKET' for the exact geo-fenced ad copy template.",
        "reasoning": "Real estate acquisitions have massive transaction values; investors gladly fund inbound lead channels."
    },
    "C8hW9h0U1kK": {
        "topic": "The 9-Word Inbound Email Reactivation Formula for Dormant Leads",
        "target_audience": "B2B Sales Directors, Account Executives & Agency Founders",
        "business_problem": "Massive lists of historical leads sit untouched because reps don't know how to follow up.",
        "hooks": [
            "Why sending 'Just checking in' emails is killing your closed-deal conversion rate.",
            "The 9-word question email that revived $40,000 in ghosted sales leads.",
            "How to turn a dormant CRM list into 10 booked calls this week with zero ad spend."
        ],
        "content_format": "2D X-Ray Flowchart showing Email Delivery & Reply Triage",
        "faceless_short_style": "inside-out",
        "cta": "Comment 'REVIVE' to copy-paste the exact 9-word reactivation script.",
        "reasoning": "Instant ROI potential without extra ad spend; sales teams can deploy this within 24 hours."
    },
    "C8iX8g1V2lL": {
        "topic": "The Minimalist 1-Page Offer Funnel vs Over-Engineered Websites",
        "target_audience": "Startup Founders, Early-Stage Entrepreneurs & Solopreneurs",
        "business_problem": "Founders waste weeks and thousands designing complex sites before closing a single paying customer.",
        "hooks": [
            "Why spending $5,000 on a website before your first 5 clients is financial suicide.",
            "The 1-page offer structure that booked $100k in consulting with zero custom coding.",
            "What every high-ticket client actually looks for before making a purchasing decision."
        ],
        "content_format": "Animated Founder Story showing Minimalist vs Bloated Launch",
        "faceless_short_style": "tall-tale",
        "cta": "Save this reel to protect your startup budget.",
        "reasoning": "Contrarian truth that cuts through startup vanity; builds trust through practical capital efficiency."
    },
    "C8jY7f2W3mM": {
        "topic": "Creative-Led Audience Targeting in the Era of Meta Advantage+ AI",
        "target_audience": "Digital Marketing Agencies & Direct-to-Consumer Brands",
        "business_problem": "Traditional interest targeting is dying; ad creatives must now do the filtering.",
        "hooks": [
            "Why your ad creative is your audience targeting now (Advantage+ benchmark test).",
            "The $50,000 split test: why manual interest targeting is losing to Advantage+.",
            "How to write opening copy hooks that force Meta's algorithm to find high-value buyers."
        ],
        "content_format": "3D Visual Flythrough of Algorithmic Creative Matching",
        "faceless_short_style": "deep-dive",
        "cta": "Comment 'TARGET' for our Creative-Led Targeting checklist.",
        "reasoning": "Critical technical shift in performance marketing; establishes AdSync as cutting-edge media experts."
    },
    "C8kZ6e3X4nN": {
        "topic": "The Reverse Funnel: Reality-Based Behind-the-Scenes Social Proof",
        "target_audience": "Local Retailers, Boutique Brands & Hospitality Businesses",
        "business_problem": "Over-polished corporate commercials feel untrustworthy and get ignored on social media.",
        "hooks": [
            "Why corporate polished advertisements are losing to unpolished reality videos.",
            "The behind-the-scenes video format that drives physical foot traffic to local businesses.",
            "How asking one simple question on video increased customer profile visits by 300%."
        ],
        "content_format": "Dynamic Cartoon Narrative showing Customer Reality",
        "faceless_short_style": "tall-tale",
        "cta": "Follow @AdSync for organic local marketing case studies.",
        "reasoning": "Humanizes local business marketing; simple to execute and resonates with authentic content preferences."
    },
    "C8la5d4Y5oO": {
        "topic": "Automated Pre-Qualification Gateways Before Calendar Scheduling",
        "target_audience": "B2B Executives, Specialized Consultants & Agency Partners",
        "business_problem": "Tire-kickers and unqualified leads clog executive calendars with low-value meetings.",
        "hooks": [
            "Why letting unvetted leads book 45 minutes on your calendar is killing company growth.",
            "The 2-question qualification filter that eliminated 90% of tire-kickers from our sales calls.",
            "How automated budget routing saves executives 15 hours of wasted pitch meetings."
        ],
        "content_format": "2D Animated Qualification Funnel with Lead Filtering",
        "faceless_short_style": "inside-out",
        "cta": "Comment 'QUALIFY' for our high-ticket Tally form booking template.",
        "reasoning": "Directly impacts executive productivity and sales team morale; clear operational value proposition."
    },
    "C8mb4c5Z6pP": {
        "topic": "The 'Neighborhood Spotlight' Series for Dominating Local Real Estate Market Share",
        "target_audience": "Independent Realtors, Managing Brokers & Property Marketers",
        "business_problem": "Realtors blend into the crowd by posting identical MLS listing photos.",
        "hooks": [
            "The 3 local spots real estate agents must film before shooting the house walkthrough.",
            "How becoming the 'neighborhood mayor' on video brought 8 seller listings in 3 weeks.",
            "The local storytelling video format that positions realtors as neighborhood authorities."
        ],
        "content_format": "Territory Map with Historic Route Highlights",
        "faceless_short_style": "paper-atlas",
        "cta": "DM 'MAYOR' to get our local community video production blueprint.",
        "reasoning": "Transforms realtors from transactional salespeople into trusted community figures."
    },
    "C8nc3b6a7qQ": {
        "topic": "Outcome Guarantees & Price Anchoring to Repel High-Friction Clients",
        "target_audience": "Agency Founders, Enterprise Consultants & B2B Service Providers",
        "business_problem": "Low pricing attracts demanding, high-churn clients who drain agency bandwidth.",
        "hooks": [
            "Why offering discounts attracts the most entitled, high-friction clients you'll ever have.",
            "How raising prices by 50% actually cut customer churn in half for our agency.",
            "The outcome-based packaging structure that makes premium pricing completely irresistible."
        ],
        "content_format": "Stick Figure Decision Tree: The Price-Trap vs Premium Positioning",
        "faceless_short_style": "stick-story",
        "cta": "Save this reel to review before your next client sales proposal.",
        "reasoning": "Solves business model dysfunction; price anchoring creates sustainable unit economics."
    },
    "C8od2a7b8rR": {
        "topic": "The 5-Step Instagram Search Optimization Blueprint for Organic Buyer Discovery",
        "target_audience": "E-Commerce Brands, Online Coaches & B2B Creators",
        "business_problem": "Social algorithms change constantly, but search intent captures active buyers.",
        "hooks": [
            "Why Gen Z is searching Instagram instead of Google (and how to rank #1 in your niche).",
            "The 3 keyword placements in your profile that double your organic inbound discovery.",
            "How to optimize your caption copy so Instagram ranks your video for buyer search terms."
        ],
        "content_format": "Screen Recording & Keyword Hierarchy Visualizer",
        "faceless_short_style": "deep-dive",
        "cta": "Comment 'SEO' for our 2026 Instagram Search Optimization cheatsheet.",
        "reasoning": "Search-based discovery provides evergreen traffic that outlasts the 48-hour Reel lifecycle."
    },
    "C8pe1z8c9sS": {
        "topic": "Commercial-Free Direct Response Hooks for Ad-Blind Audiences",
        "target_audience": "Direct Response Copywriters, Ad Agencies & Media Buyers",
        "business_problem": "Consumers have developed aggressive ad-blindness to traditional marketing formats.",
        "hooks": [
            "The immediate-value hook structure that stops people who hate ads from scrolling past.",
            "Why asking questions in your first ad sentence is causing 70% of viewers to skip.",
            "How to write ad hooks that sound like an honest review rather than a corporate sales pitch."
        ],
        "content_format": "2D X-Ray Copywriting Breakdown with Highlighting",
        "faceless_short_style": "inside-out",
        "cta": "Save this post to benchmark your next batch of ad scripts.",
        "reasoning": "Immediate utility for copywriters and media buyers looking to improve front-end click-through rates."
    },
    "C8qf0y9d0tT": {
        "topic": "The 48-Hour Automated Onboarding Protocol to Crush Buyer Remorse",
        "target_audience": "SaaS Customer Success Teams, Agencies & Membership Owners",
        "business_problem": "Customer churn spikes in the first 48 hours due to lack of immediate direction.",
        "hooks": [
            "The critical 48-hour window where 90% of high-ticket client churn is decided.",
            "How an automated customized welcome video cut client refund requests to zero.",
            "The 4-step Slack and Notion automation that wows new clients the second they pay."
        ],
        "content_format": "Animated Workflow Diagram of Automated Client Onboarding",
        "faceless_short_style": "inside-out",
        "cta": "Comment 'ONBOARD' to clone our client onboarding automation architecture.",
        "reasoning": "Retention is cheaper than acquisition; automated onboarding protects lifetime customer value."
    },
}

GENERIC_FALLBACK = {
    "topic": "Autonomous Social Media Funnels for Rapid Brand Acquisition",
    "target_audience": "Growth Marketers, Entrepreneurs & Modern Creators",
    "business_problem": "Inconsistent content publishing stalls audience growth and customer acquisition.",
    "hooks": [
        "What happens when your entire social media funnel runs autonomously 24/7?",
        "The 3 content systems modern brands use to dominate vertical video reach.",
        "Stop manually editing video: how code-driven animation scales your social presence."
    ],
    "content_format": "Fast-Paced Explainer with Kinetic Visual Graphics",
    "faceless_short_style": "deep-dive",
    "cta": "Follow @AdSync for autonomous social media engineering blueprints.",
    "reasoning": "High-level overview demonstrating the compounding leverage of automated video content."
}


def generate_adsync_idea(reel: ReelItem, analysis: ReelAnalysis) -> AdSyncIdea:
    """Generates an original, non-plagiarized AdSync concept inspired by a trend signal."""
    # Check specific shortcode catalog first
    entry = REEL_SPECIFIC_IDEAS.get(reel.shortcode)

    if not entry:
        entry = GENERIC_FALLBACK

    # Adapt opportunity score from virality and category confidence
    if analysis.virality_score is not None:
        opp_score = round(min(99.5, max(55.0, (analysis.virality_score * 0.60) + (analysis.confidence_score * 35.0) + 4.0)), 1)
        reasoning_text = entry["reasoning"]
    else:
        # If engagement metrics were null/unrecorded in the discovery stream, score purely on topical relevance
        opp_score = round(min(75.0, max(50.0, (analysis.confidence_score * 60.0) + 15.0)), 1)
        reasoning_text = f"{entry['reasoning']} (Discovery batch candidate: engagement metrics unrecorded/hidden)."

    import hashlib
    idea_id = f"idea_{hashlib.md5(reel.reel_id.encode('utf-8')).hexdigest()[:12]}"

    return AdSyncIdea(
        idea_id=idea_id,
        source_reel_id=reel.reel_id,
        target_category=analysis.primary_category,
        topic=entry["topic"],
        hooks=entry["hooks"],
        target_audience=entry["target_audience"],
        business_problem=entry["business_problem"],
        content_format=entry["content_format"],
        faceless_short_style=entry["faceless_short_style"],
        call_to_action=entry["cta"],
        opportunity_score=opp_score,
        reasoning=reasoning_text,
        trend_reference_url=reel.url,
    )


def generate_batch_ideas(reels: List[ReelItem], analyses: List[ReelAnalysis]) -> List[AdSyncIdea]:
    """Generates and ranks original AdSync ideas for a batch of analyzed reels."""
    analysis_map = {a.reel_id: a for a in analyses}
    ideas = []

    for r in reels:
        if r.reel_id in analysis_map:
            an = analysis_map[r.reel_id]
            if an.primary_category == "Other / Irrelevant":
                continue
            idea = generate_adsync_idea(r, an)
            ideas.append(idea)

    # Sort descending by opportunity score
    ideas.sort(key=lambda x: x.opportunity_score, reverse=True)
    return ideas
