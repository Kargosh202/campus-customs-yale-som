# Usability improvements

The improvements made to the Campus Customs site beyond the core build: what was added, and why it helps a Campus Customs shopper or the business.

| # | Improvement | Where |
|---|---|---|
| 1 | Sort products by price | Frontend |
| 2 | Yale theme (colors and fonts from yale.edu) | Frontend |
| 3 | Handsome Dan on the home page, with a welcome intro | Frontend |
| 4 | Faster-feeling chat replies: live progress and a speed benchmark | Backend + frontend |
| 5 | Audit trail of every chat answer | Backend |
| 6 | The chat assistant is Handsome Dan | Agent prompt + frontend |

Smaller fixes, both frontend and backend, are listed in the table at the end.

## 1. Sort products by price

**What I added**
- A **Sort by** dropdown on the Products page: Name (A to Z), Price: Low to High, Price: High to Low.
- Products with the same price (for example, every $68 hoodie) are listed alphabetically, so the order never shuffles.
- The choice is kept in the page address (`/products?sort=price-asc`). Opening a product and clicking back returns to the same sorted list, and a sorted link can be bookmarked or shared.

**Why it helps**
- **Shoppers:** most shoppers have a budget, and students especially. With 102 items, sorting by price lets them start from the $32 T-shirts or jump straight to the $98 jackets, instead of scrolling through everything.
- **Shoppers:** keeping the sort after opening a product means they don't lose their place while comparing items.
- **Business:** shoppers who find something in their price range quickly are more likely to buy, and less likely to leave.

## 2. Yale theme (colors and fonts from yale.edu)

**What I added**
- The site moved from dark purple to Yale's look, taken from www.yale.edu and Yale's identity guidelines:
  - **Yale Blue** (#00356b) for the navigation bar, banner, footer, headings, prices, and buttons.
  - **Yale Intensity Blue** (#286dc0) for links and focus outlines.
  - Dark gray text on white.
- yale.edu's own font choices: the Yale serif for headings and a Gill Sans-style sans-serif for text. The licensed Yale font files weren't copied, so the site uses the same fallbacks yale.edu does.
- A matching Yale Blue browser-tab icon.

**Why it helps**
- **Shoppers:** Campus Customs sells officially licensed Yale merchandise, so the site now looks like it belongs with Yale. Students, alumni, and parents recognize the colors, which builds trust that the gear is the real thing.
- **Shoppers:** a light background with dark text is easier to read for longer browsing, and product photos (mostly on white) blend into the page instead of sitting in bright boxes on a dark one.
- **Business:** a consistent brand look makes the store feel established and official, which supports its "Officially Licensed Yale Merchandise" position.

## 3. Handsome Dan on the home page (with a welcome intro)

**What I added**
- The Home page banner now has a historic photo of **Handsome Dan I**, Yale's first bulldog mascot (1889), blended into the Yale Blue background.
- On desktop he sits on the right side of the banner, tinted Yale Blue and fading into the background so the headline and Shop Products button stay easy to read.
- On phones he becomes a soft watermark behind the text.
- A small credit line names him and the source (Yale Manuscripts & Archives).
- The banner tagline gained a "Boola boola!"
- **A welcome intro** the first time a shopper opens the Home page in a visit:
  - A round Handsome Dan badge swoops in and explores the page, leaving a trail of paw prints.
  - He stops to bark "Woof! Boola boola!", then zooms off.
  - Meanwhile the banner text fades up piece by piece and his photo eases in. The whole intro takes under 5 seconds.
  - It plays only once per browser visit, never blocks clicks (the Shop Products button works during it), and is skipped for visitors whose device is set to reduce motion.

**Why it helps**
- **Shoppers:** students, alumni, and families recognize Handsome Dan straight away. Seeing him on the first screen makes the store feel like part of Yale tradition, not a generic shop.
- **Business:** it ties the brand to Yale's most recognizable mascot and its 130-year history, and supports the store's bulldog products (the chat assistant already knows "Handsome Dan" means bulldog gear).
- **Shoppers:** the intro gives a fun, memorable first impression. It's the kind of moment students share, and it shows the store doesn't take itself too seriously.
- **Business:** it's done without hurting usability. The photo and intro are decorative (screen readers skip them), the text contrast is unchanged, and the intro runs once, can't get in the way of clicking, and respects reduced-motion settings.

## 4. Faster-feeling chat replies (live progress)

**What I added**
- The chat now shows what the assistant is doing while it works, instead of a silent wait: "Searching the catalogue for gray crewnecks…", "Checking price and stock for Yale Mom Hoodie…", "Double-checking prices and stock…", with animated dots.
- The backend sends these updates as they happen, through a new streaming endpoint (`POST /api/chat/stream`).
- A benchmark script (`backend/benchmark.py`) measures reply time and checks answers at different reasoning settings. All settings answered 6 of 6 test questions correctly. The lower settings were about 1 to 2 seconds faster, so the store can trade a little reasoning for speed if it wants.
- The final answer still appears in one piece, only after it has passed the fact-check, so a wrong price can never flash on screen.

**Why it helps**
- **Shoppers:** a 5-to-10-second wait feels much shorter when you can see progress, and it tells them the assistant is actually looking up live stock, not guessing. That makes the answer more trustworthy.
- **Shoppers:** fewer people give up and close the chat while waiting.
- **Business:** the benchmark gives real numbers for choosing between speed and cost, instead of guessing.

## 5. Audit trail of every chat answer

**What I added**
- Every agent-loop step is appended to `output/audit_trail.json` (never wiped between runs):
  - the time, the page, and the shopper's question
  - every tool the assistant called, with short arguments and results (for example, the stock it saw for each size)
  - the stop reason of each step (finished, called a tool, content-filtered, or error), and any time the fact-check sent an answer back
  - the final answer, tokens used, and total time
- A report script (`backend/audit_report.py`) summarizes it: how runs ended, steps per message, response times, tool use, retries, and tokens. It can also show the last few conversations step by step.
- Privacy is built in:
  - Only the user's id is stored, never their name or password.
  - Email addresses and card-like numbers are blanked out.

**Why it helps**
- **Shoppers:** they benefit indirectly. If a shopper says "the bot told me this was in stock," staff can check exactly what stock the assistant saw at that moment, and fix the real cause.
- **Business:** this provides accountability for an AI that quotes prices and stock to customers. Staff can see what customers ask for most, spot items people want but the store doesn't carry (like shorts or hats), and keep an eye on speed and cost.
- **Business:** it has already caught three real problems during development, including a jailbreak attempt that left the assistant giving a confused reply, now fixed.

## 6. The chat assistant is Handsome Dan

**What I added**
- The chatbot now plays **Handsome Dan**, Yale's bulldog mascot.
- **The chat button** reads "Ask Handsome Dan", with his face on it.
- **The chat window** shows his photo and name in the header ("Handsome Dan, Campus Customs shopping assistant"), and his face appears next to each of his messages.
- **He opens with** "Woof! I'm Handsome Dan! I'm here to help you find the perfect Yale gear…". Returning shoppers get "Woof! Welcome back, <name>! It's Handsome Dan…".
- **His progress lines are in character:** "Sniffing through the catalogue for fleece jackets…", "Trotting through the whole catalogue…".
- **The system prompt** (`prompts/prompt.md`) gives him a persona: friendly, loyal, a little playful, proud of Yale, with light bulldog touches (an occasional "Woof!" or "sniffed out"). The answer always comes first.
- **Guardrails:**
  - All the honesty rules still apply: prices and stock only from the database, with the fact-check.
  - He says he's an AI assistant playing Handsome Dan if asked whether he's a real dog or a person.
  - He never claims to have tried products on.
  - He doesn't speak for Yale.

**Why it helps**
- **Shoppers:** chatting with Handsome Dan is friendlier and more memorable than "Campus Customs Assistant". A familiar mascot makes it more inviting to ask a question, especially for parents and visitors who might not otherwise use a chatbot.
- **Shoppers:** being clear that he's an AI keeps trust intact. In testing, asked "are you a real dog?", he answered that he's an AI shopping assistant playing Yale's bulldog mascot, then helped with the fleece question.
- **Business:** a character ties the store's brand to Yale's most beloved symbol and makes the shopping assistant a distinctive feature of the site, not a generic chatbot.

## Smaller usability fixes along the way

| Fix | Where | Why it helps |
|---|---|---|
| **"From your chat" product cards on the page.** When a shopper asks "what hoodies do you have?", matching products appear as cards (photo, name, price, short description) next to the chat | Backend + frontend | Shoppers see the actual products instead of reading a long text list, and can click straight through |
| **Every card opens the product page, at the top.** Clicking a card always opens the full product view (large photo, price, sizes, stock) with the image in view, and the chat results move below it | Frontend | Before the fix, a clicked card's product loaded far down the page and looked broken |
| **Chat closes on phones when a card is tapped** | Frontend | On a small screen the chat covers the page, so the product would otherwise open hidden behind it |
| **"Out of stock" wording everywhere,** in the chat and on product pages, plus "Only N left" for low stock | Agent + frontend | Clear, consistent stock language, so shoppers know immediately whether their size is available |
| **Chat history saved for logged-in shoppers, with "Welcome back, \<name\>!"** | Backend + frontend | Returning shoppers can pick up where they left off, and the assistant remembers what they were looking at |
| **The assistant knows which product page you're on.** "Do you have this in pink?" just works | Backend + agent | Shoppers don't have to retype product names |
| **"Show password" on Log In** | Frontend | Lets shoppers spot typos or autofill mistakes. It was added after a real failed login in testing |
| **About Us page with store and staff contact details,** with tap-to-call and tap-to-email links | Frontend + agent | Shoppers can reach a real person for things the assistant doesn't know (returns, hours), and the assistant points them there too |
| **Friendly form errors** ("Please enter a valid email address.", "Passwords do not match") | Backend | Clear guidance instead of technical validation messages, so fewer abandoned sign-ups |
| **Fact-check on every chat answer.** Each price and stock number must match what the database returned in that turn, or the answer is sent back and redone | Agent | Shoppers can trust the prices and sizes the assistant quotes. It never makes up a price or claims a sold-out size is available |
| **Prices always shown with cents** ("$59.50", never "$59.5") | Backend | Prices look like real store prices, every time |
| **Correct price ranges for big results** ("27 hoodies, $45.00 to $88.00", worked out across all matches, not just the ones shown) | Backend | Shoppers get an accurate sense of what's available in their budget |
| **Always-fresh answers.** The agent skips Portkey's response cache | Backend | Stock and prices are always live. It also fixed an error when the same question was asked twice |
| **A polite in-character decline** when the model provider blocks a message (e.g. a jailbreak attempt), instead of an error | Agent | Shoppers never see a broken chat. The assistant stays friendly and steers back to shopping |
