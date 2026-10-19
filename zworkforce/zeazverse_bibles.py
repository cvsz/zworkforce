"""Canonical Character Bibles and Brand Definition for ZEAZVERSE."""

from __future__ import annotations
from typing import Any

ZEAZVERSE_BRAND = {
    "name": "ZEAZVERSE",
    "tagline": "Four Souls. One Universe.",
    "preferred_handle": "@ZEAZVERSE",
    "description": "Original AI cinematic stories and virtual idols from Thailand. Featuring LALIN, NICHA, PIM, and YADA.",
    "primary_language": "en",
    "target_audience": "Global English-speaking viewers with Thai localization",
    "palette": {
        "electric_purple": "#8B5CF6",
        "neon_magenta": "#EC4899",
        "cyber_blue": "#06B6D4",
        "midnight_navy": "#070B1D",
        "soft_white": "#F8FAFC",
    },
    "brand_personality": [
        "Futuristic",
        "Cinematic",
        "Creative",
        "Sophisticated",
        "Original",
        "Energetic",
        "International",
        "Thai-inspired",
    ],
    "assets": {
        "logo_svg": '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="zv" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#8B5CF6"/><stop offset="50%" stop-color="#EC4899"/><stop offset="100%" stop-color="#06B6D4"/></linearGradient></defs><polygon points="50,5 95,90 5,90" fill="none" stroke="url(#zv)" stroke-width="8"/><circle cx="50" cy="55" r="16" fill="#8B5CF6"/></svg>',
        "banner_spec": {"width": 2560, "height": 1440, "safe_area": "1546x423"},
        "watermark_spec": {"position": "bottom-right", "opacity": 0.75, "size": "150x150"},
    },
}

GLOBAL_NEGATIVE_PROMPT = (
    "unwanted facial identity changes, costume drift, incorrect anatomy, extra fingers, "
    "extra limbs, broken hands, floating objects, unnatural physical motion, temporal flicker, "
    "missing accessories, inconsistent lighting, distorted backgrounds, accidental text artifacts, "
    "unexpected characters, unrequested logos, child, minor, underage"
)

CANONICAL_CHARACTERS: dict[str, dict[str, Any]] = {
    "lalin": {
        "id": "lalin",
        "name": "LALIN",
        "archetype": "The Dreamer",
        "age": 22,
        "nationality": "Thai",
        "appearance": {
            "gender": "Adult Thai woman",
            "hair": "Long dark high ponytail, wispy bangs",
            "face": "Natural Thai facial features, gentle expressive almond dark-brown eyes, subtle natural makeup",
            "skin": "Warm light-medium Thai skin tone",
            "body": "Athletic slim, 168cm",
        },
        "costume": {
            "top": "White fitted futuristic compression top",
            "jacket": "Reflective silver-white tech jacket with luminous purple circuit piping",
            "bottom": "Black cyberpunk shorts",
            "footwear": "White-black futuristic high-top boots",
            "accessories": ["Utility straps with purple glowing clip", "Holographic dreamer pendant"],
        },
        "personality": {
            "traits": ["Creative", "Compassionate", "Curious", "Mysterious"],
            "speech_style": "Soft-spoken yet confident, poetic cadence, inquisitive tone",
        },
        "story_themes": [
            "Dream worlds",
            "Mystery",
            "Supernatural discovery",
            "Emotional adventures",
            "Alternative dimensions",
        ],
        "voice_profile": {
            "provider": "mock",
            "model": "zv-tts-lalin-v1",
            "style": "melodic, gentle, articulate English with faint Bangkok lilt",
            "pitch": 1.05,
            "speed": 0.98,
        },
        "consistency_rules": {
            "immutable": [
                "Facial identity and eye shape",
                "High ponytail hairstyle with wispy bangs",
                "Silver-white tech jacket and dreamer pendant",
                "Warm natural Thai complexion",
            ],
            "turnaround_views": ["front", "left_45", "left_profile", "back", "right_profile", "right_45"],
        },
    },
    "nicha": {
        "id": "nicha",
        "name": "NICHA",
        "archetype": "The Strategist",
        "age": 24,
        "nationality": "Thai",
        "appearance": {
            "gender": "Adult Thai woman",
            "hair": "Sleek long dark high ponytail without bangs, sharply pulled back",
            "face": "Natural Thai facial features, sharp focused dark eyes, minimalist clean makeup",
            "skin": "Golden tan Thai skin tone",
            "body": "Fit tactical stature, 172cm",
        },
        "costume": {
            "top": "Gray fitted tactical compression top",
            "jacket": "Dark graphite tactical jacket with cyber-blue accents and structured shoulders",
            "bottom": "Black utility cargo trousers with reinforced knee plating",
            "footwear": "Heavy black futuristic combat boots",
            "accessories": ["Tactical harness details", "Wrist comm-device with cyan readout"],
        },
        "personality": {
            "traits": ["Intelligent", "Disciplined", "Analytical", "Determined"],
            "speech_style": "Direct, measured, concise, authoritative tactical delivery",
        },
        "story_themes": [
            "Cyber missions",
            "Technology & security",
            "Investigations",
            "Strategic operations",
            "Sci-fi action",
        ],
        "voice_profile": {
            "provider": "mock",
            "model": "zv-tts-nicha-v1",
            "style": "composed, crisp, decisive cadence",
            "pitch": 0.95,
            "speed": 1.02,
        },
        "consistency_rules": {
            "immutable": [
                "Facial identity and focused gaze",
                "Sleek ponytail without bangs",
                "Tactical harness and wrist comm",
                "Dark tactical jacket with cyber-blue trim",
            ],
            "turnaround_views": ["front", "left_45", "left_profile", "back", "right_profile", "right_45"],
        },
    },
    "pim": {
        "id": "pim",
        "name": "PIM",
        "archetype": "The Rebel",
        "age": 21,
        "nationality": "Thai",
        "appearance": {
            "gender": "Adult Thai woman",
            "hair": "Short dark-brown edgy bob haircut with textured layers",
            "face": "Natural Thai facial features, vibrant daring gaze, subtle crimson eyeliner accent",
            "skin": "Warm honey Thai skin tone",
            "body": "Agile athletic gymnast build, 165cm",
        },
        "costume": {
            "top": "Deep-red fitted crop tech top",
            "jacket": "Black tactical streetwear bomber jacket with neon-magenta lining",
            "bottom": "Black techwear shorts with drop straps",
            "footwear": "Black platform combat boots with red laces",
            "accessories": ["Multi-utility belt", "Fingerless tactical gloves", "Asymmetric ear cuff"],
        },
        "personality": {
            "traits": ["Fearless", "Energetic", "Spontaneous", "Confident"],
            "speech_style": "Dynamic, witty, punchy, bold conversational style",
        },
        "story_themes": [
            "High-stakes action",
            "Street adventure",
            "Martial arts & parkour",
            "Underground challenges",
            "High-energy stunts",
        ],
        "voice_profile": {
            "provider": "mock",
            "model": "zv-tts-pim-v1",
            "style": "punchy, charismatic, bright energetic timbre",
            "pitch": 1.02,
            "speed": 1.06,
        },
        "consistency_rules": {
            "immutable": [
                "Facial identity and vibrant smirk",
                "Short textured bob haircut",
                "Deep-red top and neon-magenta bomber lining",
                "Fingerless gloves and platform boots",
            ],
            "turnaround_views": ["front", "left_45", "left_profile", "back", "right_profile", "right_45"],
        },
    },
    "yada": {
        "id": "yada",
        "name": "YADA",
        "archetype": "The Visionary",
        "age": 23,
        "nationality": "Thai",
        "appearance": {
            "gender": "Adult Thai woman",
            "hair": "Ash-blonde shoulder-length sleek hair with subtle wave",
            "face": "Natural Thai facial features, contemplative amber-brown eyes, elegant luminous makeup",
            "skin": "Fair porcelain-warm Thai skin tone",
            "body": "Graceful poised silhouette, 170cm",
        },
        "costume": {
            "top": "Structured white high-collar tech top",
            "jacket": "Black tailored futuristic coat with iridescent lapels",
            "bottom": "Black tailored cargo trousers with geometric seam lines",
            "footwear": "Black sleek futuristic boots with low geometric heel",
            "accessories": ["Minimalist utility straps", "Quantum interface ring on index finger"],
        },
        "personality": {
            "traits": ["Inventive", "Elegant", "Ambitious", "Imaginative"],
            "speech_style": "Articulate, visionary, calm intellectual enthusiasm",
        },
        "story_themes": [
            "Future technology",
            "Creative invention",
            "Cosmic exploration",
            "Fantasy sci-fi synthesis",
            "Next-gen architecture",
        ],
        "voice_profile": {
            "provider": "mock",
            "model": "zv-tts-yada-v1",
            "style": "warm, silky, sophisticated intellectual tone",
            "pitch": 0.98,
            "speed": 0.99,
        },
        "consistency_rules": {
            "immutable": [
                "Facial identity and contemplative expression",
                "Ash-blonde shoulder-length hair",
                "Structured white top and black iridescent coat",
                "Quantum interface ring",
            ],
            "turnaround_views": ["front", "left_45", "left_profile", "back", "right_profile", "right_45"],
        },
    },
}

CHANNEL_SETUP_STEPS = [
    {"id": "step_01", "name": "Secure Google account ownership", "category": "security"},
    {"id": "step_02", "name": "Enable multi-factor authentication", "category": "security"},
    {"id": "step_03", "name": "Create YouTube channel through authorized user flow", "category": "channel"},
    {"id": "step_04", "name": "Confirm channel ID and actual handle", "category": "channel"},
    {"id": "step_05", "name": "Upload branding assets (avatar, banner, watermark)", "category": "branding"},
    {"id": "step_06", "name": "Configure channel description", "category": "branding"},
    {"id": "step_07", "name": "Configure country and language", "category": "settings"},
    {"id": "step_08", "name": "Configure audience settings (not Made for Kids)", "category": "settings"},
    {"id": "step_09", "name": "Complete channel feature eligibility requirements", "category": "features"},
    {"id": "step_10", "name": "Configure upload defaults (private by default)", "category": "publishing"},
    {"id": "step_11", "name": "Configure playlists for series", "category": "content"},
    {"id": "step_12", "name": "Configure channel homepage layout", "category": "branding"},
    {"id": "step_13", "name": "Configure team permissions", "category": "governance"},
    {"id": "step_14", "name": "Configure moderation and community settings", "category": "community"},
    {"id": "step_15", "name": "Verify publishing capabilities with private upload", "category": "verification"},
]

PUBLISHING_STATES = [
    "IDEA",
    "SCRIPT_APPROVED",
    "ASSETS_READY",
    "RENDERING",
    "RENDERED",
    "QA_PENDING",
    "QA_PASSED",
    "READY_FOR_REVIEW",
    "APPROVED",
    "UPLOADING",
    "PRIVATE_UPLOADED",
    "PUBLISHED",
    "FAILED",
    "CANCELLED",
    "BLOCKED",
]

CONTENT_CLASSES = [
    "Character Introduction",
    "Cinematic Action",
    "Fantasy Adventures",
    "Cyberpunk Stories",
    "Martial Arts",
    "Comedy Shorts",
    "Character Relationships",
    "Sci-Fi Exploration",
    "AI Filmmaking Behind the Scenes",
    "Original Serialized Episodes",
]
