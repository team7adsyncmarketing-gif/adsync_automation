-- =====================================================================
-- AdSync Control Center — Production Schema for Supabase PostgreSQL
-- =====================================================================

-- 1. Discovered Instagram Reels
CREATE TABLE IF NOT EXISTS public.reels (
    reel_id TEXT PRIMARY KEY,
    shortcode TEXT,
    url TEXT,
    caption TEXT,
    author_username TEXT,
    author_full_name TEXT,
    play_count BIGINT DEFAULT 0,
    like_count BIGINT DEFAULT 0,
    comment_count BIGINT DEFAULT 0,
    share_count BIGINT DEFAULT 0,
    hashtags TEXT,
    audio_id TEXT,
    audio_title TEXT,
    audio_artist TEXT,
    is_original_audio BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    is_mock BOOLEAN DEFAULT FALSE,
    raw_json JSONB
);

-- 2. Scored Reel Analyses
CREATE TABLE IF NOT EXISTS public.reel_analyses (
    reel_id TEXT PRIMARY KEY REFERENCES public.reels(reel_id) ON DELETE CASCADE,
    primary_category TEXT,
    confidence_score DOUBLE PRECISION,
    hook_text TEXT,
    hook_type TEXT,
    hook_psychology TEXT,
    content_format TEXT,
    virality_score DOUBLE PRECISION,
    analyzed_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. AdSync AI Marketing Concepts
CREATE TABLE IF NOT EXISTS public.adsync_ideas (
    idea_id TEXT PRIMARY KEY,
    source_reel_id TEXT REFERENCES public.reels(reel_id) ON DELETE SET NULL,
    target_category TEXT NOT NULL,
    topic TEXT NOT NULL,
    hooks TEXT,
    target_audience TEXT,
    business_problem TEXT,
    content_format TEXT,
    faceless_short_style TEXT,
    call_to_action TEXT,
    opportunity_score DOUBLE PRECISION,
    reasoning TEXT,
    trend_reference_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Tracked Competitors
CREATE TABLE IF NOT EXISTS public.competitors (
    handle TEXT PRIMARY KEY,
    category TEXT,
    display_name TEXT,
    bio TEXT,
    avatar_url TEXT,
    verified BOOLEAN DEFAULT FALSE,
    is_private BOOLEAN DEFAULT FALSE,
    follower_count BIGINT DEFAULT 0,
    following_count BIGINT DEFAULT 0,
    posts_count INTEGER DEFAULT 0,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    last_fetched_at TIMESTAMPTZ,
    notes TEXT
);

-- 5. Competitor Reel Snapshots
CREATE TABLE IF NOT EXISTS public.competitor_reel_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    competitor_handle TEXT REFERENCES public.competitors(handle) ON DELETE CASCADE,
    reel_id TEXT,
    shortcode TEXT,
    views BIGINT DEFAULT 0,
    likes BIGINT DEFAULT 0,
    comments BIGINT DEFAULT 0,
    taken_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Video Catalog & Approval Gate
CREATE TABLE IF NOT EXISTS public.video_catalog (
    video_id TEXT PRIMARY KEY,
    video_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    storage_url TEXT,
    title TEXT NOT NULL,
    topic TEXT,
    style TEXT,
    caption TEXT,
    hashtags_json TEXT,
    approved INTEGER DEFAULT 0,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Publication Ledger
CREATE TABLE IF NOT EXISTS public.reel_publications (
    publication_id TEXT PRIMARY KEY,
    video_path TEXT NOT NULL,
    caption TEXT,
    hashtags_json TEXT,
    creation_id TEXT,
    post_id TEXT,
    permalink TEXT,
    status TEXT DEFAULT 'PENDING',
    is_dry_run INTEGER DEFAULT 1,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Cloud Render Jobs Queue
CREATE TABLE IF NOT EXISTS public.render_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, PROCESSING, COMPLETED, FAILED
    topic TEXT NOT NULL,
    style TEXT DEFAULT 'stick-story',
    voice TEXT DEFAULT 'am_puck',
    music TEXT DEFAULT 'bed',
    speed DOUBLE PRECISION DEFAULT 1.0,
    video_id TEXT,
    video_name TEXT,
    video_url TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (RLS) but allow service_role access
ALTER TABLE public.reels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reel_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.adsync_ideas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.competitors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.video_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reel_publications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.render_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow service_role full access on reels" ON public.reels FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service_role full access on analyses" ON public.reel_analyses FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service_role full access on ideas" ON public.adsync_ideas FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service_role full access on competitors" ON public.competitors FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service_role full access on catalog" ON public.video_catalog FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service_role full access on publications" ON public.reel_publications FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service_role full access on render_jobs" ON public.render_jobs FOR ALL USING (auth.role() = 'service_role');
