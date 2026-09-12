#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "Cotton Flat Quiz"; 
const int TOTAL_QUESTIONS = 120; // 100 base prompts + 20 approved additions
const int QUEUE_SIZE = 10;
const char* ADMIN_PASS = "1346";

struct Question {
    String text;
    bool isOpenText;
    String options;             
};

Question quiz[TOTAL_QUESTIONS];
int totalActiveQuestions = 100;    
int voteCounts[TOTAL_QUESTIONS]; 

const int MAX_POOL_RESPONSES = 100; 
struct TextResponse {
    int questionId;
    String message;
};
TextResponse textPool[MAX_POOL_RESPONSES];
int poolCount = 0;

Question suggestionQueue[QUEUE_SIZE];
int queueCount = 0;

WebServer server(80);

String getPageHeader(String title) {
    String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'><title>" + title + "</title>";
    html += "<style>body{font-family:sans-serif; text-align:center; padding:15px; background:#f4f4f9; color:#333;} .card{background:white; padding:20px; border-radius:10px; box-shadow:0 4px 8px rgba(0,0,0,0.1); max-width:500px; margin:auto; margin-bottom:15px;} button, .btn{display:block; width:100%; margin:10px 0; padding:12px; font-size:16px; border:none; border-radius:5px; background:#007bff; color:white; cursor:pointer; text-decoration:none; box-sizing: border-box;} button:hover, .btn:hover{background:#0056b3;} .btn-sec{background:#6c757d;} .btn-sec:hover{background:#5a6268;} .btn-ok{background:#28a745;} .btn-ok:hover{background:#218838;} .btn-del{background:#dc3545;} .btn-del:hover{background:#bd2130;} .bar-container{background:#e9ecef; border-radius:5px; margin:8px 0; text-align:left; font-size:14px;} .bar{background:#17a2b8; height:25px; border-radius:5px; line-height:25px; color:white; padding-left:10px;} .bar-label{padding:5px 0 0 5px; font-weight:bold; text-align:left;} input, textarea, select{width:100%; padding:12px; margin:10px 0; border:1px solid #ccc; border-radius:5px; box-sizing: border-box; font-size:16px;} .resp-box{background:#f8f9fa; border-left:4px solid #007bff; padding:10px; margin:8px 0; text-align:left; border-radius:0 5px 5px 0; font-style:italic; font-size:15px; word-wrap:break-word;}</style></head><body><div class='card'>";
    return html;
}
void loadPrompts1to35() {
    quiz[0] = {"If your unedited web search history from the past year was put on a billboard, what would require the longest explanation?", true, {"", "", "", ""}};
    quiz[1] = {"You make accidental eye contact with a stranger on a crowded subway. What is your automatic behavioral coping mechanism?", false, {"Look down and scroll on your phone.", "Smile awkwardly and look away.", "Double down and stare back aggressively.", "Pretend you didn't even notice."}};
    quiz[2] = {"If a new law made everyone's personal income public and searchable, how would your friends treat each other?", true, {"", "", "", ""}};
    quiz[3] = {"An alien civilization demands we show them humanity's single greatest crowning achievement. What are we handing them?", false, {"The concept of 24-hour fast food drives.", "Internet compilation videos of cats.", "The blueprint of the microchip.", "Reality television rerun marathons."}};
    quiz[4] = {"What is a minor unwritten social rule that you break constantly just to feel a tiny, trivial spark of personal rebellion?", true, {"", "", "", ""}};
    quiz[5] = {"You get an unexpected phone call from a totally unrecognized number. What does your social anxiety make you do?", false, {"Answer it using a completely fake accent.", "Stare at the screen in pure dread until it stops.", "Google the number while it is actively ringing.", "Send an immediate text asking: 'Who is this?'"}};
    quiz[6] = {"If humans could read minds, but you could only hear the thoughts of people who actively dislike you, would you want this power?", true, {"", "", "", ""}};
    quiz[7] = {"You enter a building and a person is just a little bit too far away behind you. What is your default door-holding choice?", false, {"Hold it anyway and endure the awkward jog-walk.", "Let it close and pretend you didn't see them.", "Speed up your own walk to completely lose them.", "Hold it but look visibly annoyed while doing it."}};
    quiz[8] = {"If society collectively agreed that lying was legal and expected for just one full day, what industry would collapse first?", true, {"", "", "", ""}};
    quiz[9] = {"Which modern social trend will look the most absurdly ridiculous to historians living 100 years in the future?", false, {"Filming yourself dancing in public spaces.", "Buying virtual clothing for online gaming avatars.", "Paying premium fees for food delivery apps.", "Answering automated text surveys like this."}};
    quiz[10] = {"What is the most socially acceptable lie that everyone tells almost daily?", true, {"", "", "", ""}};
    quiz[11] = {"You walk into an empty elevator, and someone boards right after you and stands immediately next to you. How do you react?", false, {"Step to the opposite corner subtly.", "Ask them directly if they need personal space.", "Stare at the floor buttons intensely.", "Sigh loudly to show your discomfort."}};
    quiz[12] = {"If you could read the mind of your pet for ten minutes, what are you most afraid to find out?", true, {"", "", "", ""}};
    quiz[13] = {"What is the unwritten law of the grocery store checkout line that drives you insane when broken?", false, {"Leaving your cart to grab a last-second item.", "Putting items back on random incorrect shelves.", "Breathing down the neck of the person ahead.", "Using the express lane with double the item limit."}};
    quiz[14] = {"If personal fashion styles were regulated by social credit scores, what would your current outfit rank you?", true, {"", "", "", ""}};
    quiz[15] = {"You drop a piece of food on your clean kitchen floor. What rule dictates your response?", false, {"The absolute 5-second rule.", "The 10-second rule if it looks tasty.", "Throw it away immediately, germs are real.", "Eat it off the floor regardless of time."}};
    quiz[16] = {"What completely useless talent or knowledge do you possess that you are weirdly proud of?", true, {"", "", "", ""}};
    quiz[17] = {"Someone leaves a shopping cart in the middle of an empty parking spot right next to the cart return. What is your internal verdict?", false, {"A clear indicator of a failing civilization.", "Completely understandable if it's raining.", "Unfortunate, but not my business.", "I will aggressively return it for them."}};
    quiz[18] = {"If you could mandate one basic life skill class that everyone must pass before adulthood, what is it?", true, {"", "", "", ""}};
    quiz[19] = {"You realize you've been walking the wrong direction on a busy sidewalk. How do you turn around?", false, {"Stop, check your phone, snap your fingers, then turn.", "Do a dramatic pivot and look angry at the sky.", "Keep walking straight and circle the entire block.", "Just turn around normally like a sane human."}};
    quiz[20] = {"What habit from childhood are you secretly still doing as a fully grown adult?", true, {"", "", "", ""}};
    quiz[21] = {"A casual acquaintance says 'What's up?' as they walk past you. What is your response?", false, {"Say 'Good, how are you?' and immediately regret it.", "Nod and repeat 'What's up?' back.", "Keep walking and pretend you had headphones in.", "Stop and try to start an actual conversation."}};
    quiz[22] = {"If you could permanently ban one corporate buzzword from ever being spoken again, what is it?", true, {"", "", "", ""}};
    quiz[23] = {"You are at a house party where you only know the host, and they step away. Where do you go?", false, {"Stand by the food/snack table awkwardly.", "Locate the nearest pet and bond with it.", "Sit on the couch and scroll your phone.", "Leave immediately without saying goodbye."}};
    quiz[24] = {"What is a luxury service that is quietly making our generation completely helpless?", true, {"", "", "", ""}};
    quiz[25] = {"You are leaving a store empty-handed. What does your subconscious force you to do?", false, {"Act completely natural so security doesn't judge you.", "Keep your hands out of your pockets.", "Walk out as fast as physically possible.", "Buy a piece of cheap gum just to have a receipt."}};
    quiz[26] = {"If you had to choose a single food item that society replaces all currency with, what are we trading?", true, {"", "", "", ""}};
    quiz[27] = {"You wave back at someone who was actually waving at the person standing directly behind you. What do you do?", false, {"Keep your hand up and smoothly pretend to stretch.", "Put your hand down and walk into oncoming traffic.", "Laugh it off out loud so they know you knew.", "Look behind you to check who it actually was."}};
    quiz[28] = {"What is an unwritten rule of streaming platform profile sharing that must never be broken?", true, {"", "", "", ""}};
    quiz[29] = {"You are watching a movie at home with a partner and they fall asleep. What is your protocol?", false, {"Pause it immediately and wait for them.", "Keep watching but promise to fake surprise later.", "Finish it and tell them the entire ending.", "Turn it off and do something else."}};
    quiz[30] = {"If all text messages required a mandatory truth-filter that blocked lies, how many friends would you have left?", true, {"", "", "", ""}};
    quiz[31] = {"What is your default behavioral response when a server brings you the completely wrong restaurant order?", false, {"Eat it anyway and say it's exactly what you wanted.", "Politely inform them of the mistake.", "Send it back aggressively and demand a manager.", "Let your dining partner complain on your behalf."}};
    quiz[32] = {"What is the most ridiculous hill you are absolutely willing to die on?", true, {"", "", "", ""}};
    quiz[33] = {"You hear your own voice on a recorded audio message. What is your reaction?", false, {"Absolute disgust and instant denial.", "Acceptance, I sound completely normal.", "Confusion, that cannot be what I sound like.", "Never listening to a voice note ever again."}};
    quiz[34] = {"If society allowed you to remove one mandatory social custom from weddings or holidays, what goes?", true, {"", "", "", ""}};
}
void loadPrompts35to70() {
    quiz[35] = {"You see someone you know from high school at the grocery store. What is your immediate strategy?", false, {"Make zero eye contact and navigate to a new aisle.", "Walk straight up to them and say hello.", "Hide behind a display case until they leave.", "Stare until they notice you first."}};
    quiz[36] = {"What is the most useless piece of trivia taking up permanent residence in your brain?", true, {"", "", "", ""}};
    quiz[37] = {"You are texting someone and see the typing bubbles appear, then disappear. What is your internal state?", false, {"Pure existential panic and overanalysis.", "Mild curiosity about what they deleted.", "Absolute indifference, they will text eventually.", "Send an immediate follow-up text to prompt them."}};
    quiz[38] = {"What is a rule about email etiquette that you secretly think is a giant waste of time?", true, {"", "", "", ""}};
    quiz[39] = {"You open a bag of chips in a completely silent room. How do you handle the noise?", false, {"Open it with one massive, swift rip.", "Slowly peel it open over a grueling three minutes.", "Go to a completely different room to open it.", "Pour them out onto a napkin immediately."}};
    quiz[40] = {"What is a major red flag in a person's house that immediately makes you judge them?", true, {"", "", "", ""}};
    quiz[41] = {"You enter a public restroom and every stall is empty except one. Which stall do you choose?", false, {"The absolute furthest stall away from them.", "The stall directly next to them to establish dominance.", "The middle stall regardless of where they are.", "Leave and find a different restroom entirely."}};
    quiz[42] = {"What is something that is widely considered a scam but society treats as completely normal?", true, {"", "", "", ""}};
    quiz[43] = {"You are walking and realize your shoe is squeaking with every single step. What is your move?", false, {"Alter your walking gait to minimize the friction.", "Walk incredibly fast to get out of public view.", "Embrace the noise and march proudly.", "Take your shoes off and walk barefoot."}};
    quiz[44] = {"If you could hear a live laugh-track in your head whenever something funny happens, would you turn it on?", true, {"", "", "", ""}};
    quiz[45] = {"What is the supreme, definitive king of all chip flavors?", false, {"Nacho Cheese.", "Sour Cream and Onion.", "Barbecue.", "Classic Salted."}};
    quiz[46] = {"What is a household chore that you will procrastinate on until it becomes an emergency?", true, {"", "", "", ""}};
    quiz[47] = {"You are boarding a plane and someone is in your assigned window seat. How do you handle it?", false, {"Politely clear your throat and show your ticket stub.", "Take the middle seat and complain internally.", "Call a flight attendant over immediately.", "Stare at them until they move out of guilt."}};
    quiz[48] = {"What is a trend in modern architecture or interior design that you absolutely detest?", true, {"", "", "", ""}};
    quiz[49] = {"How many unread emails are currently sitting in your main personal inbox?", false, {"Zero, I am an inbox zero perfectionist.", "Between 1 and 50.", "A couple hundred clean alerts.", "Thousands, it is a digital wasteland."}};
    quiz[50] = {"What is the most irrational fear you still harbor from childhood?", true, {"", "", "", ""}};
    quiz[51] = {"You are running late to a social gathering. What is your text template format?", false, {"'On my way!' (I am still in bed).", "'Running 5 mins late!' (It will be 30).", "The absolute raw truth about your delay.", "No text, just arrive late and hope for the best."}};
    quiz[52] = {"If you could command an army of 10,000 small animals to do your bidding, which animal are you choosing?", true, {"", "", "", ""}};
    quiz[53] = {"You are at a checkout counter and the card reader fails twice. What is your fallback joke statement?", false, {"'Guess it's free then!'", "'Must be out of money!'", "Silence and intense sweating.", "Blame the technology processing framework."}};
    quiz[54] = {"What is an opinion you hold that would instantly get you kicked out of a food lover's club?", true, {"", "", "", ""}};
    quiz[55] = {"You see a coin on the ground heads-down. What do you do?", false, {"Flip it over for the next person's luck.", "Pick it up anyway, money is money.", "Ignore it completely, coins are outdated.", "Kick it down the sidewalk subtly."}};
    quiz[56] = {"What is a song that you will absolutely never skip if it comes on the radio?", true, {"", "", "", ""}};
    quiz[57] = {"You are matching paths on a sidewalk with an oncoming pedestrian and enter the side-step dance. What is the execution play?", false, {"Stop completely and let them make the decision.", "Point dynamically to the side you are taking.", "Fake left, go right swiftly.", "Look down and crash directly into them."}};
    quiz[58] = {"If you could change the sound of a car horn to any noise or phrase, what should it be?", true, {"", "", "", ""}};
    quiz[59] = {"What is your absolute maximum threshold for waiting on hold before hanging up?", false, {"Under 5 minutes, my time is valuable.", "15 minutes standard compliance.", "An hour if it is an emergency.", "I will leave it speaker-phoned all day."}};
    quiz[60] = {"What is the most bizarre food combination that you secretly think is an elite masterpiece?", true, {"", "", "", ""}};
    quiz[61] = {"You accidentally drop ice on the floor near the dispenser. What is your cleanup protocol?", false, {"Kick it under the refrigerator unit subtly.", "Pick it up and throw it in the sink.", "Leave it there to melt into the floorboards.", "Call for someone else to resolve the problem."}};
    quiz[62] = {"What is the single worst text message response a person can send?", true, {"", "", "", ""}};
    quiz[63] = {"You are packing for a three-day weekend trip. How many outfits are you packing?", false, {"Exactly three structured layouts.", "Four, just in case of an accident.", "Ten, I must prepare for every climate event.", "Whatever fits in a school backpack."}};
    quiz[64] = {"What is the most annoying notification sound or alert in existence?", true, {"", "", "", ""}};
    quiz[65] = {"You hear a noise in your house at 3 AM. What is your weapon of choice?", false, {"A heavy flashlight or bat.", "Your bare fists and pure adrenaline.", "Pull the blankets completely over your head.", "Check the security app matrix from bed."}};
    quiz[66] = {"If your pet could speak one sentence to you right now, what would it be?", true, {"", "", "", ""}};
    quiz[67] = {"You are splitting a bill at dinner and someone suggests tracking it to the exact penny. Your verdict?", false, {"Absolute approval, accuracy matters.", "Annoyance, just divide it evenly.", "I will pay for the whole thing to avoid the math.", "I am the person tracking the pennies."}};
    quiz[68] = {"What is an object you own that you refuse to throw away despite it being totally broken?", true, {"", "", "", ""}};
    quiz[69] = {"You are selecting a movie to stream. How long do you browse before actually picking something?", false, {"Under two minutes, I pick instantly.", "15 minutes of dynamic trailers.", "An hour, then I give up and go to sleep.", "I stream the same show I've seen 40 times."}};
}
void loadPrompts71to100() {
    quiz[70] = {"What is a completely harmless word that makes you cringe when spoken aloud?", true, {"", "", "", ""}};
    quiz[71] = {"You are at a grocery store self-checkout and the machine alerts 'Unexpected item in bagging area.' Your state?", false, {"Pure rage at the mechanical framework.", "Panic, I think I am accidentally stealing.", "Silence, I wait for assistance patiently.", "I begin re-arranging items frantically."}};
    quiz[72] = {"If you could speak any language fluently tonight, which one are you unlocking?", true, {"", "", "", ""}};
    quiz[73] = {"What is your standard protocol for dealing with a software update alert on your computer?", false, {"Remind me tomorrow (repeated for 6 months).", "Install immediately, security matters.", "Ignore until the machine forces a restart.", "Click update then walk away in frustration."}};
    quiz[74] = {"What is something from your past that you look back on and think 'Why did I think that was cool?'", true, {"", "", "", ""}};
    quiz[75] = {"You drop your phone face-down on concrete. What is your pick-up delay sequence?", false, {"Pick it up instantly to get it over with.", "Leave it there for 5 seconds to prepare mentally.", "Slide it with your foot to inspect it first.", "Pray out loud before turning it over."}};
    quiz[76] = {"What is the most overrated cinematic masterpiece in history?", true, {"", "", "", ""}};
    quiz[77] = {"You are ordering a drink at a busy bar counter. What strategy do you employ?", false, {"Hold cash out visibly to attract the bartender.", "Stare intensely at their eyes without blinking.", "Shout your order above the noise layout.", "Wait patiently until they naturally find you."}};
    quiz[78] = {"What is an absolute dealbreaker trait in a roommate or house guest?", true, {"", "", "", ""}};
    quiz[79] = {"You have a small piece of trash in public and no bin is visible. Where does it go?", false, {"Pocket it until you find a proper trash receptacle.", "Drop it subtly behind a bench or tree planter.", "Hold onto it for hours until you get home.", "Leave it on a shelf inside a retail store store."}};
    quiz[80] = {"What is a corporate policy or rule that you break constantly without guilt?", true, {"", "", "", ""}};
    quiz[81] = {"You are using a public keyboard. What thoughts cross your subconscious mind?", false, {"Absolute biological horror at the germ matrix.", "Indifference, keyboards are clean enough.", "I will wash my hands immediately after using it.", "I try to type using only my knuckles."}};
    quiz[82] = {"What is a personal preference or habit you have that makes people look at you sideways?", true, {"", "", "", ""}};
    quiz[83] = {"You buy an item online and see it goes on a 50% sale the next morning. Your play?", false, {"E-mail customer support demanding a price adjustment.", "Buy a second one and return it on the old receipt.", "Internalize the economic sadness and move on.", "Leave a highly aggressive 1-star product review."}};
    quiz[84] = {"What is an absolute golden law of road-trip car ownership that passengers must respect?", true, {"", "", "", ""}};
    quiz[85] = {"You are typing a message and autofill suggests a completely unhinged word layout. Your response?", false, {"Delete it and type the clean word manually.", "Send it anyway to see if they notice.", "Laugh out loud at your phone screen matrix.", "Question your entire digital browsing history profile."}};
    quiz[86] = {"What is a product or app that completely changed your lifestyle for the better?", true, {"", "", "", ""}};
    quiz[87] = {"You are at a buffets queue line and someone cuts ahead of you. Your course of action?", false, {"Clear your throat loudly and stare at their head.", "Politely say 'Excuse me, the line starts back there.'", "Do nothing but complain to the person behind you.", "Cut ahead of them at the next station out of spite."}};
    quiz[88] = {"What is a social media app that you deleted or abandoned because it became too toxic?", true, {"", "", "", ""}};
    quiz[89] = {"You are inside a public space and realize your phone volume slider is tracking max audio. Your protocol?", false, {"Mute it instantly with pure reflex velocity.", "Drop your phone on the floor out of sheer panic.", "Pretend it was someone else's phone ringing.", "Let the video play out of defiance."}};
    quiz[90] = {"What is a life advice quote or saying that you think is completely fake or unhelpful?", true, {"", "", "", ""}};
    quiz[91] = {"You are writing a professional email. How many exclamation marks are permitted?", false, {"Zero, professionalism requires strict periods.", "Exactly one at the very end greeting line.", "Multiple marks to hide your internal dread.", "I use emojis instead of punctuation blocks."}};
    quiz[92] = {"What is a physical item that you buy way too much of despite already owning plenty?", true, {"", "", "", ""}};
    quiz[93] = {"You are at a drive-thru and they forget your sauce packet. Your navigation layout?", false, {"Park the car, walk inside, and demand the sauce.", "Drive away in silent sorrow, eating dry fries.", "Check the bag before leaving the window every time.", "Loop the entire drive-thru lane again for the packet."}};
    quiz[94] = {"What is a skill that you wish you learned during your childhood years?", true, {"", "", "", ""}};
    quiz[95] = {"You are checking out of a hotel room. What is your cleanup standard?", false, {"Make the bed and fold towels to look polite.", "Leave it like a standard disaster zone.", "Strip the sheets down to make it easy for staff.", "Check every single drawer four times for missing socks."}};
    quiz[96] = {"What is something that you secretly think you are better at than 90% of the world?", true, {"", "", "", ""}};
    quiz[97] = {"You are introduced to someone and forget their name within exactly three seconds. Your play?", false, {"Call them 'dude' or 'man' for the rest of the night.", "Ask them to type their info into your phone contact app.", "Admit the slip immediately and ask for it again.", "Avoid addressing them directly at all costs."}};
    quiz[98] = {"What is a bad habit you have that you are completely unwilling to change?", true, {"", "", "", ""}};
    quiz[99] = {"If you could add one custom unwritten law to the universe that everyone must follow, what is it?", true, {"", "", "", ""}};
}

int getRandomQuestionIndex(int progressStep) {
    unsigned long seed = (unsigned long)progressStep * 137 + 43;
    return seed % totalActiveQuestions;
}
void handleMenu() {
    String html = getPageHeader("Cotton Flat Quiz - Hub");
    html += "<h1>Cotton Flat Quiz</h1>";
    html += "<p style='color:#666; margin-bottom:25px;'>Welcome to the self-paced sociological thought experiment hub.</p>";
    html += "<a href='/game' class='btn' style='background:#28a745;'>▶️ Start / Resume Quiz</a>";
    html += "<a href='/publicPool' class='btn' style='background:#17a2b8;'>📋 Browse Public Responses Pool</a>"; // <-- New Public Board Router Link
    html += "<a href='/suggest' class='btn btn-sec'>💡 Suggest a Custom Question</a>";
    html += "<hr style='margin:40px 0; border:0; border-top:1px solid #eee;'>";
    html += "<a href='/admin?pass=" + String(ADMIN_PASS) + "' style='font-size:12px; color:#ccc; text-decoration:none;'>Host Admin Panel Login</a>";
    html += "</div></body></html>";
    server.send(200, "text/html", html);
}

void handleRoot() {
    int currentStep = 0; 
    if (server.hasHeader("Cookie")) {
        String cookie = server.header("Cookie");
        int pos = cookie.indexOf("quizStep=");
        if (pos != -1) { currentStep = cookie.substring(pos + 9).toInt(); }
    }
    if (currentStep >= totalActiveQuestions) {
        String html = getPageHeader("Quiz Completed!");
        html += "<h1>100 Prompts Completed!</h1><a href='/reset' class='btn'>🔄 Wipe Session & Restart</a>";
        html += "<a href='/' class='btn btn-sec'>🏠 Back to Main Menu</a></div></body></html>";
        server.send(200, "text/html", html); return;
    }
    int targetQuestion = getRandomQuestionIndex(currentStep);
    String html = getPageHeader("Cotton Flat Quiz");
    html += "<h1>Cotton Flat Quiz</h1><h3>Prompt Tracker: " + String(currentStep + 1) + " / " + String(totalActiveQuestions) + "</h3>";
    html += "<p style='font-size:19px; font-weight:bold; margin:20px 0; line-height:1.4;'> " + quiz[targetQuestion].text + "</p>";
    if (quiz[targetQuestion].isOpenText) {
        html += "<form action='/submit' method='POST'><textarea name='text_choice' rows='4' placeholder='Type response...' required></textarea><button type='submit' class='btn'>Submit Anonymously</button></form>";
    } else {
        for(int i = 0; i < 4; i++) {
            html += "<form action='/submit' method='POST'><input type='hidden' name='num_choice' value='" + String(i + 1) + "'><button type='submit'>" + quiz[targetQuestion].options[i] + "</button></form>";
        }
    }
    html += "<hr style='margin:25px 0; border:0; border-top:1px solid #eee;'><a href='/' class='btn btn-sec'>🏠 Exit to Main Menu</a></div></body></html>";
    server.send(200, "text/html", html);
}

void handleSubmit() {
    int currentStep = 0;
    if (server.hasHeader("Cookie")) {
        String cookie = server.header("Cookie");
        int pos = cookie.indexOf("quizStep=");
        if (pos != -1) { currentStep = cookie.substring(pos + 9).toInt(); }
    }
    if (currentStep >= totalActiveQuestions) { server.send(400, "text/plain", "Bad Request"); return; }
    int targetQuestion = getRandomQuestionIndex(currentStep);
    String html = getPageHeader("Crowd Board");
    html += "<h2>Response Authenticated!</h2>";
    if (quiz[targetQuestion].isOpenText) {
        if (server.hasArg("text_choice") && server.arg("text_choice") != "") {
            if (poolCount < MAX_POOL_RESPONSES) {
                textPool[poolCount].questionId = targetQuestion; textPool[poolCount].message = server.arg("text_choice"); poolCount++;
            } else {
                for(int i = 0; i < MAX_POOL_RESPONSES - 1; i++) { textPool[i] = textPool[i+1]; }
                textPool[MAX_POOL_RESPONSES - 1].questionId = targetQuestion; textPool[MAX_POOL_RESPONSES - 1].message = server.arg("text_choice");
            }
        }
        html += "<h3>What others wrote:</h3>"; bool foundAny = false;
        for(int i = 0; i < poolCount; i++) {
            if (textPool[i].questionId == targetQuestion) { html += "<div class='resp-box'>\"" + textPool[i].message + "\"</div>"; foundAny = true; }
        }
        if (!foundAny) { html += "<p style='color:#666;'>You're the first to log an input!</p>"; }
    } else {
        if (server.hasArg("num_choice")) {
            int selection = server.arg("num_choice").toInt();
            if (selection >= 1 && selection <= 4) { voteCounts[targetQuestion][selection - 1]++; }
        }
        int total = 0; for(int i=0; i<4; i++) total += voteCounts[targetQuestion][i];
        html += "<h3>All-Time Student Distribution:</h3>";
        for(int i = 0; i < 4; i++) {
            int votes = voteCounts[targetQuestion][i]; int pct = (total > 0) ? (votes * 100) / total : 0;
            html += "<div class='bar-label'>" + quiz[targetQuestion].options[i] + " (" + String(votes) + ")</div><div class='bar-container'><div class='bar' style='width:" + String(pct) + "%;'>" + String(pct) + "%</div></div>";
        }
    }
    int nextStep = currentStep + 1;
    server.sendHeader("Set-Cookie", "quizStep=" + String(nextStep) + "; Path=/; Max-Age=86400");
    html += "<a href='/game' class='btn'>➡️ Next Random Prompt</a><a href='/' class='btn btn-sec'>🏠 Exit to Main Menu</a></div></body></html>";
    server.send(200, "text/html", html);
}

void handleReset() {
    server.sendHeader("Set-Cookie", "quizStep=0; Path=/; Max-Age=86400"); server.sendHeader("Location", "/", true); server.send(302, "text/plain", "");
}
void handleSuggestForm() {
    String html = getPageHeader("Suggest a Question");
    html += "<h2>Suggest a Quiz Question</h2><form action='/submitsyn' method='POST'><input type='text' name='qtext' placeholder='Enter question text...' required><select name='qtype' id='qtype' onchange='var m=document.getElementById(\"mc\"); if(this.value==\"mc\"){m.style.display=\"block\";}else{m.style.display=\"none\";}'><option value='text'>Open Text Response</option><option value='mc'>Multiple Choice Options</option></select><div id='mc' style='display:none;'><input type='text' name='op1' placeholder='Option 1'><input type='text' name='op2' placeholder='Option 2'><input type='text' name='op3' placeholder='Option 3'><input type='text' name='op4' placeholder='Option 4'></div><button type='submit' class='btn-ok'>Submit for Review</button></form><a href='/' class='btn btn-sec'>🏠 Back to Main Menu</a></div></body></html>";
    server.send(200, "text/html", html);
}

void handleSuggestSubmit() {
    if (queueCount < QUEUE_SIZE) {
        suggestionQueue[queueCount].text = server.arg("qtext");
        if (server.arg("qtype") == "mc") {
            suggestionQueue[queueCount].isOpenText = false; suggestionQueue[queueCount].options[0] = server.arg("op1"); suggestionQueue[queueCount].options[1] = server.arg("op2"); suggestionQueue[queueCount].options[2] = server.arg("op3"); suggestionQueue[queueCount].options[3] = server.arg("op4");
        } else {
            suggestionQueue[queueCount].isOpenText = true;
        }
        queueCount++;
        String html = getPageHeader("Sent"); html += "<h2>Sent!</h2><p>Passed onto host moderation desk.</p><a href='/' class='btn'>Return to Menu</a></div></body></html>";
        server.send(200, "text/html", html);
    } else {
        server.send(200, "text/plain", "Queue full!");
    }
}

// --- Public Access Link: Let's everyone read logged open-text responses safely ---
void handlePublicPool() {
    String html = getPageHeader("Public Responses Pool");
    html += "<h1>Global Text Logs Feed</h1>";
    if (poolCount == 0) {
        html += "<p style='color:#666;'>No open text entries have been logged by players yet. Go answer a prompt to start the feed!</p>";
    } else {
        for (int i = poolCount - 1; i >= 0; i--) { 
            int qId = textPool[i].questionId;
            html += "<div style='text-align:left; border-bottom:1px solid #ccc; padding:12px 0;'>";
            html += "<small style='color:#17a2b8; font-weight:bold;'>Prompt Context:</small><br><b>" + quiz[qId].text + "</b><br>";
            html += "<div class='resp-box' style='margin-top:5px; background:#fff;'>\"" + textPool[i].message + "\"</div></div>";
        }
    }
    html += "<a href='/' class='btn btn-sec' style='margin-top:20px;'>🏠 Back to Main Menu</a></div></body></html>";
    server.send(200, "text/html", html);
}

void handleAdmin() {
    if (!server.hasArg("pass") || server.arg("pass") != ADMIN_PASS) { server.send(401, "text/plain", "Unauthorized. Usage: /admin?pass=1346"); return; }
    String html = getPageHeader("Admin Panel"); html += "<h1>Admin Dashboard</h1>";
    html += "<a href='/publicPool' class='btn' style='background:#17a2b8;'>📋 View People's Text Answers</a>"; // Shared routing profile endpoint
    html += "<div style='border: 2px solid #dc3545; padding: 15px; border-radius: 5px; margin: 20px 0; background: #fff5f5;'>";
    html += "<a href='/adminReset?pass=" + String(ADMIN_PASS) + "' class='btn btn-del' onclick='return confirm(\"Wipe all statistics?\");'>Wipe All Global Answers & Logs</a></div>";
    html += "<h2>Pending Submissions Queue (" + String(queueCount) + ")</h2>";
    if (queueCount == 0) { html += "<p style='color:#666;'>No submissions waiting.</p>"; } else {
        for (int i = 0; i < queueCount; i++) {
            html += "<div style='text-align:left; border-bottom:1px solid #eee; padding:10px 0;'><b>Q: " + suggestionQueue[i].text + "</b><br>";
            if (!suggestionQueue[i].isOpenText) { html += "1. " + suggestionQueue[i].options[0] + "<br>2. " + suggestionQueue[i].options[1] + "<br>"; } else { html += "<i>[Open Text Prompt Type]</i><br>"; }
            html += "<div style='display:flex; gap:10px; margin-top:10px;'><a href='/approve?pass=" + String(ADMIN_PASS) + "&idx=" + String(i) + "' class='btn btn-ok' style='padding:5px; margin:0;'>Approve</a><a href='/reject?pass=" + String(ADMIN_PASS) + "&idx=" + String(i) + "' class='btn btn-del' style='padding:5px; margin:0;'>Reject</a></div></div>";
        }
    }
    html += "<hr style='margin:25px 0; border:0; border-top:1px solid #eee;'><a href='/' class='btn btn-sec'>🏠 Exit to Main Menu</a></div></body></html>"; server.send(200, "text/html", html);
}

void handleAdminReset() {
    if (!server.hasArg("pass") || server.arg("pass") != ADMIN_PASS) { server.send(401, "text/plain", "Unauthorized."); return; }
    for(int q=0; q<TOTAL_QUESTIONS; q++) {
        for(int o=0; o<4; o++) voteCounts[q][o] = 0;
    }
    poolCount = 0; queueCount = 0; totalActiveQuestions = 100;
    loadPrompts1to35(); loadPrompts35to70(); loadPrompts71to100();
    String html = getPageHeader("Wipe Success"); html += "<h2>Logs Zeroed Out!</h2><a href='/admin?pass=" + String(ADMIN_PASS) + "' class='btn'>Return</a></div></body></html>";
    server.send(200, "text/html", html);
}

void handleApprove() {
    if (server.arg("pass") == ADMIN_PASS && server.hasArg("idx")) {
        int idx = server.arg("idx").toInt();
        if (idx >= 0 && idx < queueCount && totalActiveQuestions < TOTAL_QUESTIONS) {
            quiz[totalActiveQuestions] = suggestionQueue[idx];
            for(int o=0; o<4; o++) voteCounts[totalActiveQuestions][o] = 0;
            totalActiveQuestions++;
            for (int i = idx; i < queueCount - 1; i++) suggestionQueue[i] = suggestionQueue[i + 1];
            queueCount--;
        }
        server.sendHeader("Location", "/admin?pass=" + String(ADMIN_PASS), true); server.send(302, "text/plain", "");
    }
}

void handleReject() {
    if (server.arg("pass") == ADMIN_PASS && server.hasArg("idx")) {
        int idx = server.arg("idx").toInt();
        if (idx >= 0 && idx < queueCount) {
            for (int i = idx; i < queueCount - 1; i++) suggestionQueue[i] = suggestionQueue[i + 1];
            queueCount--;
        }
        server.sendHeader("Location", "/admin?pass=" + String(ADMIN_PASS), true); server.send(302, "text/plain", "");
    }
}

void setup() {
    Serial.begin(115200);
    for(int q=0; q<TOTAL_QUESTIONS; q++) {
        for(int o=0; o<4; o++) voteCounts[q][o] = 0;
    }
    loadPrompts1to35(); loadPrompts35to70(); loadPrompts71to100();
    WiFi.softAP(ssid); 
    const char * headerkeys[] = {"User-Agent", "Cookie"};
    size_t headerkeyssize = sizeof(headerkeys) / sizeof(char*);
    server.collectHeaders(headerkeys, headerkeyssize);
    server.on("/", HTTP_GET, handleMenu);
    server.on("/game", HTTP_GET, handleRoot);
    server.on("/submit", HTTP_POST, handleSubmit);
    server.on("/reset", HTTP_GET, handleReset);
    server.on("/suggest", HTTP_GET, handleSuggestForm);
    server.on("/submitsyn", HTTP_POST, handleSuggestSubmit);
    server.on("/publicPool", HTTP_GET, handlePublicPool); // Public viewing route register configuration
    server.on("/admin", HTTP_GET, handleAdmin);
    server.on("/adminReset", HTTP_GET, handleAdminReset);
    server.on("/approve", HTTP_GET, handleApprove);
    server.on("/reject", HTTP_GET, handleReject);
    server.begin();
}

void loop() {
    server.handleClient();
}
