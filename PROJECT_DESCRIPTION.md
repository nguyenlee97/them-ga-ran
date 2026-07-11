# Finger-Chattin' Good

> One ordering brain. Two ways to enjoy KFC: a smarter self-order kiosk and a conversational ordering experience.

## Inspiration

I work in the Zalo Sales Tech team, where I see every day how the right conversational experience can make a digital interaction feel simple, helpful, and personal. That perspective made me ask: what if ordering KFC could feel less like navigating a static menu and more like being understood?

This project is also deeply personal. I have been a KFC customer for more than 10 years, and KFC has always been my favourite fried-chicken brand. There is a special sense of pride in building for a brand that has been part of so many everyday meals, celebrations, and catch-ups. **Finger-Chattin' Good** is my way of bringing together that long-time customer love with my experience in conversational commerce: helping every customer find the right meal, at the right moment, through the channel that feels most natural to them.

## What it does

Finger-Chattin' Good is an AI-powered ordering experience built around one shared KFC ordering brain.

- **Smarter self-order kiosk:** a faithful KFC Vietnam kiosk experience that recommends relevant drinks, sides, desserts, and better-value combos as a customer builds their order.
- **Conversational ordering:** a Vietnamese-first chat agent that can help customers discover menu items, build a cart, check loyalty information, apply eligible offers, confirm an order, and hand off to a person when needed.
- **Contextual recommendations:** recommendations respond to the current basket, dine-in or takeaway choice, time of day, store context, promotions, and, when a member is logged in, past orders.
- **One shared customer journey:** kiosks and chat use the same menu, cart, loyalty, recommendation, and order services, so the customer receives a consistent experience whichever front door they choose.

The current build uses the real KFC Vietnam menu, including real product information, prices, and images. Payments are intentionally mocked for the MVP.

## How we built it

We designed the product as a shared backend with two customer-facing experiences rather than two disconnected demos. The backend manages the menu, carts, orders, loyalty, vouchers, events, and recommendation requests. A dedicated AI service produces recommendations and powers the chat agent, while the kiosk presents those recommendations as helpful, touch-friendly prompts throughout checkout.

The recommendation engine is deliberately layered. It starts with explainable "frequently bought together" patterns and meal-completion suggestions, then can enrich results with member preferences and AI-written Vietnamese recommendation copy. This means the core experience remains useful even when optional AI services are unavailable.

We also built feedback into the product: every recommendation can be tracked when shown or accepted, creating a foundation for measuring conversion and improving future offers.

## Challenges we ran into

The biggest challenge was data realism. Without access to live KFC POS and behavioral data, our MVP cannot perfectly reproduce the complexity of real customer behavior, store availability, promotion rules, or seasonal demand.

To address this honestly, we used the real KFC Vietnam menu and created structured synthetic transaction histories that mirror plausible ordering patterns. The system is designed so real POS data can later be mapped into the same format and used without rebuilding the downstream recommendation experience. We also kept recommendations explainable and menu-grounded, rather than relying on an AI model to invent suggestions.

## Accomplishments that we're proud of

- Turned a static ordering flow into a more helpful, context-aware experience that aims to improve both convenience and discovery.
- Built one reusable ordering core for kiosk and chat, instead of duplicating menu and checkout logic across channels.
- Made the recommendation experience practical: it can suggest a missing drink or side, surface a dessert at the right moment, and offer a value-focused combo trade-up.
- Added member-aware personalization while preserving a useful experience for anonymous customers.
- Kept customer-facing AI safe and grounded: recommendations come from the real menu and backend validation remains the source of truth for carts, prices, and orders.
- Created a Vietnamese-first experience that is closer to how KFC Vietnam customers naturally order.

## What we learned

Building this project taught me much more about the F&B business domain. As a customer, I mainly think about what I want to eat. Looking at the experience from the perspective of someone managing KFC is completely different: every menu placement, recommendation, offer, and interaction can affect customer satisfaction, operational simplicity, and basket value.

I learned that good personalization in F&B is not just about recommending more items. It is about understanding the moment: is the customer completing a meal, ordering quickly for lunch, sharing with family, or looking for a familiar favourite? The most valuable AI does not make the experience feel complicated; it makes the next choice feel obvious.

## What's next for Finger-Chattin' Good

- Integrate real KFC POS, inventory, and promotion data to train and evaluate recommendations against real purchasing patterns.
- Deploy the conversational agent to Zalo Official Account, then extend the same ordering flow to Messenger.
- Add real payment, order-status tracking, and store-level availability for a production-ready journey.
- Use recommendation events to test which suggestion, placement, and message improve conversion and average order value.
- Introduce a contextual bandit to continuously learn the best offer for each ordering moment.
- Expand loyalty experiences with reorder shortcuts, personalised member offers, birthday rewards, and cross-channel cart continuity.
- Complete Vietnamese/English localisation and improve accessibility for a broader kiosk audience.

## Built with

- React, Vite, Tailwind CSS
- Node.js, Express, MongoDB, Mongoose
- Python, FastAPI, Uvicorn
- OpenAI API for optional chat orchestration, recommendation reranking, and Vietnamese copy
- FP-Growth / market-basket analysis with pandas and mlxtend
- Qdrant and FastEmbed for optional semantic menu search and embeddings
- Playwright for real KFC Vietnam menu collection
- Docker Compose for service deployment

## Optional Links

- Kiosk demo: `http://localhost:5173`
- Conversational-agent demo harness: `http://localhost:8080/agent/ui`
- Recommendation metrics dashboard: `http://localhost:3000/api/admin/dashboard`
- [System design](docs/DESIGN.md)
- [Recommendation-engine walkthrough](docs/RECOMMENDATION-EXPLAINED.md)
- [Demo scenarios](docs/DEMO-SCENARIOS.md)
