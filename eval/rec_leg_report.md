# REC-LEG-001/002 — legacy Bedrock vs. new LangGraph engine

Generated: 2026-07-25T15:39:52.958660+00:00

**Read before trusting track-level numbers:** the new engine's provider search is still fixture-backed until Phase 5, so track identity/diversity/playable-rate columns for the new engine are not yet meaningful — see the module docstring. Latency, cost, retrieval grounding, and explanation prose ARE meaningful today.

## Per-prompt results

| id | category | new latency (ms) | new cost (USD) | new tracks | new artists |
|---|---|---|---|---|---|
| mood-en-1 | mood-based discovery | 21004.0 | 0.003841 | 10 | Cosmic Lounge Flight, EHRLING, JAZZTRONICAL, Parov Stelar, SPACE AGE TIKI LOUNGE, Thorin's Side, Upbeat Nu Jazz & Electro Jazz 2026, 🌴 Santorini ‘66, 🎧 LOUNGE, 🚀Marimbas on the Moon! Tiki Lounge Exotica |
| mood-he-1 | mood-based discovery | 23128.3 | 0.003959 | 5 | DROWN WITH ME, EBM Music Mix, Hypnotic Dark Resurrection, Industrial Goth Rock, The Enigma TNG |
| blend-1 | blended genres | 19669.1 | 0.003484 | 10 | Blue Suit Blues, EHRLING, JAZZTRONICAL, Parov Stelar, SMOOTH JAZZ & SOUL, Smooth Jazz & R&B 90s, Smooth Jazz & Relaxing Instrumentals, Smooth Jazz Saxophone Music, Thorin's Side, Upbeat Nu Jazz & Electro Jazz 2026 |
| artist-1 | exact artist name | 18145.4 | 0.003211 | 10 | Best Trance 2026 🚀, Best Trance Mix 2026, Broken Focus, Devotos Do Odio, Kato & Jon, Minor Threat, The Exploited, The Offspring, Uplifting Trance Energy 2025, ♫ Best Uplifting Trance Mix |
| genre-1 | exact genre name | 17296.2 | 0.002953 | 10 | Afro House 2026, Deep Melodies #1, Fatso 98, Magic Club, Rosetta D33P | 2026 | MR SHANE | BUDDYNICE, Summer Mix 2026 #8, TOP Tech House DJ Mix 🎵, Tech House Mix, ✨ Tech House Mix, 🍒 Tech House & Bass House 2026 |
| anti-echo-1 | anti-echo-chamber | 17484.4 | 0.002695 | 5 | CocoRosie •ั Villain (Folkadelphia Session, Devendra Banhart, Exploring Contemporary Rock: From Origins to Influence, Weird Brother, 🤍 Devendra Banhart |
| negative-1 | negative constraints | 17851.6 | 0.003135 | 10 | 70s Disco Hits 🪩 Non-Stop Classics That Never Get Old, Bopp!, DJ Destruction, Disco Mix 1, Golden Disco Era, Koenjiblues, Rain Parade |
| genre-he-1 | exact genre name | 21984.7 | 0.004249 | 5 | DROWN WITH ME, EBM Music Mix, Hypnotic Dark Resurrection, Industrial Goth Rock, The Enigma TNG |
| mood-era-1 | mood-based discovery | 17819.5 | 0.003176 | 10 | Eileen Noise, Grunge (Official Visualizer), MAGNETIC FLY, My Own Podcast, Nirvana, Post-Grunge Playlist (1 Hour), Rock N Replay, Rokko Ca$h, VM Music Channel, Xirdeh |
| blend-2 | blended genres | 16919.1 | 0.002687 | 8 | ADA DYER, Asool, Bomfunk MC's, Freestyle, Mix Freestyle, ONSTAGE Band, SymphoBreaks |
| vague-1 | mood-based discovery | 19517.5 | 0.003270 | 10 | Best Of EDM 2010, Classic Soul Blues Treasures 🎙, EDM Mashup Mix 2026 | Best Mashups & Remixes of Popular Songs, Gaither, Billy Preston, Golden Soul Blues Café ☕, La Bamba (EDM Dance House Remix), TOP Tech House DJ Mix 🎵, Yaman Khadzi | Selected Mix 2024 | Deep House Mix 2024 | Ibiza, 🎧 RAGTIME, 🎧 TRADITIONAL GOSPEL: BLUE NOTE: GOSPEL & PIONEERS Top Hits from 1880 to Today 🎶 |
| negative-2 | negative constraints | 18677.8 | 0.003424 | 10 | Cosmic Lounge Flight, DROWN WITH ME, EBM Music Mix, Hypnotic Dark Resurrection, Industrial Goth Rock, SPACE AGE TIKI LOUNGE, The Enigma TNG, 🌴 Santorini ‘66, 🎧 LOUNGE, 🚀Marimbas on the Moon! Tiki Lounge Exotica |

## Summary

- Prompts run: 12
- New engine: unique artists across all prompts: 78 (70s Disco Hits 🪩 Non-Stop Classics That Never Get Old, ADA DYER, Afro House 2026, Asool, Best Of EDM 2010, Best Trance 2026 🚀, Best Trance Mix 2026, Blue Suit Blues, Bomfunk MC's, Bopp!, Broken Focus, Classic Soul Blues Treasures 🎙, CocoRosie •ั Villain (Folkadelphia Session, Cosmic Lounge Flight, DJ Destruction, DROWN WITH ME, Deep Melodies #1, Devendra Banhart, Devotos Do Odio, Disco Mix 1, EBM Music Mix, EDM Mashup Mix 2026 | Best Mashups & Remixes of Popular Songs, EHRLING, Eileen Noise, Exploring Contemporary Rock: From Origins to Influence, Fatso 98, Freestyle, Gaither, Billy Preston, Golden Disco Era, Golden Soul Blues Café ☕, Grunge (Official Visualizer), Hypnotic Dark Resurrection, Industrial Goth Rock, JAZZTRONICAL, Kato & Jon, Koenjiblues, La Bamba (EDM Dance House Remix), MAGNETIC FLY, Magic Club, Minor Threat, Mix Freestyle, My Own Podcast, Nirvana, ONSTAGE Band, Parov Stelar, Post-Grunge Playlist (1 Hour), Rain Parade, Rock N Replay, Rokko Ca$h, Rosetta D33P | 2026 | MR SHANE | BUDDYNICE, SMOOTH JAZZ & SOUL, SPACE AGE TIKI LOUNGE, Smooth Jazz & R&B 90s, Smooth Jazz & Relaxing Instrumentals, Smooth Jazz Saxophone Music, Summer Mix 2026 #8, SymphoBreaks, TOP Tech House DJ Mix 🎵, Tech House Mix, The Enigma TNG, The Exploited, The Offspring, Thorin's Side, Upbeat Nu Jazz & Electro Jazz 2026, Uplifting Trance Energy 2025, VM Music Channel, Weird Brother, Xirdeh, Yaman Khadzi | Selected Mix 2024 | Deep House Mix 2024 | Ibiza, ♫ Best Uplifting Trance Mix, ✨ Tech House Mix, 🌴 Santorini ‘66, 🍒 Tech House & Bass House 2026, 🎧 LOUNGE, 🎧 RAGTIME, 🎧 TRADITIONAL GOSPEL: BLUE NOTE: GOSPEL & PIONEERS Top Hits from 1880 to Today 🎶, 🚀Marimbas on the Moon! Tiki Lounge Exotica, 🤍 Devendra Banhart)
- New engine: total measured cost across 12 call(s): $0.040084 (avg $0.003340/call)
- Legacy leg was skipped (`--new-only`). Re-run without it once Bedrock credentials are available (see plan doc).

## Raw responses

### mood-en-1 — I need something warm and cozy for a rainy afternoon.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 21004.0,
  "playlist_title": "Rainy Afternoon Reverie",
  "playlist_description": "Sink into comfort with vintage lounge, space-age pop, and nu-jazz—the perfect soundtrack for a cozy, contemplative afternoon. These tracks create that warm, unhurried atmosphere that makes rain outside feel like a natural part of the moment.",
  "tracks": [
    {
      "title": "60's Exotica Jazz Cocktail Lounge Music",
      "artist": "SPACE AGE TIKI LOUNGE",
      "reasoning": "Exotica lounge from the 1960s is built for exactly this mood—relaxed, atmospheric cocktail jazz that wraps around you without demanding attention."
    },
    {
      "title": "1960s Space Age Pop",
      "artist": "Cosmic Lounge Flight",
      "reasoning": "Space Age Pop brings that retro glamour and warmth, with the kind of sophisticated instrumentation that feels like settling into a comfortable chair."
    },
    {
      "title": "Don't Confuse Nu-Jazz with Jazz (Music)",
      "artist": "Thorin's Side",
      "reasoning": "A playful nu-jazz track with electronic textures and soothing ambient layers—perfect for daydreaming on a quiet afternoon."
    },
    {
      "title": "The Princess (2012) nu-jazz | electronic | downtempo | electro-swing | acid jazz",
      "artist": "Parov Stelar",
      "reasoning": "Parov Stelar's downtempo nu-jazz has that smooth, enveloping quality that modern electronic production brings to traditional jazz warmth."
    },
    {
      "title": "Retro Vintage Tiki Lounge Exotica | 60s Lounge Background Music | Space-Age Pop🗿🍸",
      "artist": "🌴 Santorini ‘66",
      "reasoning": "Another slice of vintage tiki lounge exotica that captures the cozy, retro-tinged comfort of background music designed to put you at ease."
    },
    {
      "title": "Space Age Pop🗿🍸 | Retro Vintage 60s Background Music",
      "artist": "🚀Marimbas on the Moon! Tiki Lounge Exotica",
      "reasoning": ""
    },
    {
      "title": "EXOTICA - SPACE AGE POP: DOWNTEMPO / AMBIENT Top Hits from 1953 to Today 🎶 | Popular T...",
      "artist": "🎧 LOUNGE",
      "reasoning": "A curated collection spanning decades of lounge and space-age pop—ideal for discovering that perfect balance of timelessness and comfort."
    },
    {
      "title": "Top Contemporary Electro Jazz, Nu Jazz | Relax & Groove",
      "artist": "JAZZTRONICAL",
      "reasoning": "Contemporary electro-jazz with an emphasis on groove and relaxation, grounding the playlist in sounds that still feel soothing and present-day."
    },
    {
      "title": "Sophisticated Modern Lounge Mix",
      "artist": "Upbeat Nu Jazz & Electro Jazz 2026",
      "reasoning": "Modern lounge music with touches of nu-jazz sophistication, bridging vintage coziness with contemporary production for a polished, inviting vibe."
    },
    {
      "title": "Nu Lounge Bar Music 2017 (Mix #1)",
      "artist": "EHRLING",
      "reasoning": ""
    }
  ],
  "artists": [
    "Cosmic Lounge Flight",
    "EHRLING",
    "JAZZTRONICAL",
    "Parov Stelar",
    "SPACE AGE TIKI LOUNGE",
    "Thorin's Side",
    "Upbeat Nu Jazz & Electro Jazz 2026",
    "🌴 Santorini ‘66",
    "🎧 LOUNGE",
    "🚀Marimbas on the Moon! Tiki Lounge Exotica"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### mood-he-1 — אני רוצה משהו אנרגטי לריצת בוקר.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 23128.3,
  "playlist_title": "אנרגיה אפלה לבוקר",
  "playlist_description": "תערובת של אינדסטריאל וגוטיקה עם קצב מהיר שיהיה לך במנוע בזמן הריצה. המוזיקה הזו נשלפה מסצינת הריקוד התת-קרקעית של התשעים, עם קול חזק ומעוררי עידון אפילו בחושך.",
  "tracks": [
    {
      "title": "Dark Cybergoth Mix",
      "artist": "The Enigma TNG",
      "reasoning": "Dark Cybergoth Mix מציעה קצב מתמשך ואנרגיה סינתטית שמתאימה למטבול של ריצה בוקר, בשילוב אפלות גוטית שתשמור עליך ממלל."
    },
    {
      "title": "\"Shadow\" - The Enigma TNG",
      "artist": "Industrial Goth Rock",
      "reasoning": "Shadow - The Enigma TNG משלבת איינדוסטריאל מאגרסיבי עם דחיפה קבועה שתעזור לך להמשיך קדימה בתנופה."
    },
    {
      "title": "Industrial Tech Flow 2025",
      "artist": "Hypnotic Dark Resurrection",
      "reasoning": "Industrial Tech Flow 2025 מגדיר את המרחק עם טכנולוגיה אלקטרונית קשה ותיבת קצב שלא תיתן לך להישתהות."
    },
    {
      "title": "Goth Industrial - Dark Electro - Synthwave",
      "artist": "EBM Music Mix",
      "reasoning": "Goth Industrial - Dark Electro - Synthwave משזרת אינדוסטריאל קרן עם סינתוויי שנשמר חוקי לאורך כל הריצה."
    },
    {
      "title": "Industrial Gothic Metal Duet | Dark Romantic AI Music Video",
      "artist": "DROWN WITH ME",
      "reasoning": "Industrial Gothic Metal Duet מציעה חזון זוג אפל שנותן משקל ועוצמה ליתר המילים של הפלייליסט שלך."
    }
  ],
  "artists": [
    "DROWN WITH ME",
    "EBM Music Mix",
    "Hypnotic Dark Resurrection",
    "Industrial Goth Rock",
    "The Enigma TNG"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### blend-1 — A mix of jazz and electronic, something smooth but still danceable.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 19669.1,
  "playlist_title": "Smooth Grooves & Electric Dreams",
  "playlist_description": "A blend of silky Smooth Jazz, Nu-Jazz, and Electro-Swing that keeps the groove gentle enough for background listening but with enough electronic sparkle and rhythm to move you. Perfect for café afternoons or evening unwinding.",
  "tracks": [
    {
      "title": "Pure Jazz Sanctuary 🛜 Live Stream",
      "artist": "SMOOTH JAZZ & SOUL",
      "reasoning": "A foundational piece of Smooth Jazz that sets the warm, soulful tone—live and welcoming without demanding your attention."
    },
    {
      "title": "The Princess (2012) nu-jazz | electronic | downtempo | electro-swing | acid jazz",
      "artist": "Parov Stelar",
      "reasoning": "Parov Stelar is a cornerstone of Electro-Swing, mixing jazzy swing charm with modern electronic production; this track dances while staying sophisticated."
    },
    {
      "title": "Don't Confuse Nu-Jazz with Jazz (Music)",
      "artist": "Thorin's Side",
      "reasoning": ""
    },
    {
      "title": "Sophisticated Modern Lounge Mix",
      "artist": "Upbeat Nu Jazz & Electro Jazz 2026",
      "reasoning": "A curated lounge mix that bridges modern Nu-Jazz with upbeat electronic elements, keeping things groovy yet refined."
    },
    {
      "title": "A Soundtrack for Falling Leaves",
      "artist": "Smooth Jazz & Relaxing Instrumentals",
      "reasoning": "Smooth Jazz instrumentals with a contemplative edge; the autumn-inspired palette adds depth while maintaining easy listening."
    },
    {
      "title": "Cool Cafe Vibes • Relaxing Saxophone Instrumental for Dinner & Chill",
      "artist": "Smooth Jazz Saxophone Music",
      "reasoning": "Saxophone-led Smooth Jazz that's both relaxing and gently rhythmic—ideal for those moments when you want soul without intensity."
    },
    {
      "title": "Slow Chicago Blues & Smooth Jazz for Midnight Peace & Relaxation",
      "artist": "Blue Suit Blues",
      "reasoning": ""
    },
    {
      "title": "Top Contemporary Electro Jazz, Nu Jazz | Relax & Groove",
      "artist": "JAZZTRONICAL",
      "reasoning": "Contemporary Electro Jazz that leans into groove and playfulness, blending the ambient soothe of electronic production with active rhythm."
    },
    {
      "title": "Early Spring, The Wind Is Still Cold, But the Sunshine Is Warm | Vol. 109",
      "artist": "Smooth Jazz & R&B 90s",
      "reasoning": ""
    },
    {
      "title": "Nu Lounge Bar Music 2017 (Mix #1)",
      "artist": "EHRLING",
      "reasoning": "A Nu-Lounge set that captures that café-terrace vibe mentioned in the genre's history—electronic, melodic, and perfectly unobtrusive for any setting."
    }
  ],
  "artists": [
    "Blue Suit Blues",
    "EHRLING",
    "JAZZTRONICAL",
    "Parov Stelar",
    "SMOOTH JAZZ & SOUL",
    "Smooth Jazz & R&B 90s",
    "Smooth Jazz & Relaxing Instrumentals",
    "Smooth Jazz Saxophone Music",
    "Thorin's Side",
    "Upbeat Nu Jazz & Electro Jazz 2026"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### artist-1 — More songs like Bon Iver and Sufjan Stevens.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 18145.4,
  "playlist_title": "Melodic Journeys",
  "playlist_description": "Exploring music that shares Bon Iver and Sufjan Stevens' sense of emotional depth and atmospheric richness. This playlist drifts across progressive rock, introspective electronic music, and uplifting trance—genres that prize melody and immersive soundscapes over everything else.",
  "tracks": [
    {
      "title": "Break Me Down",
      "artist": "Broken Focus",
      "reasoning": ""
    },
    {
      "title": "Minor Threat",
      "artist": "Minor Threat",
      "reasoning": ""
    },
    {
      "title": "VibezSoulWorld | Vol 15",
      "artist": "Uplifting Trance Energy 2025",
      "reasoning": "Uplifting trance is built on the same principle as Bon Iver's work: melody as the emotional anchor, with hypnotic layers that let you sink into the sound."
    },
    {
      "title": "Punk, Rock, Hardcore Alto Jose Do Pinho",
      "artist": "Devotos Do Odio",
      "reasoning": ""
    },
    {
      "title": "Turn The Lights Off (UNKNX, Zylarion, Adrian Vale) TRANCE VERSION - Elite Trance Music",
      "artist": "Kato & Jon",
      "reasoning": "This trance rework emphasizes vocal and melodic elements, creating the kind of atmospheric storytelling you'd find in Sufjan Stevens' instrumental passages."
    },
    {
      "title": "Uplifting, Vocal & Melodic Trance | Beautiful Progressive Trance Music",
      "artist": "Best Trance Mix 2026",
      "reasoning": "Vocal and melodic trance shares the introspective quality of both artists, using sustained atmospheres and careful arrangements to guide you through each track."
    },
    {
      "title": "Beat the Bastards",
      "artist": "The Exploited",
      "reasoning": ""
    },
    {
      "title": "The Kids Aren't Alright",
      "artist": "The Offspring",
      "reasoning": ""
    },
    {
      "title": "Uplifting, Vocal & Melodic Trance Mix | EDM, Deep, Euphoric & Progressive",
      "artist": "Best Trance 2026 🚀",
      "reasoning": "Progressive trance builds slowly and deliberately, much like Sufjan's orchestral approach—allowing emotion to unfold rather than announce itself."
    },
    {
      "title": "All Time Favourites #1 ♫",
      "artist": "♫ Best Uplifting Trance Mix",
      "reasoning": "A curated mix of uplifting moments that echo the transcendent, almost spiritual feeling in Bon Iver's falsetto-driven peaks."
    }
  ],
  "artists": [
    "Best Trance 2026 🚀",
    "Best Trance Mix 2026",
    "Broken Focus",
    "Devotos Do Odio",
    "Kato & Jon",
    "Minor Threat",
    "The Exploited",
    "The Offspring",
    "Uplifting Trance Energy 2025",
    "♫ Best Uplifting Trance Mix"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### genre-1 — Give me some deep house tracks.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 17296.2,
  "playlist_title": "Deep House Essentials",
  "playlist_description": "A warm dive into deep house's soulful core—funky grooves rooted in Philly Soul and garage traditions, layered with Hammond organs and electric pianos that give the genre its unmistakable warmth and groove.",
  "tracks": [
    {
      "title": "live at LOC’d GROOVES | Deep House",
      "artist": "Fatso 98",
      "reasoning": "This is a live deep house set that captures the genre at its most direct and unfiltered."
    },
    {
      "title": "Time to Be Protected | Tech House Playlist",
      "artist": "Tech House Mix",
      "reasoning": ""
    },
    {
      "title": "Club Bangers Selection",
      "artist": "🍒 Tech House & Bass House 2026",
      "reasoning": ""
    },
    {
      "title": "January 2022 ✨",
      "artist": "✨ Tech House Mix",
      "reasoning": ""
    },
    {
      "title": "Best Tech House Mix 2024",
      "artist": "TOP Tech House DJ Mix 🎵",
      "reasoning": ""
    },
    {
      "title": "67 MIN of freedom | House Music | Deep House Mix",
      "artist": "Rosetta D33P | 2026 | MR SHANE | BUDDYNICE",
      "reasoning": "A pure deep house mix that stretches across 67 minutes, letting you sink into the meditative, soulful rhythms the genre is known for."
    },
    {
      "title": "Best Of Deep & Tech House Music Chillout Mashup Mix 🔥",
      "artist": "Summer Mix 2026 #8",
      "reasoning": ""
    },
    {
      "title": "Ibiza Summer Mix 2026 🍓 Best Of Tropical Deep House Music Chill Out Mix 2025 🍓 Chillout Lounge",
      "artist": "Magic Club",
      "reasoning": "Tropical deep house with a chill-out angle—perfect for exploring how deep house's warm, funky character translates to laid-back summer vibes."
    },
    {
      "title": "Deep Melodic Set | Black Coffee Style Vol. 23 ☕️",
      "artist": "Afro House 2026",
      "reasoning": ""
    },
    {
      "title": "Deep House Mix 2024 | Deep House, Vocal House, Nu Disco, Chillout",
      "artist": "Deep Melodies #1",
      "reasoning": "A vocal deep house mix that blends in nu-disco and chillout touches, showing the genre's range while staying true to its groovy, soulful roots."
    }
  ],
  "artists": [
    "Afro House 2026",
    "Deep Melodies #1",
    "Fatso 98",
    "Magic Club",
    "Rosetta D33P | 2026 | MR SHANE | BUDDYNICE",
    "Summer Mix 2026 #8",
    "TOP Tech House DJ Mix 🎵",
    "Tech House Mix",
    "✨ Tech House Mix",
    "🍒 Tech House & Bass House 2026"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### anti-echo-1 — Surprise me with something outside my usual indie folk taste.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 17484.4,
  "playlist_title": "Beyond the Acoustic",
  "playlist_description": "You asked for something different, so we ventured a bit wider—blending the experimental folk edges you know with some genuinely strange and wonderful music that sits at the crossroads of folk, avant-garde pop, and indie weirdness. Think of it as a gentle push into new territory.",
  "tracks": [
    {
      "title": "ROCK",
      "artist": "Exploring Contemporary Rock: From Origins to Influence",
      "reasoning": ""
    },
    {
      "title": "Taking A Page - Live In San Francisco - 2025 - 4K",
      "artist": "Devendra Banhart",
      "reasoning": "Devendra Banhart's live performance captures the freakfolk spirit—playful, unpolished, and inventive in ways that stretch far beyond traditional indie folk songwriting."
    },
    {
      "title": "audio) - HD",
      "artist": "CocoRosie •ั Villain (Folkadelphia Session",
      "reasoning": "CocoRosie embodies the stranger side of contemporary folk: their work fuses odd textures, found sounds, and avant-garde sensibilities with folk roots, creating something genuinely unpredictable."
    },
    {
      "title": "'All Over Again' Live in studio 2019",
      "artist": "Weird Brother",
      "reasoning": ""
    },
    {
      "title": "Rilkean Heart (Cocteau Twins cover) - Live - 2025",
      "artist": "🤍 Devendra Banhart",
      "reasoning": "Another Devendra Banhart moment, this time reimagining the Cocteau Twins—a bridge between folk craft and the ethereal, electronic-tinged textures of dream pop that sits worlds apart from acoustic guitar traditions."
    }
  ],
  "artists": [
    "CocoRosie •ั Villain (Folkadelphia Session",
    "Devendra Banhart",
    "Exploring Contemporary Rock: From Origins to Influence",
    "Weird Brother",
    "🤍 Devendra Banhart"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### negative-1 — Upbeat pop, but nothing with heavy autotune.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 17851.6,
  "playlist_title": "Jangle & Groove: Pop That Breathes",
  "playlist_description": "A collection of spirited pop that leans on live instrumentation and genuine energy—jangle-pop's shimmering guitars and post-disco's infectious grooves, all without heavy vocal processing. Think '80s vitality meets '70s warmth.",
  "tracks": [
    {
      "title": "My Secret Country (Ethereal Jangle-Pop from Crashing Dream 1985)",
      "artist": "Rain Parade",
      "reasoning": "Rain Parade's ethereal jangle-pop from 1985 brings exactly what you're after: crisp guitar interplay and natural vocals that carry real warmth."
    },
    {
      "title": "Stayin' Alive, Funkytown, Dancing Queen",
      "artist": "70s Disco Hits 🪩 Non-Stop Classics That Never Get Old",
      "reasoning": "Pure disco energy with some of the era's most iconic, straightforward vocal work—celebratory and unadorned."
    },
    {
      "title": "Bee Gees, ABBA, CHIC, Earth, Wind & Fire, Michael Jackson, Donna Summer, Boney M.",
      "artist": "Golden Disco Era",
      "reasoning": ""
    },
    {
      "title": "Paisley Underground",
      "artist": "Bopp!",
      "reasoning": ""
    },
    {
      "title": "80s Post-Disco & Boogie Soul Vinyl Mix",
      "artist": "Koenjiblues",
      "reasoning": "Post-disco and boogie soul with organic instrumentation—funky and upbeat while staying true to live performance feel."
    },
    {
      "title": "Couldn't Stand to Be Alone (Last Rays of a Dying Sun, 2023) | Classic Jangle-Pop",
      "artist": "Rain Parade",
      "reasoning": "Another Rain Parade gem with classic jangle-pop sensibility—melodic and spirited without any synthetic flourishes."
    },
    {
      "title": "Angel Sister (Last Rays of a Dying Sun, 2023) | Jangle-Pop Opener",
      "artist": "Rain Parade",
      "reasoning": "A jangle-pop opener that trades in the same unprocessed charm and musical clarity that defines the sound you're looking for."
    },
    {
      "title": "Bring You Back (Last Rays of a Dying Sun, 2023) | Resonant Jangle-Rock",
      "artist": "Rain Parade",
      "reasoning": ""
    },
    {
      "title": "80's Post Disco, Funk, Soul & Boogie Classics 7'' Vinyl Mix",
      "artist": "DJ Destruction",
      "reasoning": ""
    },
    {
      "title": "70s 80s | 🎵 Bee Gees, Boney M, Abba, Donna Summer Etc",
      "artist": "Disco Mix 1",
      "reasoning": ""
    }
  ],
  "artists": [
    "70s Disco Hits 🪩 Non-Stop Classics That Never Get Old",
    "Bopp!",
    "DJ Destruction",
    "Disco Mix 1",
    "Golden Disco Era",
    "Koenjiblues",
    "Rain Parade"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### genre-he-1 — משהו במקצב של רוק ישראלי קלאסי.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 21984.7,
  "playlist_title": "רוק אפל ותעשייתי",
  "playlist_description": "כשביקשת רוק קלאסי ישראלי, הגענו למשהו שונה - תערובת של רוק תעשייתי וגותי כהה שנשמע כמו הצד האפל של הרוק המודרני. הקוליות הממומשמשות והקצב הכבד כאן מזכירים את האנרגיה הגולמית של הרוק הקשה, אבל עם אלקטרוניקה מעוותת וברוח מרדנית.",
  "tracks": [
    {
      "title": "Dark Cybergoth Mix",
      "artist": "The Enigma TNG",
      "reasoning": "'Dark Cybergoth Mix' משלב אלקטרוניקה תעשייתית עם רוק כהה, קרוב ביותר למה שחיפשת עם קצת סטייה לעברי טקסטורות אלקטרוניות."
    },
    {
      "title": "\"Shadow\" - The Enigma TNG",
      "artist": "Industrial Goth Rock",
      "reasoning": "'Shadow' של Industrial Goth Rock מציע את התשובה הישירה יותר - רוק תעשייתי גותי שמשמר את כוח הרוק עם שכבות קודרות."
    },
    {
      "title": "Industrial Tech Flow 2025",
      "artist": "Hypnotic Dark Resurrection",
      "reasoning": "'Industrial Tech Flow 2025' מוסיף קצב אלקטרוני למטבח התעשייתי, בשביל מי שרוצה משהו עם פולס יותר מעכשווי."
    },
    {
      "title": "Goth Industrial - Dark Electro - Synthwave",
      "artist": "EBM Music Mix",
      "reasoning": "'Goth Industrial - Dark Electro - Synthwave' משלט את הדינמיקה של רוק תעשייתי עם סינתיסייזרים חודים וקול סאד רחוק."
    },
    {
      "title": "Industrial Gothic Metal Duet | Dark Romantic AI Music Video",
      "artist": "DROWN WITH ME",
      "reasoning": "'Industrial Gothic Metal Duet' מחזיר אותך לאנרגיה מתכתית טהורה יותר, עם דרמה גותית שמחזקת את הצד הרוק של התערובת."
    }
  ],
  "artists": [
    "DROWN WITH ME",
    "EBM Music Mix",
    "Hypnotic Dark Resurrection",
    "Industrial Goth Rock",
    "The Enigma TNG"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### mood-era-1 — 90s grunge for a moody evening.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 17819.5,
  "playlist_title": "Moody Grunge Evening",
  "playlist_description": "A collection capturing the raw sincerity and introspective melancholy of 90s grunge and its aftermath. From essential tracks to deeper cuts, this playlist honors the era's honest, inward-looking spirit—perfect for when you want to sit with the heavier emotions.",
  "tracks": [
    {
      "title": "Top 5 Post-Grunge Bands. #shorts",
      "artist": "Xirdeh",
      "reasoning": ""
    },
    {
      "title": "Blind ranking grunge albums #podcast #creedband #grunge #90smusic",
      "artist": "My Own Podcast",
      "reasoning": ""
    },
    {
      "title": "Top 5 Grunge Songs of All Time.",
      "artist": "Rock N Replay",
      "reasoning": "Rock N Replay's ranking of all-time grunge songs provides a curated journey through the genre's most impactful moments."
    },
    {
      "title": "No One Leaves Clean [Dark Grunge / Alternative Rock Full Album]",
      "artist": "Eileen Noise",
      "reasoning": "Eileen Noise's full album showcases dark, alternative-leaning grunge that sustains a moody atmosphere throughout an entire evening."
    },
    {
      "title": "Smells Like Teen Spirit",
      "artist": "Nirvana",
      "reasoning": "Nirvana's 'Smells Like Teen Spirit' is the quintessential grunge anthem, embodying the genre's breakthrough moment with its raw energy and earnest vulnerability."
    },
    {
      "title": "Top 50 Post Grunge Songs. The Best Post Grunge Songs",
      "artist": "VM Music Channel",
      "reasoning": "A comprehensive collection of post-grunge highlights carries forward the tragic, sentimental qualities that defined the sound after the original movement faded."
    },
    {
      "title": "Avinish Bhaskar | SARBAN",
      "artist": "Grunge (Official Visualizer)",
      "reasoning": ""
    },
    {
      "title": "Dark & Emotional Rock Mix",
      "artist": "Post-Grunge Playlist (1 Hour)",
      "reasoning": "A dedicated post-grunge emotional mix keeps the introspective, sorrowful tone alive in the material that followed grunge's heyday."
    },
    {
      "title": "Grunge Vs Post Grunge Guitar Riffs #guitar #nirvana #90s #grunge #2000s #alternativerock #shorts",
      "artist": "Rokko Ca$h",
      "reasoning": ""
    },
    {
      "title": "Architect Of Prisons [Full Album] Heavy Metal / Alt Metal / Post-metal / Post-Grunge",
      "artist": "MAGNETIC FLY",
      "reasoning": ""
    }
  ],
  "artists": [
    "Eileen Noise",
    "Grunge (Official Visualizer)",
    "MAGNETIC FLY",
    "My Own Podcast",
    "Nirvana",
    "Post-Grunge Playlist (1 Hour)",
    "Rock N Replay",
    "Rokko Ca$h",
    "VM Music Channel",
    "Xirdeh"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### blend-2 — Hip hop mixed with soul, in English please.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 16919.1,
  "playlist_title": "Soul & Breaks",
  "playlist_description": "A collection blending hip-hop's breakbeat foundation with soulful vocals and smooth grooves. These tracks honor the roots of rap culture—from freestyle's early energy to the softer, more melodic side where soul and hip-hop meet.",
  "tracks": [
    {
      "title": "Don't Stop The Rock",
      "artist": "Freestyle",
      "reasoning": "A classic freestyle track that sits at the heart of hip-hop's breakdancing culture, with the kind of instrumental foundation that made the genre possible."
    },
    {
      "title": "Sidhu Moosewala ( Full Song )| latest song 2024 | The kidds | Sidhu Records ™.",
      "artist": "Asool",
      "reasoning": ""
    },
    {
      "title": "Late Night Mood Jazz Relaxing Smooth Jazz Saxophone",
      "artist": "ONSTAGE Band",
      "reasoning": ""
    },
    {
      "title": "If I Fall (Itaal And Jay's Urban Splendor)",
      "artist": "ADA DYER",
      "reasoning": "A soulful take on urban R&B, bringing the smooth vocal warmth and emotional depth that defines the modern soul-hip-hop blend."
    },
    {
      "title": "MEGAMIX FREESTYLE - Stevie B, Noel, Gina Dee, MOdern Bass, Freestyle Music",
      "artist": "Mix Freestyle",
      "reasoning": ""
    },
    {
      "title": "Freestyler (Break dance) Red Bull BC One [Пупок Видео] #Брейк #Брейкинг #Фристайло",
      "artist": "Bomfunk MC's",
      "reasoning": "An iconic breakdance anthem that captures the electro-funk spirit of hip-hop's earliest days, built for movement and the culture it represents."
    },
    {
      "title": "Freestyler (Video Original Version)",
      "artist": "Bomfunk MC's",
      "reasoning": ""
    },
    {
      "title": "Electric Wave [Electro Freestyle Breakdance]",
      "artist": "SymphoBreaks",
      "reasoning": ""
    }
  ],
  "artists": [
    "ADA DYER",
    "Asool",
    "Bomfunk MC's",
    "Freestyle",
    "Mix Freestyle",
    "ONSTAGE Band",
    "SymphoBreaks"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### vague-1 — Play me something good.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 19517.5,
  "playlist_title": "Feel-Good Groove",
  "playlist_description": "A warm mix that flows from soulful blues and gospel roots through modern house and electronic vibes—all tied together by that timeless spirit of joy and positivity that makes you want to move.",
  "tracks": [
    {
      "title": "Bobby “Blue” Bland, Ray Charles & Smooth Vintage Soul Classics",
      "artist": "Golden Soul Blues Café ☕",
      "reasoning": "Bobby \"Blue\" Bland and Ray Charles bring that classic soul warmth and emotional depth that house music itself draws inspiration from."
    },
    {
      "title": "Best Tech House Mix 2024",
      "artist": "TOP Tech House DJ Mix 🎵",
      "reasoning": "Tech house keeps the feel-good groove alive with contemporary production and steady, soulful beats perfect for letting loose."
    },
    {
      "title": "Popular Top So...",
      "artist": "🎧 TRADITIONAL GOSPEL: BLUE NOTE: GOSPEL & PIONEERS Top Hits from 1880 to Today 🎶",
      "reasoning": "Gospel's foundation of hope and community spirit echoes through everything on this playlist—it's where the warmth starts."
    },
    {
      "title": "Día de Muertos Party | J.Devis & Jorge Walking",
      "artist": "La Bamba (EDM Dance House Remix)",
      "reasoning": "A house remix that marries dance energy with infectious celebration, bringing that playful, compassionate house vibe to life."
    },
    {
      "title": "2020 Megamix ┃Best EDM Songs Of All Time - DJ Mix 2023",
      "artist": "Best Of EDM 2010",
      "reasoning": "Electronic dance music at its most joyful—the kind that reminds you why people fill dance floors to feel alive."
    },
    {
      "title": "You Can't Beat God Giving (Live)",
      "artist": "Gaither, Billy Preston",
      "reasoning": "Billy Preston and gospel vocals deliver pure positivity and spiritual uplift, grounding the electronic elements in real heart."
    },
    {
      "title": "Electro House Music",
      "artist": "EDM Mashup Mix 2026 | Best Mashups & Remixes of Popular Songs",
      "reasoning": "Electro house grooves with that digital warmth that house music perfected—simple, soulful, and made for feeling good."
    },
    {
      "title": "Bobby “Blue” Bland, Ray Charles & Gospel Blues Icons",
      "artist": "Classic Soul Blues Treasures 🎙",
      "reasoning": ""
    },
    {
      "title": "STRIDE: BLUE NOTE: GOSPEL & PIONEERS Top Hits from 1890 to Today 🎶 | Popular Top Song...",
      "artist": "🎧 RAGTIME",
      "reasoning": ""
    },
    {
      "title": "Vibey Deep House Mix 2024 | Mix",
      "artist": "Yaman Khadzi | Selected Mix 2024 | Deep House Mix 2024 | Ibiza",
      "reasoning": ""
    }
  ],
  "artists": [
    "Best Of EDM 2010",
    "Classic Soul Blues Treasures 🎙",
    "EDM Mashup Mix 2026 | Best Mashups & Remixes of Popular Songs",
    "Gaither, Billy Preston",
    "Golden Soul Blues Café ☕",
    "La Bamba (EDM Dance House Remix)",
    "TOP Tech House DJ Mix 🎵",
    "Yaman Khadzi | Selected Mix 2024 | Deep House Mix 2024 | Ibiza",
    "🎧 RAGTIME",
    "🎧 TRADITIONAL GOSPEL: BLUE NOTE: GOSPEL & PIONEERS Top Hits from 1880 to Today 🎶"
  ],
  "engine": "graph",
  "placeholder": false
}
```

### negative-2 — Chill acoustic music, but nothing that sounds like a coffee-shop cliche.

**New engine:**
```json
{
  "ok": true,
  "status": 200,
  "latency_ms": 18677.8,
  "playlist_title": "Retro Futures & Moody Margins",
  "playlist_description": "A curated escape from the ordinary: vintage space-age lounge and exotica sit alongside darker, more experimental sounds. There's warmth here, but with an edge—think mid-century cocktail bars crossed with industrial intrigue.",
  "tracks": [
    {
      "title": "Space Age Pop🗿🍸 | Retro Vintage 60s Background Music",
      "artist": "🚀Marimbas on the Moon! Tiki Lounge Exotica",
      "reasoning": "Pure retro lounge aesthetics with that nostalgic 60s vibe, but the marimba-and-tiki angle keeps it pleasantly weird rather than generic."
    },
    {
      "title": "Dark Cybergoth Mix",
      "artist": "The Enigma TNG",
      "reasoning": ""
    },
    {
      "title": "60's Exotica Jazz Cocktail Lounge Music",
      "artist": "SPACE AGE TIKI LOUNGE",
      "reasoning": "Straight exotica cocktail jazz—the kind of atmospheric background music that actually rewards listening, without feeling like it's trying too hard."
    },
    {
      "title": "Retro Vintage Tiki Lounge Exotica | 60s Lounge Background Music | Space-Age Pop🗿🍸",
      "artist": "🌴 Santorini ‘66",
      "reasoning": "Another slice of vintage space-age pop from the lounge tradition, layering that retro comfort with a slightly dreamier approach."
    },
    {
      "title": "Industrial Gothic Metal Duet | Dark Romantic AI Music Video",
      "artist": "DROWN WITH ME",
      "reasoning": "A tonal shift into moody territory; industrial and gothic undertones give the playlist some textural contrast and emotional depth beyond sunshine nostalgia."
    },
    {
      "title": "1960s Space Age Pop",
      "artist": "Cosmic Lounge Flight",
      "reasoning": ""
    },
    {
      "title": "Goth Industrial - Dark Electro - Synthwave",
      "artist": "EBM Music Mix",
      "reasoning": "Dark electro that leans atmospheric rather than aggressive—it's experimental enough to feel fresh, grounded in that gothic-industrial world that keeps things from feeling too quaint."
    },
    {
      "title": "Industrial Tech Flow 2025",
      "artist": "Hypnotic Dark Resurrection",
      "reasoning": ""
    },
    {
      "title": "\"Shadow\" - The Enigma TNG",
      "artist": "Industrial Goth Rock",
      "reasoning": ""
    },
    {
      "title": "EXOTICA - SPACE AGE POP: DOWNTEMPO / AMBIENT Top Hits from 1953 to Today 🎶 | Popular T...",
      "artist": "🎧 LOUNGE",
      "reasoning": "A curated hit collection spanning classic exotica and space-age pop from across decades, a nice moment to reflect on how the mood has evolved through the playlist."
    }
  ],
  "artists": [
    "Cosmic Lounge Flight",
    "DROWN WITH ME",
    "EBM Music Mix",
    "Hypnotic Dark Resurrection",
    "Industrial Goth Rock",
    "SPACE AGE TIKI LOUNGE",
    "The Enigma TNG",
    "🌴 Santorini ‘66",
    "🎧 LOUNGE",
    "🚀Marimbas on the Moon! Tiki Lounge Exotica"
  ],
  "engine": "graph",
  "placeholder": false
}
```
