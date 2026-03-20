"""Build 30 unique email templates from detailed scenarios.

Each template is hand-crafted component by component — no preset reuse.
Unique palettes, real Unsplash images, realistic content.

Usage:
    cd backend
    DATABASE_URL="..." python3 scripts/build_library_v2.py
"""

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine import build_html
from config.database import get_session
from models.template_library import TemplateLibraryItem


def _id():
    return f"lib-{uuid.uuid4().hex[:8]}"


# ─── Component builders ───

def row(bg="#FFFFFF", padding="0", children=None):
    return {"id": _id(), "type": "row", "props": {"backgroundColor": bg, "padding": padding}, "styles": {}, "parentId": None, "children": children or [], "visibility": True, "locked": False}

def col(width="100%", bg="transparent", padding="0", children=None, parent_id=None):
    return {"id": _id(), "type": "column", "props": {"width": width, "backgroundColor": bg, "padding": padding}, "styles": {}, "parentId": parent_id, "children": children or [], "visibility": True, "locked": False}

def heading(text, level="h1", size=36, color="#FFFFFF", align="center", padding="10px 20px", family="Georgia, serif"):
    return {"id": _id(), "type": "heading", "props": {"content": text, "level": level, "fontSize": size, "color": color, "fontFamily": family, "textAlign": align, "padding": padding}, "styles": {}, "parentId": None, "children": [], "visibility": True, "locked": False}

def text(content, size=16, color="#666666", align="center", padding="5px 20px", family="Arial, sans-serif"):
    return {"id": _id(), "type": "text", "props": {"content": content, "fontSize": size, "color": color, "fontFamily": family, "textAlign": align, "padding": padding}, "styles": {}, "parentId": None, "children": [], "visibility": True, "locked": False}

def button(label, href="#", bg="#2563EB", color="#FFFFFF", padding="14px 36px", radius="6px", size=16, align="center"):
    return {"id": _id(), "type": "button", "props": {"text": label, "href": href, "backgroundColor": bg, "color": color, "padding": padding, "borderRadius": radius, "fontSize": size, "fontFamily": "Arial, sans-serif", "textAlign": align}, "styles": {}, "parentId": None, "children": [], "visibility": True, "locked": False}

def image(src, alt="Image", width="100%"):
    return {"id": _id(), "type": "image", "props": {"src": src, "alt": alt, "width": width, "height": "auto"}, "styles": {}, "parentId": None, "children": [], "visibility": True, "locked": False}

def spacer(height="20px"):
    return {"id": _id(), "type": "spacer", "props": {"height": height}, "styles": {}, "parentId": None, "children": [], "visibility": True, "locked": False}

def divider(color="#E5E7EB", width="1px", margin="20px 0"):
    return {"id": _id(), "type": "divider", "props": {"borderColor": color, "borderWidth": width, "margin": margin}, "styles": {}, "parentId": None, "children": [], "visibility": True, "locked": False}


# ─── Section builders (return a row) ───

def hero_dark(h1_text, sub_text, btn_text, bg, btn_bg, btn_color="#FFFFFF", h1_size=42, h1_family="Georgia, serif"):
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="50px 30px", children=[
        heading(h1_text, "h1", h1_size, "#FFFFFF", "center", "10px 20px", h1_family),
        spacer("10px"),
        text(sub_text, 18, "#E0E0E0", "center", "0 40px 20px"),
        button(btn_text, "#", btn_bg, btn_color),
        spacer("15px"),
    ])])

def hero_minimal(h2_text, sub_text, text_color="#333333", bg="#FFFFFF"):
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="40px 30px", children=[
        heading(h2_text, "h2", 28, text_color, "center", "0 20px 8px", "Arial, sans-serif"),
        text(sub_text, 15, "#888888" if bg == "#FFFFFF" else "#AAAAAA", "center", "0 40px"),
    ])])

def hero_image(h1_text, sub_text, btn_text, img_url, bg, btn_bg):
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="0", children=[
        image(img_url, h1_text),
        spacer("5px"),
        heading(h1_text, "h1", 36, "#FFFFFF", "center", "20px 20px 5px", "Georgia, serif"),
        text(sub_text, 16, "#CCCCCC", "center", "0 30px 15px"),
        button(btn_text, "#", btn_bg),
        spacer("20px"),
    ])])

def image_row(src, alt="Image"):
    return row(bg="#FFFFFF", children=[col(width="100%", padding="0", children=[image(src, alt)])])

def stats_row(s1_val, s1_lbl, s2_val, s2_lbl, s3_val, s3_lbl, accent="#2563EB", bg="#F8F9FA"):
    def stat_col(val, lbl):
        return col(width="33.33%", padding="20px 10px", children=[
            heading(val, "h2", 32, accent, "center", "0 0 4px"),
            text(lbl, 13, "#666666", "center", "0"),
        ])
    return row(bg=bg, children=[stat_col(s1_val, s1_lbl), stat_col(s2_val, s2_lbl), stat_col(s3_val, s3_lbl)])

def checklist_row(title, items, check_color="#22C55E", bg="#FFFFFF", text_color="#333333"):
    children = [heading(title, "h3", 20, text_color, "left", "0 0 10px", "Arial, sans-serif")]
    for item in items:
        children.append(text(f'<span style="color:{check_color};font-weight:bold;">&#10003;</span>&nbsp;&nbsp;{item}', 14, text_color, "left", "4px 0"))
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="25px 30px", children=children)])

def cta_row(h2_text, sub_text, btn_text, btn_bg="#2563EB", bg="#F8F9FA"):
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="30px", children=[
        heading(h2_text, "h2", 24, "#1a1a1a" if bg != "#1a1a1a" else "#FFFFFF", "center", "0 20px 6px", "Arial, sans-serif"),
        text(sub_text, 14, "#666666", "center", "0 40px 15px"),
        button(btn_text, "#", btn_bg),
    ])])

def dual_cta_row(h2_text, btn1_text, btn2_text, btn1_bg="#2563EB", btn2_bg="#6B7280", bg="#F8F9FA"):
    return row(bg=bg, children=[
        col(width="50%", bg=bg, padding="30px 15px 30px 30px", children=[
            heading(h2_text, "h2", 22, "#1a1a1a", "right", "0 0 12px", "Arial, sans-serif"),
            button(btn1_text, "#", btn1_bg, "#FFFFFF", "12px 24px"),
        ]),
        col(width="50%", bg=bg, padding="30px 30px 30px 15px", children=[
            heading("", "h2", 22, bg, "left", "0 0 12px", "Arial, sans-serif"),
            button(btn2_text, "#", btn2_bg, "#FFFFFF", "12px 24px"),
        ]),
    ])

def text_image_row(h3_text, body, img_url, bg="#FFFFFF", text_color="#333333"):
    return row(bg=bg, children=[
        col(width="50%", bg=bg, padding="25px", children=[
            heading(h3_text, "h3", 20, text_color, "left", "0 0 8px", "Arial, sans-serif"),
            text(body, 14, "#666666", "left", "0"),
        ]),
        col(width="50%", bg=bg, padding="10px", children=[
            image(img_url, h3_text),
        ]),
    ])

def testimonial_row(quote, author, role, accent="#2563EB", bg="#F8F9FA"):
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="30px 40px", children=[
        text(f'<em style="font-size:16px;color:#444;line-height:1.6;">"{quote}"</em>', 16, "#444444", "left", "0 0 15px"),
        divider(accent, "2px", "0 0 10px 0"),
        text(f'<strong>{author}</strong>', 14, "#333333", "left", "0"),
        text(role, 12, "#888888", "left", "0"),
    ])])

def coupon_row(title, code, expiry, btn_text, accent="#E91E63", bg="#FFF8F0"):
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="25px 30px", children=[
        heading(title, "h3", 20, accent, "center", "0 0 10px", "Arial, sans-serif"),
        text(f'<span style="display:inline-block;border:2px dashed {accent};padding:8px 24px;font-size:22px;font-weight:bold;letter-spacing:3px;color:{accent};font-family:monospace;">{code}</span>', 14, accent, "center", "5px 0"),
        text(expiry, 12, "#888888", "center", "8px 0 12px"),
        button(btn_text, "#", accent),
    ])])

def urgency_row(h2_text, body, btn_text, accent="#DC2626", bg="#FEF2F2"):
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="25px 30px", children=[
        heading(h2_text, "h2", 24, accent, "center", "0 0 8px", "Arial, sans-serif"),
        text(body, 14, "#7F1D1D" if "FEF" in bg else "#666666", "center", "0 30px 15px"),
        button(btn_text, "#", accent),
    ])])

def products_2col(p1_name, p1_price, p1_img, p2_name, p2_price, p2_img, accent="#E91E63", bg="#FFFFFF"):
    def prod(name, price, img):
        return col(width="50%", bg="#FFFFFF", padding="15px", children=[
            image(img, name),
            spacer("8px"),
            heading(name, "h3", 16, "#1a1a1a", "center", "4px", "Arial, sans-serif"),
            text(price, 18, accent, "center", "0 0 8px"),
            button("Shop Now", "#", accent, "#FFFFFF", "8px 20px", "4px", 13),
        ])
    return row(bg=bg, children=[prod(p1_name, p1_price, p1_img), prod(p2_name, p2_price, p2_img)])

def products_3col(p1_name, p1_price, p2_name, p2_price, p3_name, p3_price, accent="#E91E63", bg="#FFFFFF"):
    def prod(name, price):
        return col(width="33.33%", bg="#FFFFFF", padding="12px", children=[
            heading(name, "h3", 14, "#1a1a1a", "center", "4px", "Arial, sans-serif"),
            text(price, 16, accent, "center", "0 0 6px"),
            button("Shop", "#", accent, "#FFFFFF", "6px 16px", "4px", 12),
        ])
    return row(bg=bg, children=[prod(p1_name, p1_price), prod(p2_name, p2_price), prod(p3_name, p3_price)])

def featured_product_row(img_url, name, desc, price, btn_text, accent="#2563EB", bg="#FFFFFF"):
    return row(bg=bg, children=[
        col(width="50%", bg=bg, padding="10px", children=[image(img_url, name)]),
        col(width="50%", bg=bg, padding="25px 20px", children=[
            heading(name, "h2", 24, "#1a1a1a", "left", "0 0 8px", "Arial, sans-serif"),
            text(desc, 14, "#666666", "left", "0 0 10px"),
            text(f'<strong style="font-size:22px;color:{accent};">{price}</strong>', 14, accent, "left", "0 0 15px"),
            button(btn_text, "#", accent, "#FFFFFF", "10px 24px"),
        ]),
    ])

def footer_dark(company, address, unsub_url="#", bg="#111111", text_col="#999999", link_col="#4A90D9"):
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="15px 20px", children=[
        divider("#333333", "1px", "5px 0"),
        text(f'<strong>{company}</strong>', 13, text_col, "center", "8px 0 2px"),
        text(address, 11, "#666666", "center", "0 0 8px"),
        text(f'<a href="{unsub_url}" style="color:{link_col};">Unsubscribe</a>', 11, "#666666", "center", "0 0 10px"),
    ])])

def footer_social(company, social_text, unsub_url="#", bg="#111111", text_col="#999999", link_col="#4A90D9"):
    return row(bg=bg, children=[col(width="100%", bg=bg, padding="15px 20px", children=[
        text(social_text, 12, link_col, "center", "10px 0 5px"),
        divider("#333333", "1px", "5px 0"),
        text(f'<strong>{company}</strong>', 13, text_col, "center", "8px 0 2px"),
        text(f'<a href="{unsub_url}" style="color:{link_col};">Unsubscribe</a>', 11, "#666666", "center", "0 0 10px"),
    ])])


# ─── Unsplash URLs ───
IMG = {
    "team_collab": "https://images.unsplash.com/photo-1739298061740-5ed03045b280?w=600",
    "analytics": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600",
    "coding": "https://images.unsplash.com/photo-1603575448878-868a20723f5d?w=600",
    "data_viz": "https://images.unsplash.com/photo-1770681381576-f1fdceb2ea01?w=600",
    "fashion_model": "https://images.unsplash.com/photo-1618908623278-dfcf55e6f687?w=600",
    "shopping_bags": "https://images.unsplash.com/photo-1760565030307-f05068b2585d?w=600",
    "fashion_collection": "https://images.unsplash.com/photo-1772570824145-e996a55204fb?w=600",
    "leather_bag": "https://images.unsplash.com/photo-1598099947145-e85739e7ca28?w=600",
    "spring_fashion": "https://images.unsplash.com/photo-1650381612893-a7ec1c2a4557?w=600",
    "gym": "https://images.unsplash.com/photo-1584827386916-b5351d3ba34b?w=600",
    "fitness": "https://images.unsplash.com/photo-1771086559194-91fffc427573?w=600",
    "yoga": "https://images.unsplash.com/photo-1542354771-435b9f200e57?w=600",
    "fine_dining": "https://images.unsplash.com/photo-1761095596849-608b6a337c36?w=600",
    "gourmet": "https://images.unsplash.com/photo-1755811248324-3c9b7c8865fc?w=600",
    "bbq": "https://images.unsplash.com/photo-1702741168115-cd3d9a682972?w=600",
    "pasta": "https://images.unsplash.com/photo-1609166639722-47053ca112ea?w=600",
    "wine_dinner": "https://images.unsplash.com/photo-1703797967065-539818bc9770?w=600",
    "students": "https://images.unsplash.com/photo-1758612214882-03f8a1d7211f?w=600",
    "ai_tech": "https://images.unsplash.com/photo-1697577418970-95d99b5a55cf?w=600",
    "conference": "https://images.unsplash.com/photo-1762968269894-1d7e1ce8894e?w=600",
    "speaker": "https://images.unsplash.com/photo-1646369505567-3a9cbb052342?w=600",
    "luxury_home": "https://images.unsplash.com/photo-1706809019043-c16ada0165e9?w=600",
    "house_interior": "https://images.unsplash.com/photo-1648147870253-c45f6f430528?w=600",
    "house_sale": "https://images.unsplash.com/photo-1563002543-b217d7fddab5?w=600",
    "creative_workspace": "https://images.unsplash.com/photo-1742440710226-450e3b85c100?w=600",
    "website_mockup": "https://images.unsplash.com/photo-1617609277590-ec2d145ca13b?w=600",
    "remote_work": "https://images.unsplash.com/photo-1626065838283-d338b7702fed?w=600",
    "pro_woman": "https://images.unsplash.com/photo-1581065178047-8ee15951ede6?w=600",
}


# ─── All 30 Templates ───

TEMPLATES = {
    "saas-welcome": lambda: [
        hero_dark("Welcome to CloudSync", "Your files. Your team. Perfectly in sync — from anywhere in the world.", "Start Your Free Trial", "#0F172A", "#2563EB"),
        image_row(IMG["team_collab"], "Team collaboration"),
        stats_row("99.9%", "Uptime", "50,000+", "Teams Worldwide", "4.9/5", "User Rating", "#2563EB", "#EFF6FF"),
        checklist_row("Everything You Need", ["Unlimited cloud storage for your entire team", "Real-time collaboration on documents and files", "Bank-grade AES-256 encryption", "24/7 priority customer support"], "#2563EB", "#FFFFFF"),
        cta_row("Ready to transform your workflow?", "Join 50,000+ teams already using CloudSync. Free for 14 days.", "Get Started Free", "#2563EB", "#EFF6FF"),
        footer_dark("CloudSync Inc.", "100 Cloud Ave, San Francisco, CA 94107", "#", "#0F172A"),
    ],
    "saas-product-launch": lambda: [
        hero_image("Introducing Smart Analytics 2.0", "AI-powered insights that predict what's next for your business.", "See It In Action", IMG["analytics"], "#1E1B4B", "#7C3AED"),
        text_image_row("What's New", "Real-time dashboards with predictive forecasting. Automated reports delivered to your inbox. Custom KPI tracking with smart alerts.", IMG["data_viz"], "#FFFFFF"),
        testimonial_row("Smart Analytics transformed how we make decisions. We spotted a market shift two weeks before our competitors.", "Rachel Kim", "VP of Strategy, GrowthCo", "#7C3AED", "#F5F3FF"),
        dual_cta_row("Choose How to Start", "Start Free Trial", "Watch Demo Video", "#7C3AED", "#9CA3AF", "#F5F3FF"),
        footer_dark("Analytica Inc.", "200 Data Drive, Austin, TX 78701", "#", "#1E1B4B"),
    ],
    "saas-newsletter": lambda: [
        hero_minimal("DevFlow Monthly — March 2026", "Product updates, tips, and stories from our developer community.", "#18181B"),
        text_image_row("New: GitHub Integration", "Connect your repos directly to DevFlow. Auto-sync issues, PRs, and deployments. Set up in under 2 minutes.", IMG["coding"]),
        checklist_row("5 Ways to Ship Faster", ["Use feature flags to decouple deploys from releases", "Automate your CI/CD pipeline with DevFlow Actions", "Write tests for critical paths only", "Pair program on complex features"], "#10B981", "#ECFDF5"),
        cta_row("Read More on Our Blog", "Deep dives, tutorials, and engineering culture posts every week.", "Visit the Blog", "#10B981"),
        footer_dark("DevFlow Inc.", "42 Terminal St, Portland, OR 97201", "#", "#18181B"),
    ],
    "saas-trial-ending": lambda: [
        hero_dark("Your Trial Ends Tomorrow", "Don't lose access to your workspace and 14 days of progress.", "Upgrade Now", "#0F172A", "#DC2626"),
        urgency_row("Less Than 24 Hours Left", "After your trial expires, your account will be downgraded to the free plan. You'll lose team sharing, 50GB storage, and priority support.", "Upgrade to Pro — $19/mo", "#DC2626", "#FEF2F2"),
        checklist_row("What You'll Lose", ["50GB cloud storage (downgraded to 2GB)", "Team sharing and collaboration features", "Priority customer support", "API access and all integrations"], "#DC2626", "#FFFFFF"),
        cta_row("Need more time?", "Reply to this email and we'll extend your trial by 7 days. No strings attached.", "Contact Support", "#6B7280"),
        footer_dark("CloudSync Inc.", "100 Cloud Ave, San Francisco, CA 94107", "#", "#0F172A"),
    ],
    "ecom-welcome": lambda: [
        hero_dark("Welcome to UrbanThread", "Fashion that fits your life. Here's 15% off your first order.", "Shop Now", "#09090B", "#F43F5E"),
        image_row(IMG["fashion_model"], "Fashion model"),
        coupon_row("Your Welcome Gift", "WELCOME15", "Valid for 30 days from today", "Shop the Collection", "#F43F5E", "#FFF1F2"),
        products_2col("Summer Linen Shirt", "$49.99", "https://placehold.co/280x200/FFF1F2/F43F5E?text=Linen+Shirt", "Classic Chinos", "$59.99", "https://placehold.co/280x200/FFF1F2/F43F5E?text=Chinos", "#F43F5E"),
        cta_row("Free Shipping on Orders $75+", "Easy returns within 30 days. No questions asked.", "Start Shopping", "#F43F5E", "#FFF1F2"),
        footer_social("UrbanThread", "Twitter &nbsp;|&nbsp; Instagram &nbsp;|&nbsp; Pinterest", "#", "#09090B"),
    ],
    "ecom-sale": lambda: [
        hero_dark("FLASH SALE — 50% OFF", "24 hours only. Our biggest sale of the year. Everything must go.", "Shop the Sale", "#09090B", "#EF4444"),
        urgency_row("Ends at Midnight!", "Every item is 50% off. No exclusions, no minimum order. Free express shipping on all sale orders.", "Shop All Deals", "#EF4444"),
        products_3col("Leather Jacket", "$89 <s>$178</s>", "Silk Dress", "$64 <s>$128</s>", "Wool Coat", "$120 <s>$240</s>", "#EF4444"),
        coupon_row("Stack & Save", "FLASH10", "Extra 10% off — stack with sale prices!", "Apply at Checkout", "#EF4444", "#FEF2F2"),
        cta_row("Don't Wait — Sale Ends Tonight", "Free express shipping on all sale orders.", "Shop Now →", "#EF4444"),
        footer_dark("UrbanThread", "456 Fashion Blvd, New York, NY 10001", "#", "#09090B"),
    ],
    "ecom-product-launch": lambda: [
        hero_image("New Arrivals Just Dropped", "Fresh styles for the season. Be the first to shop.", "See What's New", IMG["fashion_collection"], "#292524", "#0D9488"),
        products_3col("Oversized Blazer", "$129", "Cropped Tee", "$34", "Wide-Leg Pants", "$79", "#0D9488"),
        text_image_row("The Spring Edit", "Master the art of layering this spring. Mix textures, play with proportions, and look effortlessly cool.", IMG["spring_fashion"], "#F0FDFA"),
        dual_cta_row("Complete Your Look", "Shop Women", "Shop Men", "#0D9488", "#6B7280", "#F0FDFA"),
        footer_social("UrbanThread", "Twitter &nbsp;|&nbsp; Instagram &nbsp;|&nbsp; Pinterest", "#", "#292524"),
    ],
    "ecom-abandoned-cart": lambda: [
        hero_minimal("You Left Something Behind", "Your cart is waiting. Complete your purchase before items sell out."),
        featured_product_row(IMG["leather_bag"], "Classic Leather Bag", "Hand-crafted Italian leather. Timeless design that gets better with age. Only 3 left in stock.", "$189.00", "Complete Purchase", "#F59E0B"),
        coupon_row("Need a nudge?", "COMEBACK10", "10% off — expires in 48 hours", "Return to Cart", "#F59E0B", "#FFFBEB"),
        cta_row("Questions? We're here to help.", "Free shipping · Easy returns · Secure checkout", "Complete Your Order", "#F59E0B"),
        footer_dark("UrbanThread", "456 Fashion Blvd, New York, NY 10001", "#", "#1C1917"),
    ],
    "ecom-newsletter": lambda: [
        hero_minimal("This Week at UrbanThread", "Trending picks, style guides, and exclusive deals curated for you.", "#475569"),
        text_image_row("Style Guide: Spring Layers", "Master the art of layering this spring. Mix textures, play with proportions, and stay warm while looking effortlessly cool.", IMG["spring_fashion"]),
        products_2col("Editor's Pick: Linen Blazer", "$98", "https://placehold.co/280x200/FAFAF9/E11D48?text=Blazer", "Trending: Cargo Pants", "$72", "https://placehold.co/280x200/FAFAF9/E11D48?text=Cargo", "#E11D48"),
        cta_row("Members Get Early Access", "Join our VIP list for 24-hour early access to new drops.", "Join VIP", "#E11D48", "#FAFAF9"),
        footer_social("UrbanThread", "Twitter &nbsp;|&nbsp; Instagram &nbsp;|&nbsp; Pinterest", "#", "#09090B"),
    ],
    "health-welcome": lambda: [
        hero_dark("Welcome to FitPulse", "Your journey to a healthier you starts now. Let's make every rep count.", "Start Your First Workout", "#064E3B", "#059669"),
        image_row(IMG["gym"], "Gym workout"),
        stats_row("500+", "Workouts", "50+", "Programs", "1M+", "Members", "#059669", "#F0FDF4"),
        checklist_row("Your FitPulse Membership", ["Personalized workout plans based on your goals", "Nutrition tracking with AI meal suggestions", "Progress photos and body measurements", "Live classes with certified trainers"], "#84CC16", "#FFFFFF"),
        cta_row("Start with a 7-Day Challenge", "Quick, effective workouts for all fitness levels. No equipment needed.", "Begin Challenge", "#059669", "#F0FDF4"),
        footer_dark("FitPulse Inc.", "789 Wellness Way, Los Angeles, CA 90001", "#", "#064E3B"),
    ],
    "health-promo": lambda: [
        hero_dark("New Year, New You — 40% Off", "Premium annual membership at the lowest price ever.", "Claim Your Spot", "#052E16", "#EAB308"),
        image_row(IMG["fitness"], "Fitness training"),
        urgency_row("Offer Ends January 31st", "Lock in $9.99/month (normally $16.99) for your entire first year. Cancel anytime.", "Get 40% Off Now", "#059669", "#DCFCE7"),
        testimonial_row("FitPulse changed my life. I've lost 30 lbs and gained confidence I never knew I had. The trainers are incredible.", "Sarah M.", "Member since 2024", "#059669", "#FFFFFF"),
        dual_cta_row("Choose Your Plan", "Annual — $9.99/mo", "Monthly — $16.99/mo", "#059669", "#6B7280", "#DCFCE7"),
        footer_dark("FitPulse Inc.", "789 Wellness Way, Los Angeles, CA 90001", "#", "#052E16"),
    ],
    "health-newsletter": lambda: [
        hero_minimal("Your Weekly Wellness Digest", "Workouts, nutrition tips, and motivation — every Monday.", "#0F766E"),
        text_image_row("Workout of the Week: HIIT Burn", "Torch calories in just 20 minutes with this high-intensity session. No equipment needed — do it anywhere.", IMG["yoga"]),
        checklist_row("5 Tips for Better Sleep", ["Set a consistent bedtime — even on weekends", "Avoid screens 30 minutes before bed", "Keep your room cool (65-68°F)", "Try a 10-minute evening stretch routine"], "#0F766E", "#F0FDFA"),
        cta_row("This Week's Challenge", "Drink 8 glasses of water every day for 7 days. Track in the app.", "Accept the Challenge", "#0F766E"),
        footer_dark("FitPulse Inc.", "789 Wellness Way, Los Angeles, CA 90001", "#", "#0F766E"),
    ],
    "food-welcome": lambda: [
        hero_dark("Welcome to Savory Bites", "Where every meal is an experience. Your table is ready.", "View Our Menu", "#450A0A", "#CA8A04"),
        image_row(IMG["fine_dining"], "Fine dining"),
        text_image_row("Chef's Table Experience", "Join Chef Marco for an intimate 7-course tasting menu every Saturday. Seasonal ingredients, inspired pairings.", IMG["gourmet"], "#FFFFFF"),
        coupon_row("First Visit Special", "WELCOME20", "20% off your first order — dine in or delivery", "Order Now", "#CA8A04", "#FEF9C3"),
        cta_row("Reserve Your Table", "Open Tuesday–Sunday, 5pm–11pm. Walk-ins welcome.", "Make a Reservation", "#CA8A04"),
        footer_dark("Savory Bites", "321 Culinary Lane, Chicago, IL 60601", "#", "#450A0A"),
    ],
    "food-promo": lambda: [
        hero_dark("Weekend Special: Family Feast", "Feed the whole family for $49. Order by Friday.", "Order the Feast", "#3B0764", "#EA580C"),
        products_2col("BBQ Platter for 4", "$49", IMG["bbq"], "Pasta Family Pack", "$39", IMG["pasta"], "#EA580C"),
        coupon_row("Free Dessert with Every Order", "SWEETDEAL", "This weekend only", "Add to Order", "#EA580C", "#FFF7ED"),
        cta_row("Free Delivery on Orders $30+", "Hot and fresh to your door in 45 minutes or less.", "Order Now", "#EA580C"),
        footer_dark("Savory Bites", "321 Culinary Lane, Chicago, IL 60601", "#", "#3B0764"),
    ],
    "food-event": lambda: [
        hero_image("Wine & Dine Night", "An evening of curated wines paired with Chef Marco's finest. March 28th.", "Reserve Your Spot", IMG["wine_dinner"], "#7F1D1D", "#F472B6"),
        checklist_row("What to Expect", ["5-course tasting menu by Chef Marco", "Wine pairings selected by our sommelier", "Live jazz performance", "Complimentary welcome cocktail"], "#F472B6", "#FDF2F8"),
        cta_row("Limited to 40 Guests", "Saturday, March 28th — 7:00 PM. Smart casual.", "RSVP Now — $95/person", "#F472B6"),
        footer_dark("Savory Bites", "321 Culinary Lane, Chicago, IL 60601", "#", "#7F1D1D"),
    ],
    "edu-welcome": lambda: [
        hero_dark("Welcome to LearnHub", "Thousands of courses. World-class instructors. Learn at your own pace.", "Explore Courses", "#312E81", "#0EA5E9"),
        image_row(IMG["students"], "Students learning"),
        stats_row("10K+", "Courses", "500+", "Instructors", "2M+", "Students", "#0EA5E9", "#E0F2FE"),
        checklist_row("Getting Started", ["Browse courses by topic or skill level", "Enroll in your first course — many are free", "Track progress with personalized dashboards", "Earn certificates to showcase your skills"], "#0EA5E9", "#FFFFFF"),
        cta_row("Start Learning Today", "Over 2,000 free courses to get you started.", "Browse Free Courses", "#0EA5E9", "#E0F2FE"),
        footer_dark("LearnHub", "500 Education Blvd, Boston, MA 02101", "#", "#312E81"),
    ],
    "edu-launch": lambda: [
        hero_image("New Course: AI for Everyone", "No coding required. Understand AI and the future of work.", "Enroll Now — Free", IMG["ai_tech"], "#1E3A5F", "#06B6D4"),
        text_image_row("What You'll Learn", "This 6-week course covers AI fundamentals, real-world applications, and how AI is transforming every industry. Perfect for beginners.", IMG["students"], "#FFFFFF"),
        testimonial_row("This course gave me the confidence to lead AI initiatives at my company. Complex topics explained simply.", "David Chen", "Product Manager at TechCorp", "#06B6D4", "#CFFAFE"),
        dual_cta_row("Starts April 1st", "Enroll Free", "View Curriculum", "#06B6D4", "#6B7280", "#CFFAFE"),
        footer_dark("LearnHub", "500 Education Blvd, Boston, MA 02101", "#", "#1E3A5F"),
    ],
    "edu-newsletter": lambda: [
        hero_minimal("LearnHub Weekly", "New courses, learning tips, and student success stories.", "#334155"),
        text_image_row("Course Spotlight: Data Visualization", "Turn raw data into compelling stories. Learn Tableau, D3.js, and visual storytelling in this hands-on course.", IMG["data_viz"], "#FFFFFF"),
        stats_row("94%", "Completion Rate", "4.8★", "Avg Rating", "12hr", "Total Content", "#8B5CF6", "#EDE9FE"),
        cta_row("Learning Streak Challenge", "Complete 1 lesson per day for 30 days. Win a Pro subscription.", "Start Your Streak", "#8B5CF6"),
        footer_dark("LearnHub", "500 Education Blvd, Boston, MA 02101", "#", "#334155"),
    ],
    "event-conference": lambda: [
        hero_dark("TechForward 2026", "The future of technology. April 15–17, San Francisco.", "Register Now", "#020617", "#06B6D4"),
        image_row(IMG["conference"], "Tech conference"),
        stats_row("80+", "Speakers", "3", "Days", "5K+", "Attendees", "#06B6D4", "#0F172A"),
        checklist_row("Conference Highlights", ["Keynote by the CEO of OpenAI", "50+ breakout sessions on AI, Cloud, and Security", "Startup pitch competition with $100K prize", "Networking mixer with industry leaders"], "#06B6D4", "#FFFFFF"),
        dual_cta_row("Early Bird Pricing Ends March 31", "Register — $299", "View Agenda", "#06B6D4", "#475569"),
        footer_dark("TechForward", "1 Innovation Way, San Francisco, CA 94105", "#", "#020617"),
    ],
    "event-webinar": lambda: [
        hero_minimal("Free Webinar: Building with AI", "Live 60-minute session. Thursday, March 27th at 2pm ET.", "#581C87"),
        text_image_row("Your Host: Dr. Sarah Lin", "AI researcher and author of 'Practical Machine Learning'. Sarah has helped 200+ companies implement AI solutions.", IMG["speaker"], "#FFFFFF"),
        checklist_row("What You'll Learn", ["How to identify AI opportunities in your business", "Common pitfalls and how to avoid them", "Tools and frameworks to get started today", "Live Q&A with Dr. Lin"], "#D946EF", "#FDF4FF"),
        cta_row("Save Your Spot", "Free to attend. Recording sent to all registrants.", "Register for Free", "#D946EF"),
        footer_dark("TechForward", "1 Innovation Way, San Francisco, CA 94105", "#", "#581C87"),
    ],
    "event-followup": lambda: [
        hero_minimal("Thanks for Attending!", "We hope you enjoyed TechForward 2026. Here's everything you need.", "#292524"),
        checklist_row("Event Resources", ["Watch all session recordings on our YouTube channel", "Download speaker slides from the resource hub", "Connect with attendees on our community Slack", "Share your feedback in our 2-minute survey"], "#10B981", "#D1FAE5"),
        testimonial_row("Best tech conference I've attended in years. The quality of speakers and the networking opportunities were incredible.", "Alex Rivera", "CTO at ScaleUp", "#10B981", "#FFFFFF"),
        dual_cta_row("Stay Connected", "Watch Recordings", "Join Community", "#10B981", "#6B7280", "#D1FAE5"),
        footer_dark("TechForward", "1 Innovation Way, San Francisco, CA 94105", "#", "#292524"),
    ],
    "realestate-welcome": lambda: [
        hero_dark("Find Your Dream Home", "Personalized property search powered by local expertise.", "Browse Listings", "#1C1917", "#D97706"),
        image_row(IMG["luxury_home"], "Luxury home"),
        stats_row("500+", "Active Listings", "15+", "Years Experience", "98%", "Client Satisfaction", "#D97706", "#FFFBEB"),
        text_image_row("Meet Your Agent", "Hi! I'm Jennifer Torres, your dedicated real estate agent. I'll help you navigate every step — from search to closing.", IMG["pro_woman"], "#FFFFFF"),
        cta_row("Let's Start Your Search", "Tell me what you're looking for and I'll send personalized recommendations.", "Schedule a Consultation", "#D97706", "#FFFBEB"),
        footer_dark("Torres Realty", "888 Property Blvd, Miami, FL 33101", "#", "#1C1917"),
    ],
    "realestate-listing": lambda: [
        hero_image("New Listing: 4BR Modern Farmhouse", "2,800 sqft · 4 Bed · 3 Bath · 0.5 Acre · $625,000", "Schedule a Viewing", IMG["house_interior"], "#0F172A", "#B45309"),
        stats_row("$625K", "List Price", "2,800", "Sq Ft", "2024", "Year Built", "#B45309", "#FFFBEB"),
        checklist_row("Property Highlights", ["Open-concept kitchen with quartz countertops", "Primary suite with walk-in closet and spa bathroom", "Finished basement with home theater", "Covered patio with outdoor kitchen"], "#B45309", "#FFFFFF"),
        dual_cta_row("Interested?", "Schedule Viewing", "Request Details", "#B45309", "#78716C", "#FFFBEB"),
        footer_dark("Torres Realty", "888 Property Blvd, Miami, FL 33101", "#", "#0F172A"),
    ],
    "realestate-newsletter": lambda: [
        hero_minimal("March Market Update", "Local real estate trends, new listings, and tips for buyers and sellers.", "#B45309"),
        stats_row("+5.2%", "Home Prices YoY", "22", "Avg Days on Market", "340", "Homes Sold", "#B45309", "#FEF3C7"),
        text_image_row("Buyer's Tip: Pre-Approval Power", "In today's market, pre-approval before house hunting gives you a significant advantage. Sellers take pre-approved buyers more seriously.", IMG["house_sale"], "#FFFFFF"),
        cta_row("Thinking About Selling?", "Get a free home valuation in under 24 hours.", "Get Free Valuation", "#B45309"),
        footer_dark("Torres Realty", "888 Property Blvd, Miami, FL 33101", "#", "#44403C"),
    ],
    "agency-welcome": lambda: [
        hero_dark("We Build Brands That Matter", "Strategy. Design. Technology. Results.", "See Our Work", "#0C0A09", "#E11D48"),
        image_row(IMG["creative_workspace"], "Creative workspace"),
        stats_row("200+", "Projects Delivered", "50+", "Happy Clients", "12", "Awards Won", "#E11D48", "#FFF1F2"),
        testimonial_row("Crimson Creative didn't just redesign our brand — they transformed how our customers see us. Revenue is up 40% since launch.", "Marcus Lee", "CEO at Velocity Labs", "#E11D48", "#FFFFFF"),
        cta_row("Let's Create Something Amazing", "Free 30-minute strategy session for new clients.", "Book Your Session", "#E11D48"),
        footer_dark("Crimson Creative", "77 Design District, Brooklyn, NY 11201", "#", "#0C0A09"),
    ],
    "agency-case-study": lambda: [
        hero_dark("Case Study: Velocity Labs", "How we helped a B2B startup increase conversions by 340%.", "Read the Full Story", "#4C0519", "#FB7185"),
        stats_row("+340%", "Conversions", "+180%", "Traffic", "6 wks", "Timeline", "#FB7185", "#FFE4E6"),
        text_image_row("The Challenge", "Velocity Labs had a great product but their website wasn't converting. Visitors bounced within seconds. They needed a complete brand overhaul.", IMG["website_mockup"], "#FFFFFF"),
        cta_row("Want Results Like This?", "Every project starts with understanding your goals.", "Let's Talk", "#FB7185"),
        footer_dark("Crimson Creative", "77 Design District, Brooklyn, NY 11201", "#", "#4C0519"),
    ],
    "agency-launch": lambda: [
        hero_image("Now Offering: AI Brand Strategy", "Data-driven brand positioning powered by artificial intelligence.", "Learn More", IMG["ai_tech"], "#0C0A09", "#06B6D4"),
        checklist_row("What's Included", ["AI-powered competitive analysis report", "Brand positioning matrix with data insights", "Visual identity recommendations", "90-day content strategy roadmap"], "#06B6D4", "#FFFFFF"),
        coupon_row("Launch Special", "AIBRAND", "First 10 clients get 25% off", "Claim Your Spot", "#06B6D4", "#042F2E"),
        cta_row("Limited Availability", "We take on only 5 new AI strategy clients per month.", "Apply Now", "#06B6D4"),
        footer_dark("Crimson Creative", "77 Design District, Brooklyn, NY 11201", "#", "#0C0A09"),
    ],
    "generic-sale": lambda: [
        hero_dark("MASSIVE SALE — UP TO 60% OFF", "Our biggest sale of the year. Everything must go.", "Shop the Sale", "#111827", "#DC2626"),
        products_3col("Best Seller #1", "$29 <s>$72</s>", "Best Seller #2", "$39 <s>$98</s>", "Best Seller #3", "$19 <s>$48</s>", "#DC2626"),
        urgency_row("Hurry — Sale Ends Sunday!", "Once it's gone, it's gone. No rainchecks, no extensions.", "Shop All Deals", "#DC2626"),
        coupon_row("Stack & Save", "EXTRA15", "Extra 15% off sale prices", "Apply Code", "#DC2626", "#FEF2F2"),
        cta_row("Free Shipping on Everything", "No minimum order. Delivery in 3-5 business days.", "Start Shopping →", "#DC2626"),
        footer_dark("The Store", "123 Commerce St, Anytown, USA", "#", "#111827"),
    ],
    "generic-newsletter": lambda: [
        hero_minimal("The Weekly Brief", "News, insights, and tips delivered every Friday.", "#475569"),
        text_image_row("The Future of Remote Work", "A new study reveals that hybrid work isn't just preferred — it's more productive. Here's what the data says and what it means for your team.", IMG["remote_work"]),
        checklist_row("Quick Links", ["Read: 5 productivity hacks for remote teams", "Watch: Interview with our CEO on industry trends", "Download: Free template pack for project planning", "Join: Our community Slack with 5,000+ members"], "#3B82F6", "#F3F4F6"),
        cta_row("Share the Brief", "Know someone who'd enjoy this newsletter?", "Forward to a Friend", "#3B82F6"),
        footer_social("The Weekly Brief", "Twitter &nbsp;|&nbsp; LinkedIn &nbsp;|&nbsp; Newsletter Archive", "#", "#475569"),
    ],
    "generic-thankyou": lambda: [
        hero_minimal("Thank You!", "We truly appreciate your support. Here's what happens next.", "#16A34A"),
        checklist_row("Next Steps", ["Check your inbox for a confirmation email", "You'll receive updates within 24 hours", "Bookmark your dashboard for easy access", "Reach out anytime — we're here to help"], "#16A34A", "#F0FDF4"),
        testimonial_row("The onboarding experience was seamless. I was up and running in minutes. Highly recommend!", "Jamie Park", "Happy Customer", "#16A34A", "#FFFFFF"),
        cta_row("Need Help?", "Our support team is available 24/7 via chat, email, or phone.", "Contact Support", "#16A34A"),
        footer_dark("Your Company", "456 Business Ave, Anytown, USA", "#", "#1C1917"),
    ],
}


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates", "library")
    os.makedirs(output_dir, exist_ok=True)

    session = get_session()
    cards = []

    print(f"Building {len(TEMPLATES)} unique templates...")

    for slug, builder in TEMPLATES.items():
        print(f"  {slug}...", end=" ")
        components = builder()

        # Update DB
        existing = session.query(TemplateLibraryItem).filter_by(slug=slug).first()
        if existing:
            existing.components = components
        else:
            print("not in DB, skipping")
            continue

        # Render HTML
        name = existing.name
        template = {"templateName": name, "templateSubject": name, "components": components}
        try:
            html = build_html(template)
            size_kb = f"{len(html) / 1024:.1f}"

            # Save standalone file
            wrapped = f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=600"><title>{name}</title><style>html,body{{margin:0;padding:0;background:#f4f4f4}}.v{{width:600px;margin:0 auto}}</style></head><body><div class="v">{html}</div></body></html>'
            with open(os.path.join(output_dir, f"{slug}.html"), "w") as f:
                f.write(wrapped)

            escaped = html.replace("&", "&amp;").replace('"', "&quot;")
            cards.append((slug, name, existing.description, existing.industry, existing.purpose, existing.tone, size_kb, escaped))
            print(f"{len(components)} rows, {size_kb} KB")
        except Exception as e:
            print(f"ERROR: {e}")

    session.commit()
    session.close()

    # Build index.html
    print("\nBuilding index.html...")
    idx = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Template Library</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,sans-serif;background:#0a0f1a;color:#e2e8f0;padding:40px 20px}h1{text-align:center;font-size:28px;margin-bottom:8px;color:#fff}.sub{text-align:center;color:#64748b;margin-bottom:40px;font-size:14px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:24px;max-width:1400px;margin:0 auto}.card{background:#111827;border:1px solid #1e293b;border-radius:16px;overflow:hidden;transition:all .3s}.card:hover{border-color:#0891b2;transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,0,0,.3)}.pw{background:#e5e7eb;overflow:hidden;height:400px;position:relative}.pf{width:600px;height:1100px;border:none;pointer-events:none;background:#fff;transform:scale(.55);transform-origin:top left}.ob{display:none;position:absolute;bottom:12px;right:12px;padding:6px 14px;background:rgba(6,182,212,.9);color:#fff;border:none;border-radius:8px;font-size:11px;font-weight:600;cursor:pointer;text-decoration:none}.card:hover .ob{display:block}.info{padding:14px 16px}.info h3{font-size:13px;font-weight:600;color:#f1f5f9;margin-bottom:4px}.desc{font-size:11px;color:#64748b;line-height:1.5;margin-bottom:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.meta{display:flex;gap:6px;flex-wrap:wrap}.t{font-size:9px;padding:3px 8px;border-radius:6px;text-transform:uppercase;letter-spacing:.5px;font-weight:600}.ti{background:#164e63;color:#67e8f9}.tp{background:#1e3a5f;color:#7dd3fc}.tt{background:#312e81;color:#a5b4fc}.ts{background:#1c1917;color:#78716c}</style></head><body><h1>Template Library</h1><p class="sub">30 unique email templates — real Unsplash images, distinct palettes, industry-specific content</p><div class="grid">'

    for slug, name, desc, industry, purpose, tone, size_kb, escaped in cards:
        idx += f'<div class="card"><div class="pw"><iframe srcdoc="{escaped}" class="pf" loading="lazy"></iframe><a href="{slug}.html" target="_blank" class="ob">Open Full View</a></div><div class="info"><h3>{name}</h3><p class="desc">{desc[:120]}</p><div class="meta"><span class="t ti">{industry}</span><span class="t tp">{purpose}</span><span class="t tt">{tone}</span><span class="t ts">{size_kb} KB</span></div></div></div>'

    idx += '</div></body></html>'
    with open(os.path.join(output_dir, "index.html"), "w") as f:
        f.write(idx)

    print(f"Done! {len(cards)} templates, {len(idx)//1024} KB index.html")


if __name__ == "__main__":
    main()
