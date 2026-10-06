# Design: Yale look and Handsome Dan

Goal: make Campus Customs look and feel like it belongs to Yale, since it sells officially licensed Yale merchandise.

## Yale visual identity

Taken from www.yale.edu's stylesheets and Yale's identity guidelines (yaleidentity.yale.edu/colors).

| Element | Value | Used for |
|---|---|---|
| Yale Blue | `#00356b` | Nav bar, home banner, footer, headings, prices, buttons, chat header, shopper's chat bubbles |
| Yale Intensity Blue | `#286dc0` | Links, hover states, focus outlines, "From your chat" label |
| Text and background | `#222` on white | Body text and pages (light theme, replacing the earlier dark purple) |
| Headings font | YaleNew → Palatino / Book Antiqua | Page titles, product names on detail pages, chat header |
| Body font | Mallory → Gill Sans / Calibri | All other text |

- Fonts use yale.edu's own font stacks. YaleNew and Mallory are licensed Yale typefaces, so their files weren't copied. They show only where installed; everyone else gets yale.edu's fallbacks.
- No official Yale logo or wordmark is used. The browser-tab icon is a Yale Blue "CC" monogram.
- Buttons flip to white on blue areas (nav bar, banner) so they stay visible.
- All colors live as CSS variables at the top of `frontend/src/index.css`.

## Handsome Dan

Yale's bulldog mascot ties the store to Yale tradition. The 1889 photo of Handsome Dan I (credit: Yale Manuscripts & Archives) is used in three places.

**1. Home page banner**
- The black-and-white photo sits on the right of the Yale Blue banner. A luminosity blend tints it blue, and a left-edge fade keeps the headline readable.
- On phones it becomes a faint watermark behind the centered text.
- A small credit line names him and the source. The tagline ends with "Boola boola!"

**2. Welcome intro (first Home visit per session, under 5 seconds)**
- A round badge of Dan's face swoops in, loops around the page leaving fading 🐾 paw prints, pauses to say "Woof! Boola boola!", and zooms off.
- The banner text fades up line by line, and the photo eases in.
- It never blocks clicks, runs once per browser session, and is skipped when the device is set to reduce motion.

**3. The chatbot is Handsome Dan**
- The chat button reads "Ask Handsome Dan", with his face in a round avatar. The same avatar appears in the chat header and beside each of his messages.
- Greeting: "Woof! I'm Handsome Dan! I'm here to help you find the perfect Yale gear…"
- Progress lines in character: "Sniffing through the catalogue for hoodies…"
- Persona in `backend/prompts/prompt.md`: friendly, Yale-proud, at most one "Woof!" per reply, and it says he's an AI if asked. The fact-checking and safety rules are unchanged.

## Design rules we kept

- **Readability first:** dark text on white, and white text only on Yale Blue. Dan's photo is always faded behind text, never on top of it.
- **Decorative images are hidden from screen readers** (`alt=""`, `aria-hidden`).
- **Motion is short, one-time, and optional,** respecting `prefers-reduced-motion`.
- **One avatar, used everywhere:** a single photo, cropped with CSS, for the banner, intro badge, and chat. There are no extra image files.

Files: `frontend/src/index.css` (theme, banner, intro, avatar), `frontend/src/components/HandsomeDanIntro.tsx`, `frontend/src/pages/Home.tsx`, `frontend/src/components/ChatWidget.tsx`, `frontend/public/images/handsome-dan-1889.jpg`.
