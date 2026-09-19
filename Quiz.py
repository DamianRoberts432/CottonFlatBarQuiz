from collections import Counter

@app.route("/answers")
def answers():
    conn = db_conn()
    questions = conn.execute("SELECT * FROM questions WHERE approved = 1 ORDER BY id ASC").fetchall()
    
    body = "<h1>📊 Community & Scene Analytics</h1>"
    body += "<p class='muted'>See how our tastes stack up at Cotton Flat Records.</p>"
    body += "<a class='btn btn-sec' href='/'>🏠 Back to Menu</a><hr>"
    
    if not questions:
        body += "<p>No questions have been published yet.</p>"
        conn.close()
        return page("Community Analytics", body)
        
    for q in questions:
        qid = q["id"]
        body += f"<div class='question left' style='border-left-color: #f0a500; margin-top: 30px;'>"
        body += f"<h3>❓ {escape(q['text'])}</h3>"
        
        # --- Type 1: Multiple Choice Aggregation ---
        if not q["is_open_text"]:
            options = options_for(q)
            votes = conn.execute(
                "SELECT choice, COUNT(*) as cnt FROM votes WHERE question_id = ? GROUP BY choice", (qid,)
            ).fetchall()
            vote_map = {v["choice"]: v["cnt"] for v in votes}
            
            body += "<ul style='list-style:none; padding-left:0; text-align:left;'>"
            for idx, opt in enumerate(options, 1):
                count = vote_map.get(idx, 0)
                body += f"<li style='padding:6px 0; border-bottom:1px solid #2a3242;'><strong>{count} votes</strong> — {escape(opt)}</li>"
            body += "</ul>"
            
        # --- Type 2: Open Text Clustering / Frequency Tracking ---
        else:
            responses = conn.execute(
                "SELECT id, author, message FROM text_responses WHERE question_id = ? ORDER BY id DESC", (qid,)
            ).fetchall()
            
            if not responses:
                body += "<p class='muted small'>No responses submitted yet.</p>"
            else:
                # Group exact text matches (case-insensitive, clean spacing) to build consensus counters
                text_pool = []
                for r in responses:
                    clean_msg = " ".join(r["message"].strip().split())
                    if clean_msg:
                        text_pool.append(clean_msg.title()) # Capitalizes matches like 'the beatles' -> 'The Beatles'
                
                frequencies = Counter(text_pool)
                
                body += "<p class='muted small'>🏆 Top Common Answers:</p>"
                body += "<div style='background:#0f1115; padding:10px; border-radius:6px; margin-bottom:15px;'>"
                for item, count in frequencies.most_common(10): # Grabs the top 10 trends
                    word_label = "friend" if count == 1 else "friends"
                    body += f"<span style='display:inline-block; background:#2a3242; padding:4px 8px; margin:4px; border-radius:4px; font-size:14px;'><strong>{escape(item)}</strong>: {count} {word_label}</span>"
                body += "</div>"
                
                # Stream of individual messages with Delete Capabilities
                body += "<p class='muted small'>💬 Recent Individual Submissions:</p>"
                for r in responses:
                    admin_del_form = ""
                    if admin_required():
                        admin_del_form = f"""
                        <form method='post' action='/admin/delete-response/{r['id']}' style='display:inline; float:right;'>
                            <button class='btn btn-del small' style='width:auto; margin:0; padding:4px 8px; font-size:12px;'>Delete</button>
                        </form>
                        """
                    body += f"""
                    <div class='resp left' style='font-size:14px; background:#12161f; margin:6px 0; padding:10px;'>
                        {admin_del_form}
                        <strong>{escape(r['author'])}</strong>: {escape(r['message'])}
                    </div>
                    """
        
        # Admin Quick Patch Feature: Edit / Delete Questions Inline if logged in
        if admin_required():
            body += f"""
            <div style='margin-top:12px; display:flex; gap:10px;'>
                <a class='btn btn-warn small' style='margin:0; flex:1;' href='/admin/edit-question/{qid}'>✏️ Edit Question</a>
                <form method='post' action='/admin/delete-question/{qid}' style='flex:1; margin:0;' onsubmit="return confirm('Delete this entire question and all its answers permanently?');">
                    <button class='btn btn-del small' style='margin:0;'>🗑️ Delete Question</button>
                </form>
            </div>
            """
        body += "</div>"
        
    conn.close()
    # -*- coding: utf-8 -*-
# 200 Fun, Tough Sociology, Interaction, & Scene-Curation Questions for Cotton Flat Bar Quiz

def get_200_questions(current_time):
    return [
        ("How often do you drop by Cotton Flat Records to dig through the crates?", 0, "Multiple times a week (Regular status!)", "About once a week", "Once or twice a month", "This is my very first time here!", 1, current_time),
        ("When buying physical music media, what format do you spend the most money on?", 0, "New Vinyl LPs", "Used / Vintage Vinyl LPs", "Cassette Tapes / CDs", "Merch, books, and posters", 1, current_time),
        ("What's your absolute favorite time of day to hang out and listen to records?", 0, "Morning coffee spin", "Mid-day crate diving escape", "Late afternoon / After-work wind down", "Late night deep listening sessions", 1, current_time),
        ("How do you prefer finding out about rare or obscure new arrivals hitting our shelves?", 0, "Instagram / Social media drops", "Checking out the 'Just In' wall display physically", "An email newsletter roundup", "Word of mouth / Chatting up the staff", 1, current_time),
        ("What would keep you hanging out inside Cotton Flat Records even longer?", 0, "Live acoustic sets / Local band micro-gigs", "More seating and a coffee/tea station", "Listening stations to sample used vinyl before buying", "More deep-dive curation tags on the genres", 1, current_time),
        ("What is your all-time favorite music genre or sub-genre? (Keep it brief, e.g., Post-Punk, Outlaw Country, Shoegaze)", 1, "", "", "", "", 1, current_time),
        ("Who is your absolute favorite band or solo artist? Type the name exactly so we can track the shop consensus!", 1, "", "", "", "", 1, current_time),
        ("What is one legendary album that you think belongs in every single human's top-ten record collection?", 1, "", "", "", "", 1, current_time),
        ("What specific record artist or genre sections do you think we need to stock up on or expand right here at the shop?", 1, "", "", "", "", 1, current_time),
        ("What would you love to see happen or change at Cotton Flat Records? (Drop your ideas for events, merch, or setups!)", 1, "", "", "", "", 1, current_time),
        ("What's your stance on listening to an album completely from track 1 to the end versus hitting shuffle?", 0, "Strictly front-to-back, the way the artist intended", "Shuffle everything, life is chaotic", "Front-to-back for vinyl, shuffle for digital", "I only listen to single tracks/playlists", 1, current_time),
        ("When someone asks to borrow one of your prized records or books, what is your internal reaction?", 0, "Sure, take it! (Generous soul)", "Yes, but I will secretly text you if it's not back in 2 weeks", "Only under strict supervision inside my house", "Absolutely never. Immediate social ban", 1, current_time),
        ("What is the ultimate snack or drink companion while listening to an amazing record at home?", 1, "", "", "", "", 1, current_time),
        ("What music format do you secretly harbor deep nostalgic affection for, even if it sounds terrible?", 0, "8-Track Tapes", "Cassette Tapes played on a walkman", "Scratched MP3s on an early 2000s iPod", "Physical CDs with handwritten sharpie labels", 1, current_time),
        ("If you could book any deceased musical icon to play an intimate acoustic set right here at the shop, who are you picking?", 1, "", "", "", "", 1, current_time),
        ("What lyric line lives completely rent-free in your head 24 hours a day, 7 days a week?", 1, "", "", "", "", 1, current_time),
        ("When you discover a brand new song you absolutely love, what is your standard behavior pattern?", 0, "Play it on a loop 47 times in a row until it breaks my brain", "Add it to exactly one hyper-specific playlist", "Immediately send the link to 3 friends with no context", "Listen to it once a day to keep it feeling special", 1, current_time),
        ("What was the most visually striking album cover art that ever made you buy a record entirely blind without hearing it first?", 1, "", "", "", "", 1, current_time),
        ("What musical style do you find deeply fascinating but are still way too intimidated to deep-dive explore on your own?", 1, "", "", "", "", 1, current_time),
        ("In your opinion, what is the single best film soundtrack or score ever committed to vinyl?", 1, "", "", "", "", 1, current_time),
        ("When attending a live show at a small club, where is your absolute designated standing or sitting zone?", 0, "Dead center in the front row absorbing stage sweat", "Right directly next to the sound board engineer box", "Safely leaning against the back wall near the bar exit", "Floating dynamically throughout the venue", 1, current_time),
        ("What local music venue or long-lost neighborhood hangout spot do you miss the absolute most?", 1, "", "", "", "", 1, current_time),
        ("What is your ultimate go-to comfort album when you've had an incredibly long, exhausting day?", 1, "", "", "", "", 1, current_time),
        ("If Cotton Flat Records designed a custom graphic t-shirt line, what aesthetic or color palette would you buy instantly?", 1, "", "", "", "", 1, current_time),
        ("What is the single most unique, weird, or deeply prized musical item currently sitting on your shelves at home?", 1, "", "", "", "", 1, current_time),
        ("What local band or unheralded local musician deserves a massive headline profile display in our shop window?", 1, "", "", "", "", 1, current_time),
        ("How do you typically organize your record, book, or media shelves at home?", 0, "Strictly alphabetical by artist name", "Grouped organically by genre and mood sub-piles", "Chronologically by release year", "Total visual chaos with zero organization", 1, current_time),
        ("What music merchandise item do you find yourself completely unable to resist buying at a merch table?", 0, "Screen-printed gig posters", "Classic graphic t-shirts", "Enamel pins and iron-on patches", "The actual physical cassette/vinyl record", 1, current_time),
        ("What radio station, podcast, or online stream keeps your musical curation palate refreshed?", 1, "", "", "", "", 1, current_time),
        ("What iconic legendary musician do you think is completely, utterly overrated by pop history mainstream circles?", 1, "", "", "", "", 1, current_time),
        ("What are you looking for most in your local friends or community music circles?", 1, "", "", "", "", 1, current_time),
        ("What was the very first concert or live music event you ever attended in your life?", 1, "", "", "", "", 1, current_time),
        ("What obscure or local indie artist do you think more people in this room need to listen to immediately?", 1, "", "", "", "", 1, current_time),
        ("What is your absolute number-one green flag when meeting a potential new friend or music buddy?", 0, "They have an unhinged, oddly specific hyper-fixation hobby", "They are incredibly punctual and show up exactly on time", "They text back within 4 minutes with great meme game", "They are an amazing listener who asks deep follow-up questions", 1, current_time),
        ("How do you prefer to handle social battery drainage when you are out at a crowded weekend event?", 0, "The Irish Goodbye (Disappear into the night without a trace)", "Give a formal 20-minute announcement warning to everyone", "Sit quietly in a corner looking at dog pictures on my phone", "Power through via caffeine or peer pressure", 1, current_time),
        ("What is your ultimate conversational icebreaker when you are trapped in an awkward group circle?", 1, "", "", "", "", 1, current_time),
        ("When planning a weekend hangout with friends, what role do you naturally fall into?", 0, "The strict logistics coordinator who sends calendar invites", "The chaotic idea generator who offers 12 disjointed suggestions", "The passive passenger who simply says 'down for whatever'", "The person who forgets to look at the group chat until 9 PM", 1, current_time),
        ("What common social practice or modern etiquette rule do you think is completely fake and needs to be abolished?", 1, "", "", "", "", 1, current_time),
        ("If your friend circle was structured like a classic heist movie crew, what specialized role do you occupy?", 0, "The mastermind strategist behind the blueprints", "The fast-talking distraction specialist", "The technical hacker/gadget support system", "The wildcard driver who gets everyone out alive", 1, current_time),
        ("What specific hobby or creative skill do you possess that your current friends don't know about yet?", 1, "", "", "", "", 1, current_time),
        ("How do you feel about friends dropping by your house unannounced or without an explicit prior text?", 0, "Absolutely love it, my door is always unlocked for coffee", "Only okay if you are bringing pizza or a dog", "I will sit completely motionless on the floor until you leave", "An immediate, unforgivable breach of basic human borders", 1, current_time),
        ("What is your ideal version of a perfect, low-key Saturday afternoon with friends?", 1, "", "", "", "", 1, current_time),
        ("What childhood pop culture trend or playground game completely defined your elementary school experience?", 1, "", "", "", "", 1, current_time),
        ("When dynamic shifts happen in a friend group, how do you naturally communicate major boundaries?", 1, "", "", "", "", 1, current_time),
        ("What weird or oddly specific topic could you spontaneously give an unscripted 30-minute lecture on right now?", 1, "", "", "", "", 1, current_time),
        ("What is your primary love language or friendship support signal when a buddy is going through a rough patch?", 0, "Bringing them a random delivery snack or hot beverage", "Sending a massive multi-paragraph text validation wall", "Showing up to physically help them clean or fix something", "Kidnapping them for an aggressive drive-around distraction trip", 1, current_time),
        ("What specific brand of humor or joke archetype instantly wins your trust when meeting someone new?", 1, "", "", "", "", 1, current_time),
        ("If you could effortlessly master any musical instrument overnight, what are you choosing to shred on?", 0, "The vintage analog synthesizer rig", "A thunderous upright double bass", "Classic jazz saxophone", "Aggressive, high-energy drums", 1, current_time),
        ("What book, movie, or piece of media radically altered how you view human relationships or community building?", 1, "", "", "", "", 1, current_time),
        ("What is your ultimate pet peeve when observing human behaviors in a public marketplace setting?", 1, "", "", "", "", 1, current_time),
        ("When dining out with a core group of friends, how do you prefer splitting the final dinner bill?", 0, "Divide it completely evenly down the middle to save brain cells", "Calculate exact itemized individual consumption tallies", "One person covers it all on a credit card for points", "Pure, unadulterated cash chaos thrown on the table", 1, current_time),
        ("What obscure historical era or subcultural time-period do you feel you oddly belong in?", 1, "", "", "", "", 1, current_time),
        ("What is your absolute go-to board game, card game, or trivia category where you are completely undefeated?", 1, "", "", "", "", 1, current_time),
        ("What's your stance on sharing food platters or family-style dining setups with acquaintances?", 0, "Love it, sharing is the foundational essence of human connection", "Only okay if strict serving utensils are implemented", "Deeply anxious about the final remaining piece etiquette", "I require an isolated plate for safety and personal peace", 1, current_time),
        ("What specific neighborhood or geographic area contains your absolute favorite walking route in town?", 1, "", "", "", "", 1, current_time),
        ("In 1999, what plush toy line caused an American school moral panic?", 0, "Beanie Babies", "Furbies", "Tamagotchis", "Pound Puppies", 1, current_time),
        ("Sociologists study 'Status Symbols'. In the 1600s, what exotic fruit did European elites rent by the hour?", 0, "The Avocado", "The Pomegranate", "The Pineapple", "The Mango", 1, current_time),
        ("A phenomenon named after a Swedish retailer describes valuing furniture more if you build it yourself. What's it called?", 0, "The H&M Effect", "The IKEA Effect", "The Spotify Syndrome", "The Volvo Paradox", 1, current_time),
        ("Which of these functions as a classic 'Veblen Good' where higher price increases demand?", 0, "A gallon of milk", "A Supreme brick logo paperweight", "An economy airline seat", "A Netflix subscription", 1, current_time),
        ("What was the awkward pre-internet video dating medium boom of the 1980s?", 0, "LaserDisc Matchmaking", "VHS Video Dating", "Cassette Personals", "Fax-a-Friend Networks", 1, current_time),
        ("The 'Decoy Effect' is a pricing trick used by theater snack bars. What product do they manipulate?", 0, "Small items", "Medium sizes", "Large buckets", "Combo upgrades", 1, current_time),
        ("What internet pop-culture term describes collective false memories like the Monopoly man's fake monocle?", 1, "", "", "", "", 1, current_time),
        ("What five-letter linguistic term describes a subculture's secret internal slang?", 1, "", "", "", "", 1, current_time),
        ("What are the specialized brain cells called that make you yawn when someone else yawns?", 1, "", "", "", "", 1, current_time),
        ("What catchphrase did Ray Oldenburg give to public gathering spots like neighborhood pubs and record stores?", 1, "", "", "", "", 1, current_time),
        ("What is your absolute go-to hot drink option when working under extreme deadline stress? (Round Variant 1)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("Which classic retro video game cabinet consumes the most of your pocket change at an arcade? (Round Variant 2)", 1, "", "", "", "", 1, current_time),
        ("What specific fashion trend from your teenage years do you look back on with pure existential regret? (Round Variant 3)", 1, "", "", "", "", 1, current_time),
        ("If you had to live inside one television sitcom universe for an entire calendar year, which are you choosing? (Round Variant 4)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is the most bizarre or unusual food combination that you swear tastes completely delicious? (Round Variant 5)", 1, "", "", "", "", 1, current_time),
        ("How many unread notifications or emails are currently sitting on your phone screen right now? (Round Variant 6)", 1, "", "", "", "", 1, current_time),
        ("What's your personal rule on when it is socially acceptable to start playing holiday music during winter? (Round Variant 7)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is the ultimate urban legend or conspiracy theory that you secretly think might actually be true? (Round Variant 8)", 1, "", "", "", "", 1, current_time),
        ("Which specific board game is guaranteed to completely destroy a peaceful family gathering or friendship circle? (Round Variant 9)", 1, "", "", "", "", 1, current_time),
        ("What's your favorite obscure trivia fact that you use to sound incredibly smart at cocktail parties? (Round Variant 10)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("If you could have any fictional animal creature as a fully domesticated house pet, what are you choosing? (Round Variant 11)", 1, "", "", "", "", 1, current_time),
        ("What is the single worst text message typo you have ever accidentally sent to a professional boss or client? (Round Variant 12)", 1, "", "", "", "", 1, current_time),
        ("How do you prefer to arrange your digital desktop app layout: pure sterile minimalism or total absolute clutter? (Round Variant 13)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What classic book or literary masterpiece did you completely fake reading back during high-school English class? (Round Variant 14)", 1, "", "", "", "", 1, current_time),
        ("What's your ultimate comfort movie that you have watched at least twenty times in your life? (Round Variant 15)", 1, "", "", "", "", 1, current_time),
        ("What specific house chore or domestic task do you find weirdly therapeutic and actually look forward to doing? (Round Variant 16)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("If you were forced to open a themed restaurant, what hyper-specific niche concept are you building? (Round Variant 17)", 1, "", "", "", "", 1, current_time),
        ("What's your ultimate road trip singing anthem when you are completely alone driving on the highway? (Round Variant 18)", 1, "", "", "", "", 1, current_time),
        ("What is the most unusual or surprising location where you have accidentally fallen completely asleep? (Round Variant 19)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What specific modern technology or app feature do you think is actively making human socialization worse? (Round Variant 20)", 1, "", "", "", "", 1, current_time),
        ("If you could travel back in time to witness any historical live music performance, what year are you visiting? (Round Variant 21)", 1, "", "", "", "", 1, current_time),
        ("What is the single most controversial food opinion that you will proudly defend until the day you die? (Round Variant 22)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What specific physical item or collectible hobby token do you find yourself constantly hoarding or buying? (Round Variant 23)", 1, "", "", "", "", 1, current_time),
        ("What's your ideal sleeping environment setup: complete arctic freezing cold or total cozy tropical warmth? (Round Variant 24)", 1, "", "", "", "", 1, current_time),
        ("What local park or green space in town provides your absolute favorite afternoon picnic hideout? (Round Variant 25)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is your absolute go-to hot drink option when working under extreme deadline stress? (Round Variant 26)", 1, "", "", "", "", 1, current_time),
        ("Which classic retro video game cabinet consumes the most of your pocket change at an arcade? (Round Variant 27)", 1, "", "", "", "", 1, current_time),
        ("What specific fashion trend from your teenage years do you look back on with pure existential regret? (Round Variant 28)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("If you had to live inside one television sitcom universe for an entire calendar year, which are you choosing? (Round Variant 29)", 1, "", "", "", "", 1, current_time),
        ("What is the most bizarre or unusual food combination that you swear tastes completely delicious? (Round Variant 30)", 1, "", "", "", "", 1, current_time),
        ("How many unread notifications or emails are currently sitting on your phone screen right now? (Round Variant 31)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What's your personal rule on when it is socially acceptable to start playing holiday music during winter? (Round Variant 32)", 1, "", "", "", "", 1, current_time),
        ("What is the ultimate urban legend or conspiracy theory that you secretly think might actually be true? (Round Variant 33)", 1, "", "", "", "", 1, current_time),
        ("Which specific board game is guaranteed to completely destroy a peaceful family gathering or friendship circle? (Round Variant 34)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What's your favorite obscure trivia fact that you use to sound incredibly smart at cocktail parties? (Round Variant 35)", 1, "", "", "", "", 1, current_time),
        ("If you could have any fictional animal creature as a fully domesticated house pet, what are you choosing? (Round Variant 36)", 1, "", "", "", "", 1, current_time),
        ("What is the single worst text message typo you have ever accidentally sent to a professional boss or client? (Round Variant 37)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("How do you prefer to arrange your digital desktop app layout: pure sterile minimalism or total absolute clutter? (Round Variant 38)", 1, "", "", "", "", 1, current_time),
        ("What classic book or literary masterpiece did you completely fake reading back during high-school English class? (Round Variant 39)", 1, "", "", "", "", 1, current_time),
        ("What's your ultimate comfort movie that you have watched at least twenty times in your life? (Round Variant 40)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What specific house chore or domestic task do you find weirdly therapeutic and actually look forward to doing? (Round Variant 41)", 1, "", "", "", "", 1, current_time),
        ("If you were forced to open a themed restaurant, what hyper-specific niche concept are you building? (Round Variant 42)", 1, "", "", "", "", 1, current_time),
        ("What's your ultimate road trip singing anthem when you are completely alone driving on the highway? (Round Variant 43)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is the most unusual or surprising location where you have accidentally fallen completely asleep? (Round Variant 44)", 1, "", "", "", "", 1, current_time),
        ("What specific modern technology or app feature do you think is actively making human socialization worse? (Round Variant 45)", 1, "", "", "", "", 1, current_time),
        ("If you could travel back in time to witness any historical live music performance, what year are you visiting? (Round Variant 46)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is the single most controversial food opinion that you will proudly defend until the day you die? (Round Variant 47)", 1, "", "", "", "", 1, current_time),
        ("What specific physical item or collectible hobby token do you find yourself constantly hoarding or buying? (Round Variant 48)", 1, "", "", "", "", 1, current_time),
        ("What's your ideal sleeping environment setup: complete arctic freezing cold or total cozy tropical warmth? (Round Variant 49)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What local park or green space in town provides your absolute favorite afternoon picnic hideout? (Round Variant 50)", 1, "", "", "", "", 1, current_time),
        ("What is your absolute go-to hot drink option when working under extreme deadline stress? (Round Variant 51)", 1, "", "", "", "", 1, current_time),
        ("Which classic retro video game cabinet consumes the most of your pocket change at an arcade? (Round Variant 52)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What specific fashion trend from your teenage years do you look back on with pure existential regret? (Round Variant 53)", 1, "", "", "", "", 1, current_time),
        ("If you had to live inside one television sitcom universe for an entire calendar year, which are you choosing? (Round Variant 54)", 1, "", "", "", "", 1, current_time),
        ("What is the most bizarre or unusual food combination that you swear tastes completely delicious? (Round Variant 55)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("How many unread notifications or emails are currently sitting on your phone screen right now? (Round Variant 56)", 1, "", "", "", "", 1, current_time),
        ("What's your personal rule on when it is socially acceptable to start playing holiday music during winter? (Round Variant 57)", 1, "", "", "", "", 1, current_time),
        ("What is the ultimate urban legend or conspiracy theory that you secretly think might actually be true? (Round Variant 58)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("Which specific board game is guaranteed to completely destroy a peaceful family gathering or friendship circle? (Round Variant 59)", 1, "", "", "", "", 1, current_time),
        ("What's your favorite obscure trivia fact that you use to sound incredibly smart at cocktail parties? (Round Variant 60)", 1, "", "", "", "", 1, current_time),
        ("If you could have any fictional animal creature as a fully domesticated house pet, what are you choosing? (Round Variant 61)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is the single worst text message typo you have ever accidentally sent to a professional boss or client? (Round Variant 62)", 1, "", "", "", "", 1, current_time),
        ("How do you prefer to arrange your digital desktop app layout: pure sterile minimalism or total absolute clutter? (Round Variant 63)", 1, "", "", "", "", 1, current_time),
        ("What classic book or literary masterpiece did you completely fake reading back during high-school English class? (Round Variant 64)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What's your ultimate comfort movie that you have watched at least twenty times in your life? (Round Variant 65)", 1, "", "", "", "", 1, current_time),
        ("What specific house chore or domestic task do you find weirdly therapeutic and actually look forward to doing? (Round Variant 66)", 1, "", "", "", "", 1, current_time),
        ("If you were forced to open a themed restaurant, what hyper-specific niche concept are you building? (Round Variant 67)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What's your ultimate road trip singing anthem when you are completely alone driving on the highway? (Round Variant 68)", 1, "", "", "", "", 1, current_time),
        ("What is the most unusual or surprising location where you have accidentally fallen completely asleep? (Round Variant 69)", 1, "", "", "", "", 1, current_time),
        ("What specific modern technology or app feature do you think is actively making human socialization worse? (Round Variant 70)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("If you could travel back in time to witness any historical live music performance, what year are you visiting? (Round Variant 71)", 1, "", "", "", "", 1, current_time),
        ("What is the single most controversial food opinion that you will proudly defend until the day you die? (Round Variant 72)", 1, "", "", "", "", 1, current_time),
        ("What specific physical item or collectible hobby token do you find yourself constantly hoarding or buying? (Round Variant 73)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What's your ideal sleeping environment setup: complete arctic freezing cold or total cozy tropical warmth? (Round Variant 74)", 1, "", "", "", "", 1, current_time),
        ("What local park or green space in town provides your absolute favorite afternoon picnic hideout? (Round Variant 75)", 1, "", "", "", "", 1, current_time),
        ("What is your absolute go-to hot drink option when working under extreme deadline stress? (Round Variant 76)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("Which classic retro video game cabinet consumes the most of your pocket change at an arcade? (Round Variant 77)", 1, "", "", "", "", 1, current_time),
        ("What specific fashion trend from your teenage years do you look back on with pure existential regret? (Round Variant 78)", 1, "", "", "", "", 1, current_time),
        ("If you had to live inside one television sitcom universe for an entire calendar year, which are you choosing? (Round Variant 79)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is the most bizarre or unusual food combination that you swear tastes completely delicious? (Round Variant 80)", 1, "", "", "", "", 1, current_time),
        ("How many unread notifications or emails are currently sitting on your phone screen right now? (Round Variant 81)", 1, "", "", "", "", 1, current_time),
        ("What's your personal rule on when it is socially acceptable to start playing holiday music during winter? (Round Variant 82)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is the ultimate urban legend or conspiracy theory that you secretly think might actually be true? (Round Variant 83)", 1, "", "", "", "", 1, current_time),
        ("Which specific board game is guaranteed to completely destroy a peaceful family gathering or friendship circle? (Round Variant 84)", 1, "", "", "", "", 1, current_time),
        ("What's your favorite obscure trivia fact that you use to sound incredibly smart at cocktail parties? (Round Variant 85)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("If you could have any fictional animal creature as a fully domesticated house pet, what are you choosing? (Round Variant 86)", 1, "", "", "", "", 1, current_time),
        ("What is the single worst text message typo you have ever accidentally sent to a professional boss or client? (Round Variant 87)", 1, "", "", "", "", 1, current_time),
        ("How do you prefer to arrange your digital desktop app layout: pure sterile minimalism or total absolute clutter? (Round Variant 88)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What classic book or literary masterpiece did you completely fake reading back during high-school English class? (Round Variant 89)", 1, "", "", "", "", 1, current_time),
        ("What's your ultimate comfort movie that you have watched at least twenty times in your life? (Round Variant 90)", 1, "", "", "", "", 1, current_time),
        ("What specific house chore or domestic task do you find weirdly therapeutic and actually look forward to doing? (Round Variant 91)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("If you were forced to open a themed restaurant, what hyper-specific niche concept are you building? (Round Variant 92)", 1, "", "", "", "", 1, current_time),
        ("What's your ultimate road trip singing anthem when you are completely alone driving on the highway? (Round Variant 93)", 1, "", "", "", "", 1, current_time),
        ("What is the most unusual or surprising location where you have accidentally fallen completely asleep? (Round Variant 94)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What specific modern technology or app feature do you think is actively making human socialization worse? (Round Variant 95)", 1, "", "", "", "", 1, current_time),
        ("If you could travel back in time to witness any historical live music performance, what year are you visiting? (Round Variant 96)", 1, "", "", "", "", 1, current_time),
        ("What is the single most controversial food opinion that you will proudly defend until the day you die? (Round Variant 97)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What specific physical item or collectible hobby token do you find yourself constantly hoarding or buying? (Round Variant 98)", 1, "", "", "", "", 1, current_time),
        ("What's your ideal sleeping environment setup: complete arctic freezing cold or total cozy tropical warmth? (Round Variant 99)", 1, "", "", "", "", 1, current_time),
        ("What local park or green space in town provides your absolute favorite afternoon picnic hideout? (Round Variant 100)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is your absolute go-to hot drink option when working under extreme deadline stress? (Round Variant 101)", 1, "", "", "", "", 1, current_time),
        ("Which classic retro video game cabinet consumes the most of your pocket change at an arcade? (Round Variant 102)", 1, "", "", "", "", 1, current_time),
        ("What specific fashion trend from your teenage years do you look back on with pure existential regret? (Round Variant 103)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("If you had to live inside one television sitcom universe for an entire calendar year, which are you choosing? (Round Variant 104)", 1, "", "", "", "", 1, current_time),
        ("What is the most bizarre or unusual food combination that you swear tastes completely delicious? (Round Variant 105)", 1, "", "", "", "", 1, current_time),
        ("How many unread notifications or emails are currently sitting on your phone screen right now? (Round Variant 106)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What's your personal rule on when it is socially acceptable to start playing holiday music during winter? (Round Variant 107)", 1, "", "", "", "", 1, current_time),
        ("What is the ultimate urban legend or conspiracy theory that you secretly think might actually be true? (Round Variant 108)", 1, "", "", "", "", 1, current_time),
        ("Which specific board game is guaranteed to completely destroy a peaceful family gathering or friendship circle? (Round Variant 109)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What's your favorite obscure trivia fact that you use to sound incredibly smart at cocktail parties? (Round Variant 110)", 1, "", "", "", "", 1, current_time),
        ("If you could have any fictional animal creature as a fully domesticated house pet, what are you choosing? (Round Variant 111)", 1, "", "", "", "", 1, current_time),
        ("What is the single worst text message typo you have ever accidentally sent to a professional boss or client? (Round Variant 112)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("How do you prefer to arrange your digital desktop app layout: pure sterile minimalism or total absolute clutter? (Round Variant 113)", 1, "", "", "", "", 1, current_time),
        ("What classic book or literary masterpiece did you completely fake reading back during high-school English class? (Round Variant 114)", 1, "", "", "", "", 1, current_time),
        ("What's your ultimate comfort movie that you have watched at least twenty times in your life? (Round Variant 115)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What specific house chore or domestic task do you find weirdly therapeutic and actually look forward to doing? (Round Variant 116)", 1, "", "", "", "", 1, current_time),
        ("If you were forced to open a themed restaurant, what hyper-specific niche concept are you building? (Round Variant 117)", 1, "", "", "", "", 1, current_time),
        ("What's your ultimate road trip singing anthem when you are completely alone driving on the highway? (Round Variant 118)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is the most unusual or surprising location where you have accidentally fallen completely asleep? (Round Variant 119)", 1, "", "", "", "", 1, current_time),
        ("What specific modern technology or app feature do you think is actively making human socialization worse? (Round Variant 120)", 1, "", "", "", "", 1, current_time),
        ("If you could travel back in time to witness any historical live music performance, what year are you visiting? (Round Variant 121)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What is the single most controversial food opinion that you will proudly defend until the day you die? (Round Variant 122)", 1, "", "", "", "", 1, current_time),
        ("What specific physical item or collectible hobby token do you find yourself constantly hoarding or buying? (Round Variant 123)", 1, "", "", "", "", 1, current_time),
        ("What's your ideal sleeping environment setup: complete arctic freezing cold or total cozy tropical warmth? (Round Variant 124)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What local park or green space in town provides your absolute favorite afternoon picnic hideout? (Round Variant 125)", 1, "", "", "", "", 1, current_time),
        ("What is your absolute go-to hot drink option when working under extreme deadline stress? (Round Variant 126)", 1, "", "", "", "", 1, current_time),
        ("Which classic retro video game cabinet consumes the most of your pocket change at an arcade? (Round Variant 127)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("What specific fashion trend from your teenage years do you look back on with pure existential regret? (Round Variant 128)", 1, "", "", "", "", 1, current_time),
        ("If you had to live inside one television sitcom universe for an entire calendar year, which are you choosing? (Round Variant 129)", 1, "", "", "", "", 1, current_time),
        ("What is the most bizarre or unusual food combination that you swear tastes completely delicious? (Round Variant 130)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("How many unread notifications or emails are currently sitting on your phone screen right now? (Round Variant 131)", 1, "", "", "", "", 1, current_time),
        ("What's your personal rule on when it is socially acceptable to start playing holiday music during winter? (Round Variant 132)", 1, "", "", "", "", 1, current_time),
        ("What is the ultimate urban legend or conspiracy theory that you secretly think might actually be true? (Round Variant 133)", 0, "Option A Vibe", "Option B Vibe", "Option C Choice", "Option D Standout", 1, current_time),
        ("Which specific board game is guaranteed to completely destroy a peaceful family gathering or friendship circle? (Round Variant 134)", 1, "", "", "", "", 1, current_time),
        ("What's your favorite obscure trivia fact that you use to sound incredibly smart at cocktail parties? (Round Variant 135)", 1, "", "", "", "", 1, current_time),
    ]

    return page("Community Analytics", body)
