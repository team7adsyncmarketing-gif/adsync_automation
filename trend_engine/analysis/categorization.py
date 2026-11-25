"""Categorization engine for mapping Instagram trends into target marketing niches."""

import re
from typing import Dict, Tuple, List
from ..storage.models import ReelItem

# Taxonomy mapping with keyword weights
CATEGORY_TAXONOMY: Dict[str, Dict[str, float]] = {
    "Meta Ads": {
        "metaads": 3.0, "facebookads": 3.0, "instagramads": 3.0, "roas": 2.5,
        "adcreative": 2.5, "mediabuying": 2.5, "cpa": 2.0, "advantage+": 2.5,
        "adspend": 2.0, "cpm": 2.0, "adsmanager": 2.5, "adhooks": 2.0,
        "creativefatigue": 2.5, "retargeting": 2.0, "lookalike": 2.0,
    },
    "Instagram Marketing": {
        "instagrammarketing": 3.0, "reelsgrowth": 2.5, "algorithmhack": 2.5,
        "socialmediatips": 2.0, "carousel": 2.0, "instagramseo": 2.5,
        "hookstrategy": 2.0, "profileoptimization": 2.0, "reelsreach": 2.0,
        "stories": 1.5, "engagementrate": 2.0, "contentcreator": 1.5,
    },
    "Lead Generation": {
        "leadgeneration": 3.0, "leadgen": 3.0, "inboundleads": 2.5,
        "coldoutreach": 2.0, "salesfunnels": 2.5, "bookedcalls": 2.5,
        "colddm": 2.0, "prospecting": 2.0, "leadmagnet": 2.5,
        "appointmentsetting": 2.5, "qualifiedleads": 2.5, "salespipeline": 2.0,
    },
    "Marketing Automation": {
        "marketingautomation": 3.0, "crmautomation": 3.0, "aiagents": 2.5,
        "manychat": 2.5, "zapier": 2.5, "makecom": 2.5, "webhooks": 2.0,
        "onboardingautomation": 2.5, "emailautomation": 2.0, "workflows": 2.0,
        "churnreduction": 2.0, "systemization": 2.0, "operations": 1.5,
    },
    "Branding": {
        "branding": 3.0, "brandstrategy": 3.0, "brandidentity": 2.5,
        "positioning": 2.5, "brandvoice": 2.0, "storytelling": 2.0,
        "authoritybuilding": 2.0, "premiumpricing": 2.0, "brandpromise": 2.5,
    },
    "Business Growth": {
        "businessgrowth": 3.0, "scalingbusiness": 2.5, "entrepreneurship": 2.0,
        "agencylife": 2.0, "pricingstrategy": 2.5, "startupstrategy": 2.0,
        "b2bsales": 2.0, "operationscale": 2.0, "productization": 2.5,
    },
    "Real Estate Marketing": {
        "realestatemarketing": 3.5, "realtorlife": 3.0, "propertyvideo": 3.0,
        "luxuryrealestate": 2.5, "localrealtor": 2.5, "listingappointments": 3.0,
        "wholesalinghouses": 2.5, "homeowners": 2.0, "neighborhoodspotlight": 2.5,
    },
    "Digital Marketing": {
        "digitalmarketing": 2.5, "marketingstrategy": 2.0, "seo": 2.5,
        "conversionrate": 2.0, "funnels": 2.0, "contentstrategy": 2.0,
        "growthhacking": 2.0, "attribution": 2.0, "omnichannel": 2.0,
    },
}


def classify_reel_category(reel: ReelItem) -> Tuple[str, float]:
    """Classifies a Reel into one of the 8 target marketing niches with a confidence score."""
    text_corpus = f"{reel.caption.lower()} {' '.join(reel.hashtags)} {reel.author_username.lower()}"
    words = re.findall(r"[a-z0-9\+\_]+", text_corpus)
    word_set = set(words)

    scores: Dict[str, float] = {cat: 0.0 for cat in CATEGORY_TAXONOMY}

    for cat, keywords in CATEGORY_TAXONOMY.items():
        for kw, weight in keywords.items():
            if kw in word_set or kw in text_corpus:
                scores[cat] += weight

    best_cat = max(scores, key=scores.get)
    max_score = scores[best_cat]

    if max_score < 1.0:
        return "Other / Irrelevant", 0.0

    # Normalize confidence between 0.4 and 0.98
    total_score = sum(scores.values())
    confidence = min(0.98, max(0.40, round(max_score / (total_score + 1.0) + (max_score * 0.05), 2)))
    return best_cat, confidence

