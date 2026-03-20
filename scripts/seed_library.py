"""Seed the template library — generate templates and store in DB + S3 + Pinecone.

Usage:
    cd backend
    python scripts/seed_library.py

Requires: PINECONE_API_KEY, DATABASE_URL, S3_BUCKET env vars (or uses defaults from .env.example)
"""

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pinecone import Pinecone
from config.database import get_session
from config.s3 import upload_to_s3
from models.template_library import TemplateLibraryItem

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "pcsk_XoFm1_C5wauDJj49GctiXGSD4tYsF8mZSEN6f6mBRUKTNf5g5F1JtqcwZgJAo1bEfccwJ")
PINECONE_INDEX = "template-library"

# Template definitions — each will be generated as a full email
TEMPLATES = [
    # SaaS
    {"slug": "saas-welcome", "name": "SaaS Welcome Email", "industry": "saas", "purpose": "welcome", "tone": "professional",
     "description": "Professional SaaS welcome email with dark blue hero, feature highlights in 3 columns, getting started CTA, and clean footer. Ideal for onboarding new users."},
    {"slug": "saas-product-launch", "name": "SaaS Product Launch", "industry": "saas", "purpose": "launch", "tone": "professional",
     "description": "Product launch announcement for SaaS companies. Hero with product name, key features section, pricing highlights, and early adopter CTA."},
    {"slug": "saas-newsletter", "name": "SaaS Monthly Newsletter", "industry": "saas", "purpose": "newsletter", "tone": "casual",
     "description": "Monthly newsletter template for SaaS products. Updates section, tips column, featured article, and community links."},
    {"slug": "saas-trial-ending", "name": "SaaS Trial Ending", "industry": "saas", "purpose": "re-engagement", "tone": "urgent",
     "description": "Urgent trial expiration email for SaaS. Countdown urgency block, feature recap, upgrade CTA with pricing, and support contact."},

    # E-commerce
    {"slug": "ecom-welcome", "name": "E-commerce Welcome", "industry": "ecommerce", "purpose": "welcome", "tone": "friendly",
     "description": "Friendly welcome email for online stores. Brand hero, popular products grid, first-order discount coupon, and shopping CTA."},
    {"slug": "ecom-sale", "name": "E-commerce Flash Sale", "industry": "ecommerce", "purpose": "sale", "tone": "urgent",
     "description": "Flash sale email with bold urgency. Hero with discount percentage, product showcase grid, coupon code banner, countdown text, and shop now CTA."},
    {"slug": "ecom-product-launch", "name": "E-commerce New Arrivals", "industry": "ecommerce", "purpose": "launch", "tone": "friendly",
     "description": "New product arrivals announcement. Hero image, 2-column product cards with images and prices, collection link, and footer."},
    {"slug": "ecom-abandoned-cart", "name": "Abandoned Cart Recovery", "industry": "ecommerce", "purpose": "re-engagement", "tone": "friendly",
     "description": "Cart recovery email. Reminder heading, product image with name and price, checkout CTA, customer support link, and footer."},
    {"slug": "ecom-newsletter", "name": "E-commerce Newsletter", "industry": "ecommerce", "purpose": "newsletter", "tone": "casual",
     "description": "Weekly e-commerce newsletter. Featured product hero, trending items grid, style tips section, and social media links footer."},

    # Health & Fitness
    {"slug": "health-welcome", "name": "Fitness App Welcome", "industry": "health", "purpose": "welcome", "tone": "friendly",
     "description": "Energetic welcome email for fitness apps. Motivational hero, 3-column benefits (workouts, nutrition, tracking), getting started steps, and download CTA."},
    {"slug": "health-promo", "name": "Gym Membership Sale", "industry": "health", "purpose": "sale", "tone": "urgent",
     "description": "Gym membership promotion. Bold hero with discount, membership tiers comparison, limited time urgency block, and sign up CTA."},
    {"slug": "health-newsletter", "name": "Wellness Newsletter", "industry": "health", "purpose": "newsletter", "tone": "friendly",
     "description": "Weekly wellness newsletter. Health tip of the week, workout spotlight, nutrition recipe, and motivational quote."},

    # Food & Restaurant
    {"slug": "food-welcome", "name": "Restaurant Welcome", "industry": "food", "purpose": "welcome", "tone": "friendly",
     "description": "Warm restaurant welcome email. Hero with ambiance image, menu highlights, first-visit discount, reservation CTA, and location footer."},
    {"slug": "food-promo", "name": "Food Delivery Promo", "industry": "food", "purpose": "sale", "tone": "casual",
     "description": "Food delivery promotion. Hero with food image, featured dishes grid, promo code banner, order now CTA, and delivery info."},
    {"slug": "food-event", "name": "Restaurant Event Invite", "industry": "food", "purpose": "event", "tone": "friendly",
     "description": "Restaurant event invitation. Event details hero, menu preview, chef spotlight, RSVP button, and venue info footer."},

    # Education
    {"slug": "edu-welcome", "name": "Online Course Welcome", "industry": "education", "purpose": "welcome", "tone": "professional",
     "description": "Course platform welcome email. Hero with platform name, course categories in 3 columns, instructor spotlight, and start learning CTA."},
    {"slug": "edu-launch", "name": "New Course Launch", "industry": "education", "purpose": "launch", "tone": "professional",
     "description": "New course announcement. Course hero with title, curriculum overview, instructor bio, early bird pricing, and enroll CTA."},
    {"slug": "edu-newsletter", "name": "Education Newsletter", "industry": "education", "purpose": "newsletter", "tone": "casual",
     "description": "Educational newsletter. Featured article, learning tips, student success story, upcoming webinars, and community links."},

    # Events
    {"slug": "event-conference", "name": "Conference Invitation", "industry": "events", "purpose": "event", "tone": "professional",
     "description": "Conference invitation email. Event hero with date/location, speaker lineup in 3 columns, agenda highlights, register CTA, and venue info."},
    {"slug": "event-webinar", "name": "Webinar Invitation", "industry": "events", "purpose": "event", "tone": "casual",
     "description": "Webinar invitation. Topic hero, speaker bio with photo, key takeaways checklist, register button, and calendar reminder."},
    {"slug": "event-followup", "name": "Post-Event Thank You", "industry": "events", "purpose": "welcome", "tone": "friendly",
     "description": "Post-event thank you email. Thank you hero, event highlights, recording link, feedback survey CTA, and next event teaser."},

    # Real Estate
    {"slug": "realestate-welcome", "name": "Real Estate Welcome", "industry": "real_estate", "purpose": "welcome", "tone": "professional",
     "description": "Real estate agent welcome email. Professional hero, services overview, featured listings, consultation CTA, and contact info footer."},
    {"slug": "realestate-listing", "name": "New Property Listing", "industry": "real_estate", "purpose": "launch", "tone": "professional",
     "description": "New property listing announcement. Property hero image, key details (beds/baths/sqft), feature highlights, schedule viewing CTA, and agent contact."},
    {"slug": "realestate-newsletter", "name": "Real Estate Market Update", "industry": "real_estate", "purpose": "newsletter", "tone": "professional",
     "description": "Monthly real estate market newsletter. Market stats section, featured listings grid, buyer/seller tips, and consultation CTA."},

    # Agency
    {"slug": "agency-welcome", "name": "Agency Welcome", "industry": "agency", "purpose": "welcome", "tone": "professional",
     "description": "Creative agency welcome email. Bold hero with tagline, services in 3 columns, client testimonial, portfolio CTA, and contact footer."},
    {"slug": "agency-case-study", "name": "Agency Case Study", "industry": "agency", "purpose": "newsletter", "tone": "professional",
     "description": "Case study email. Client hero with results stats, challenge/solution/result sections, testimonial quote, and consultation CTA."},
    {"slug": "agency-launch", "name": "Agency Service Launch", "industry": "agency", "purpose": "launch", "tone": "casual",
     "description": "New service announcement. Service hero, benefits checklist, pricing overview, limited intro offer, and book a call CTA."},

    # Cross-industry
    {"slug": "generic-sale", "name": "Generic Sale Announcement", "industry": "other", "purpose": "sale", "tone": "urgent",
     "description": "Universal sale email. Bold discount hero, featured items grid, coupon code block, urgency countdown text, and shop CTA."},
    {"slug": "generic-newsletter", "name": "Generic Newsletter", "industry": "other", "purpose": "newsletter", "tone": "casual",
     "description": "All-purpose newsletter. Featured content hero, 2-column articles, tips section, and social footer."},
    {"slug": "generic-thankyou", "name": "Thank You Email", "industry": "other", "purpose": "welcome", "tone": "friendly",
     "description": "Universal thank you email. Warm hero, appreciation message, next steps, helpful resources, and contact footer."},
]


def build_template_components(spec):
    """Build a basic template component tree for a library item.

    Uses presets to compose: hero + content + cta + footer.
    """
    from engine.presets import local_preset_loader
    from engine.builder import inject_preset

    template = {"components": []}

    # Pick hero based on tone
    hero_preset = "hero-bold" if spec["tone"] in ("urgent", "professional") else "hero-minimal"
    hero = local_preset_loader(hero_preset)
    hero["customizations"] = {
        "headline": spec["name"].replace("Email", "").replace("Template", "").strip(),
        "primaryColor": "#1a1a2e" if spec["tone"] == "professional" else "#2563EB",
    }
    if "subtitle" in (hero.get("variables") or {}):
        hero["customizations"]["subtitle"] = spec["description"][:80]
    template = inject_preset(template, hero)

    # Add content based on purpose
    if spec["purpose"] in ("sale", "launch"):
        content = local_preset_loader("product-2col")
        template = inject_preset(template, content)

    if spec["purpose"] in ("newsletter", "event"):
        content = local_preset_loader("content-text-image")
        template = inject_preset(template, content)

    # Add CTA
    cta = local_preset_loader("cta-single")
    cta["customizations"] = {"heading": "Ready to get started?", "buttonText": "Get Started"}
    template = inject_preset(template, cta)

    # Add footer
    footer = local_preset_loader("footer-simple")
    template = inject_preset(template, footer)

    return template["components"]


def upsert_to_pinecone(pc_index, items):
    """Upsert template descriptions to Pinecone with integrated embedding."""
    vectors = []
    for item in items:
        text = f"{item['industry']} {item['purpose']} {item['tone']} email template. {item['description']}"
        vectors.append({
            "id": item["slug"],
            "values": None,  # Will use integrated embedding
            "metadata": {
                "slug": item["slug"],
                "name": item["name"],
                "industry": item["industry"],
                "purpose": item["purpose"],
                "tone": item["tone"],
                "description": item["description"],
            },
        })

    # Pinecone with integrated embedding — use upsert with text
    # For now, use a simple hash-based approach since integrated embedding
    # requires specific model configuration
    import hashlib
    import struct

    for v in vectors:
        text = f"{v['metadata']['industry']} {v['metadata']['purpose']} {v['metadata']['tone']} {v['metadata']['description']}"
        # Generate deterministic embedding from text hash (placeholder until real embeddings)
        h = hashlib.sha256(text.encode()).digest()
        # Expand to 1024 dimensions
        embedding = []
        for i in range(1024):
            byte_idx = i % len(h)
            embedding.append((h[byte_idx] / 255.0) * 2 - 1)  # normalize to [-1, 1]
        v["values"] = embedding

    # Batch upsert
    batch_size = 50
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        pc_index.upsert(vectors=batch)

    print(f"Upserted {len(vectors)} vectors to Pinecone")


def main():
    print(f"Seeding {len(TEMPLATES)} templates...")

    # Connect to Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)
    pc_index = pc.Index(PINECONE_INDEX)

    session = get_session()

    try:
        for spec in TEMPLATES:
            slug = spec["slug"]
            print(f"  {slug}...", end=" ")

            # Check if exists
            existing = session.query(TemplateLibraryItem).filter_by(slug=slug).first()
            if existing:
                print("exists, skipping")
                continue

            # Build components
            components = build_template_components(spec)

            # Store in S3
            s3_key = f"library/{slug}.json"
            template_json = json.dumps({
                "templateName": spec["name"],
                "components": components,
            }, ensure_ascii=False)

            try:
                upload_to_s3(s3_key, template_json.encode("utf-8"), "application/json")
            except Exception as e:
                print(f"S3 upload failed: {e}")
                s3_key = ""

            # Store in DB
            item = TemplateLibraryItem(
                id=str(uuid.uuid4()),
                slug=slug,
                name=spec["name"],
                description=spec["description"],
                industry=spec["industry"],
                purpose=spec["purpose"],
                tone=spec["tone"],
                layout_style="standard",
                components=components,
                s3_key=s3_key,
            )
            session.add(item)
            session.commit()
            print("done")

        # Upsert all to Pinecone
        print("\nUpserting to Pinecone...")
        all_items = session.query(TemplateLibraryItem).filter_by(is_active=True).all()
        upsert_to_pinecone(pc_index, [t.to_summary() for t in all_items])

        stats = pc_index.describe_index_stats()
        print(f"\nDone! DB: {len(all_items)} templates, Pinecone: {stats.total_vector_count} vectors")

    finally:
        session.close()


if __name__ == "__main__":
    main()
