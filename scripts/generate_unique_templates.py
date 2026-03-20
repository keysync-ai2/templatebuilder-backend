"""Generate 30 unique email templates with distinct styles per industry/purpose.

Each template gets a unique color palette, layout structure, and realistic content.
"""

import json
import os
import sys
import uuid
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.builder import inject_preset, _remap_ids
from engine.presets import local_preset_loader
from config.database import get_session
from models.template_library import TemplateLibraryItem

# ─── Color palettes per industry ───
PALETTES = {
    "saas": {
        "primary": "#0F172A", "secondary": "#1E40AF", "accent": "#3B82F6",
        "text": "#F8FAFC", "muted": "#94A3B8", "bg": "#F1F5F9", "cta": "#2563EB", "cta_text": "#FFFFFF",
    },
    "ecommerce": {
        "primary": "#18181B", "secondary": "#DC2626", "accent": "#EF4444",
        "text": "#FFFFFF", "muted": "#A1A1AA", "bg": "#FEF2F2", "cta": "#DC2626", "cta_text": "#FFFFFF",
    },
    "health": {
        "primary": "#064E3B", "secondary": "#059669", "accent": "#10B981",
        "text": "#FFFFFF", "muted": "#D1FAE5", "bg": "#ECFDF5", "cta": "#059669", "cta_text": "#FFFFFF",
    },
    "food": {
        "primary": "#7C2D12", "secondary": "#EA580C", "accent": "#FB923C",
        "text": "#FFFFFF", "muted": "#FED7AA", "bg": "#FFF7ED", "cta": "#EA580C", "cta_text": "#FFFFFF",
    },
    "education": {
        "primary": "#1E1B4B", "secondary": "#4338CA", "accent": "#6366F1",
        "text": "#FFFFFF", "muted": "#C7D2FE", "bg": "#EEF2FF", "cta": "#4338CA", "cta_text": "#FFFFFF",
    },
    "events": {
        "primary": "#581C87", "secondary": "#9333EA", "accent": "#A855F7",
        "text": "#FFFFFF", "muted": "#E9D5FF", "bg": "#FAF5FF", "cta": "#9333EA", "cta_text": "#FFFFFF",
    },
    "real_estate": {
        "primary": "#1C1917", "secondary": "#B45309", "accent": "#F59E0B",
        "text": "#FFFFFF", "muted": "#D6D3D1", "bg": "#FFFBEB", "cta": "#B45309", "cta_text": "#FFFFFF",
    },
    "agency": {
        "primary": "#0C0A09", "secondary": "#E11D48", "accent": "#FB7185",
        "text": "#FFFFFF", "muted": "#A8A29E", "bg": "#FFF1F2", "cta": "#E11D48", "cta_text": "#FFFFFF",
    },
    "other": {
        "primary": "#111827", "secondary": "#2563EB", "accent": "#60A5FA",
        "text": "#FFFFFF", "muted": "#9CA3AF", "bg": "#F3F4F6", "cta": "#2563EB", "cta_text": "#FFFFFF",
    },
}

# ─── Template content specs ───
SPECS = {
    "saas-welcome": {
        "hero": "hero-bold", "hero_vars": {"headline": "Welcome to CloudSync", "subtitle": "Your team's productivity hub. Get started in under 2 minutes.", "buttonText": "Start Your Free Trial", "buttonUrl": "#"},
        "middle": [
            ("content-stats", {"stat1Value": "99.9%", "stat1Label": "Uptime", "stat2Value": "50K+", "stat2Label": "Teams", "stat3Value": "4.9/5", "stat3Label": "Rating"}),
            ("content-checklist", {"heading": "What You Get", "item1": "Unlimited cloud storage for your team", "item2": "Real-time collaboration on documents", "item3": "Advanced security & encryption", "item4": "24/7 priority customer support"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Ready to transform your workflow?", "supportText": "Join 50,000+ teams already using CloudSync.", "buttonText": "Get Started Free"},
    },
    "saas-product-launch": {
        "hero": "hero-image", "hero_vars": {"headline": "Introducing Smart Analytics", "subtitle": "AI-powered insights that predict what's next for your business.", "buttonText": "See It In Action", "heroImage": "https://placehold.co/600x250/1E40AF/FFFFFF?text=Smart+Analytics"},
        "middle": [
            ("product-featured", {"productName": "Smart Analytics Pro", "description": "Get real-time dashboards, predictive forecasting, and automated reports delivered to your inbox every morning.", "price": "Starting at $29/mo", "buttonText": "Start Free Trial", "productImage": "https://placehold.co/280x280/EEF2FF/4338CA?text=Dashboard"}),
        ],
        "cta": "cta-dual", "cta_vars": {"heading": "Choose Your Plan", "primaryText": "Start Free Trial", "secondaryText": "Book a Demo"},
    },
    "saas-newsletter": {
        "hero": "hero-minimal", "hero_vars": {"headline": "CloudSync Monthly Update", "bodyText": "Product updates, tips, and stories from our community — March 2026."},
        "middle": [
            ("content-text-image", {"heading": "New: AI Writing Assistant", "bodyText": "Draft emails, documents, and reports in seconds with our new AI-powered writing assistant. Now available for all Pro plans.", "image": "https://placehold.co/280x200/F1F5F9/64748B?text=AI+Writing"}),
            ("content-stats", {"stat1Value": "3x", "stat1Label": "Faster Drafts", "stat2Value": "85%", "stat2Label": "Time Saved", "stat3Value": "12K", "stat3Label": "Users Love It"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Try AI Writing Today", "supportText": "Available now for Pro and Enterprise plans.", "buttonText": "Try It Now"},
    },
    "saas-trial-ending": {
        "hero": "hero-bold", "hero_vars": {"headline": "Your Trial Ends Tomorrow", "subtitle": "Don't lose access to your workspace and 14 days of work.", "buttonText": "Upgrade Now"},
        "middle": [
            ("countdown-urgency", {"heading": "Less Than 24 Hours Left", "bodyText": "After your trial ends, your account will be downgraded to the free plan. Upgrade now to keep all your data and features.", "buttonText": "Upgrade to Pro — $19/mo"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Need more time?", "supportText": "Reply to this email and we'll extend your trial by 7 days.", "buttonText": "Contact Support"},
    },
    "ecom-welcome": {
        "hero": "hero-bold", "hero_vars": {"headline": "Welcome to UrbanThread", "subtitle": "Fashion that fits your life. Here's 15% off your first order.", "buttonText": "Shop Now"},
        "middle": [
            ("coupon-banner", {"heading": "Your Welcome Gift", "couponCode": "WELCOME15", "expiryText": "Valid for 30 days", "buttonText": "Shop the Collection"}),
            ("product-2col", {"product1Name": "Summer Linen Shirt", "product1Price": "$49.99", "product2Name": "Classic Chinos", "product2Price": "$59.99"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Free Shipping on Orders $75+", "supportText": "Easy returns within 30 days. No questions asked.", "buttonText": "Start Shopping"},
    },
    "ecom-sale": {
        "hero": "hero-bold", "hero_vars": {"headline": "FLASH SALE — 50% OFF", "subtitle": "24 hours only. Don't miss our biggest sale of the year.", "buttonText": "Shop the Sale"},
        "middle": [
            ("countdown-urgency", {"heading": "Ends at Midnight!", "bodyText": "Every item in the store is 50% off. No exclusions, no minimum order.", "buttonText": "Shop All Deals"}),
            ("product-3col", {"product1Name": "Leather Jacket", "product1Price": "$89 $178", "product2Name": "Silk Dress", "product2Price": "$64 $128", "product3Name": "Wool Coat", "product3Price": "$120 $240"}),
            ("coupon-banner", {"heading": "Extra 10% Off", "couponCode": "FLASH10", "expiryText": "Stack with sale prices!", "buttonText": "Apply at Checkout"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Don't Wait — Sale Ends Tonight", "supportText": "Free express shipping on all sale orders.", "buttonText": "Shop Now →"},
    },
    "ecom-product-launch": {
        "hero": "hero-image", "hero_vars": {"headline": "New Arrivals Just Dropped", "subtitle": "Fresh styles for the season. Be the first to shop.", "buttonText": "See What's New", "heroImage": "https://placehold.co/600x250/18181B/FFFFFF?text=New+Collection"},
        "middle": [
            ("product-3col", {"product1Name": "Oversized Blazer", "product1Price": "$129", "product2Name": "Cropped Tee", "product2Price": "$34", "product3Name": "Wide-Leg Pants", "product3Price": "$79"}),
        ],
        "cta": "cta-dual", "cta_vars": {"heading": "Complete Your Look", "primaryText": "Shop Women", "secondaryText": "Shop Men"},
    },
    "ecom-abandoned-cart": {
        "hero": "hero-minimal", "hero_vars": {"headline": "You left something behind", "bodyText": "Your cart is waiting for you. Complete your purchase before items sell out."},
        "middle": [
            ("product-featured", {"productName": "Classic Leather Bag", "description": "Hand-crafted Italian leather. Only 3 left in stock.", "price": "$189.00", "buttonText": "Complete Purchase", "productImage": "https://placehold.co/280x280/FEF2F2/DC2626?text=Leather+Bag"}),
            ("coupon-banner", {"heading": "Need a nudge?", "couponCode": "COMEBACK10", "expiryText": "10% off — expires in 48 hours", "buttonText": "Return to Cart"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Questions? We're here to help", "supportText": "Free shipping. Easy returns. Secure checkout.", "buttonText": "Complete Your Order"},
    },
    "ecom-newsletter": {
        "hero": "hero-minimal", "hero_vars": {"headline": "This Week at UrbanThread", "bodyText": "Trending picks, style guides, and exclusive deals — curated just for you."},
        "middle": [
            ("content-text-image", {"heading": "Style Guide: Spring Layers", "bodyText": "Master the art of layering this spring with our curated guide. Mix textures, play with proportions, and stay warm while looking effortlessly cool.", "image": "https://placehold.co/280x200/FEF2F2/DC2626?text=Spring+Style"}),
            ("product-2col", {"product1Name": "Editor's Pick: Linen Blazer", "product1Price": "$98", "product2Name": "Trending: Cargo Pants", "product2Price": "$72"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Members Get Early Access", "supportText": "Join our VIP list for 24-hour early access to new drops.", "buttonText": "Join VIP"},
    },
    "health-welcome": {
        "hero": "hero-bold", "hero_vars": {"headline": "Welcome to FitPulse", "subtitle": "Your journey to a healthier you starts now. Let's make it count.", "buttonText": "Start Your First Workout"},
        "middle": [
            ("content-stats", {"stat1Value": "500+", "stat1Label": "Workouts", "stat2Value": "50+", "stat2Label": "Programs", "stat3Value": "1M+", "stat3Label": "Members"}),
            ("content-checklist", {"heading": "Your FitPulse Membership", "item1": "Personalized workout plans based on your goals", "item2": "Nutrition tracking with meal suggestions", "item3": "Progress photos and body measurements", "item4": "Live classes with certified trainers"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Start with a 7-Day Challenge", "supportText": "Quick, effective workouts designed for beginners.", "buttonText": "Begin Challenge"},
    },
    "health-promo": {
        "hero": "hero-bold", "hero_vars": {"headline": "New Year, New You — 40% Off", "subtitle": "Premium annual membership at the lowest price ever.", "buttonText": "Claim Your Spot"},
        "middle": [
            ("countdown-urgency", {"heading": "Offer Ends January 31st", "bodyText": "Lock in $9.99/month (normally $16.99) for your entire first year. Cancel anytime.", "buttonText": "Get 40% Off Now"}),
            ("content-testimonial", {"quote": "FitPulse changed my life. I've lost 30 lbs and gained confidence I never knew I had. The trainers are incredible.", "authorName": "Sarah M.", "authorRole": "Member since 2024"}),
        ],
        "cta": "cta-dual", "cta_vars": {"heading": "Choose Your Plan", "primaryText": "Annual — $9.99/mo", "secondaryText": "Monthly — $16.99/mo"},
    },
    "health-newsletter": {
        "hero": "hero-minimal", "hero_vars": {"headline": "Your Weekly Wellness Digest", "bodyText": "Workouts, nutrition tips, and motivation — delivered every Monday."},
        "middle": [
            ("content-text-image", {"heading": "Workout of the Week: HIIT Burn", "bodyText": "Torch calories in just 20 minutes with this high-intensity interval training session. No equipment needed — do it anywhere.", "image": "https://placehold.co/280x200/ECFDF5/059669?text=HIIT+Workout"}),
            ("content-checklist", {"heading": "5 Tips for Better Sleep", "item1": "Set a consistent bedtime — even on weekends", "item2": "Avoid screens 30 minutes before bed", "item3": "Keep your room cool (65-68°F)", "item4": "Try a 10-minute evening stretch routine"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "This Week's Challenge", "supportText": "Drink 8 glasses of water every day for 7 days.", "buttonText": "Accept the Challenge"},
    },
    "food-welcome": {
        "hero": "hero-bold", "hero_vars": {"headline": "Welcome to Savory Bites", "subtitle": "Where every meal is an experience. Your table is ready.", "buttonText": "View Our Menu"},
        "middle": [
            ("content-text-image", {"heading": "Chef's Table Experience", "bodyText": "Join Chef Marco for an intimate 7-course tasting menu every Saturday evening. Seasonal ingredients, inspired pairings, unforgettable flavors.", "image": "https://placehold.co/280x200/FFF7ED/EA580C?text=Chef's+Table"}),
            ("coupon-banner", {"heading": "First Visit Special", "couponCode": "WELCOME20", "expiryText": "20% off your first order", "buttonText": "Order Now"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Reserve Your Table", "supportText": "Open Tuesday–Sunday, 5pm–11pm. Walk-ins welcome.", "buttonText": "Make a Reservation"},
    },
    "food-promo": {
        "hero": "hero-bold", "hero_vars": {"headline": "Weekend Special: Family Feast", "subtitle": "Feed the whole family for $49. Order by Friday for Saturday delivery.", "buttonText": "Order the Feast"},
        "middle": [
            ("product-2col", {"product1Name": "BBQ Platter for 4", "product1Price": "$49", "product2Name": "Pasta Family Pack", "product2Price": "$39"}),
            ("coupon-banner", {"heading": "Free Dessert with Every Order", "couponCode": "SWEETDEAL", "expiryText": "This weekend only", "buttonText": "Add to Order"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Free Delivery on $30+", "supportText": "Hot and fresh to your door in 45 minutes or less.", "buttonText": "Order Now"},
    },
    "food-event": {
        "hero": "hero-image", "hero_vars": {"headline": "Wine & Dine Night", "subtitle": "An evening of curated wines paired with Chef Marco's finest dishes. March 28th.", "buttonText": "Reserve Your Spot", "heroImage": "https://placehold.co/600x250/7C2D12/FFFFFF?text=Wine+%26+Dine"},
        "middle": [
            ("content-checklist", {"heading": "What to Expect", "item1": "5-course tasting menu by Chef Marco", "item2": "Wine pairings selected by our sommelier", "item3": "Live jazz performance", "item4": "Complimentary welcome cocktail"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Limited to 40 Guests", "supportText": "Saturday, March 28th — 7:00 PM. Dress code: Smart casual.", "buttonText": "RSVP Now — $95/person"},
    },
    "edu-welcome": {
        "hero": "hero-bold", "hero_vars": {"headline": "Welcome to LearnHub", "subtitle": "Thousands of courses. World-class instructors. Learn at your own pace.", "buttonText": "Explore Courses"},
        "middle": [
            ("content-stats", {"stat1Value": "10K+", "stat1Label": "Courses", "stat2Value": "500+", "stat2Label": "Instructors", "stat3Value": "2M+", "stat3Label": "Students"}),
            ("content-checklist", {"heading": "Getting Started", "item1": "Browse courses by topic or skill level", "item2": "Enroll in your first course — many are free", "item3": "Track your progress with personalized dashboards", "item4": "Earn certificates to showcase your skills"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Start Learning Today", "supportText": "Over 2,000 free courses to get you started.", "buttonText": "Browse Free Courses"},
    },
    "edu-launch": {
        "hero": "hero-image", "hero_vars": {"headline": "New Course: AI for Everyone", "subtitle": "No coding required. Understand AI, machine learning, and the future of work.", "buttonText": "Enroll Now — Free", "heroImage": "https://placehold.co/600x250/1E1B4B/FFFFFF?text=AI+for+Everyone"},
        "middle": [
            ("content-text-image", {"heading": "What You'll Learn", "bodyText": "This 6-week course covers the fundamentals of artificial intelligence, real-world applications, and how AI is transforming every industry. Perfect for beginners and professionals alike.", "image": "https://placehold.co/280x200/EEF2FF/4338CA?text=Course+Preview"}),
            ("content-testimonial", {"quote": "This course gave me the confidence to lead AI initiatives at my company. The instructor explains complex topics in a way anyone can understand.", "authorName": "David Chen", "authorRole": "Product Manager at TechCorp"}),
        ],
        "cta": "cta-dual", "cta_vars": {"heading": "Starts April 1st", "primaryText": "Enroll Free", "secondaryText": "View Curriculum"},
    },
    "edu-newsletter": {
        "hero": "hero-minimal", "hero_vars": {"headline": "LearnHub Weekly", "bodyText": "New courses, learning tips, and student success stories — every Thursday."},
        "middle": [
            ("content-text-image", {"heading": "Course Spotlight: Data Visualization", "bodyText": "Turn raw data into compelling stories. Learn Tableau, D3.js, and the art of visual storytelling in this hands-on course.", "image": "https://placehold.co/280x200/EEF2FF/4338CA?text=Data+Viz"}),
            ("content-stats", {"stat1Value": "94%", "stat1Label": "Completion Rate", "stat2Value": "4.8★", "stat2Label": "Avg Rating", "stat3Value": "12hr", "stat3Label": "Total Content"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Learning Streak Challenge", "supportText": "Complete 1 lesson per day for 30 days. Win a Pro subscription.", "buttonText": "Start Your Streak"},
    },
    "event-conference": {
        "hero": "hero-bold", "hero_vars": {"headline": "TechForward 2026", "subtitle": "The future of technology. April 15–17, San Francisco.", "buttonText": "Register Now"},
        "middle": [
            ("content-stats", {"stat1Value": "80+", "stat1Label": "Speakers", "stat2Value": "3", "stat2Label": "Days", "stat3Value": "5K+", "stat3Label": "Attendees"}),
            ("content-checklist", {"heading": "Conference Highlights", "item1": "Keynote by the CEO of OpenAI", "item2": "50+ breakout sessions on AI, Cloud, and Security", "item3": "Startup pitch competition with $100K prize", "item4": "Networking mixer with industry leaders"}),
        ],
        "cta": "cta-dual", "cta_vars": {"heading": "Early Bird Pricing Ends March 31", "primaryText": "Register — $299", "secondaryText": "View Agenda"},
    },
    "event-webinar": {
        "hero": "hero-minimal", "hero_vars": {"headline": "Free Webinar: Building with AI", "bodyText": "Join us for a live 60-minute session on practical AI implementation. Thursday, March 27th at 2pm ET."},
        "middle": [
            ("content-text-image", {"heading": "Your Host: Dr. Sarah Lin", "bodyText": "AI researcher and author of 'Practical Machine Learning'. Sarah has helped 200+ companies implement AI solutions that drive real business results.", "image": "https://placehold.co/280x200/FAF5FF/9333EA?text=Dr.+Sarah+Lin"}),
            ("content-checklist", {"heading": "What You'll Learn", "item1": "How to identify AI opportunities in your business", "item2": "Common pitfalls and how to avoid them", "item3": "Tools and frameworks to get started today", "item4": "Live Q&A with Dr. Lin"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Save Your Spot", "supportText": "Free to attend. Recording sent to all registrants.", "buttonText": "Register for Free"},
    },
    "event-followup": {
        "hero": "hero-minimal", "hero_vars": {"headline": "Thanks for Attending!", "bodyText": "We hope you enjoyed TechForward 2026. Here's everything you need from the event."},
        "middle": [
            ("content-checklist", {"heading": "Event Resources", "item1": "Watch all session recordings on our YouTube channel", "item2": "Download speaker slides from the resource hub", "item3": "Connect with attendees on our community Slack", "item4": "Share your feedback in our 2-minute survey"}),
            ("content-testimonial", {"quote": "Best tech conference I've attended in years. The quality of speakers and the networking opportunities were incredible.", "authorName": "Alex Rivera", "authorRole": "CTO at ScaleUp"}),
        ],
        "cta": "cta-dual", "cta_vars": {"heading": "Stay Connected", "primaryText": "Watch Recordings", "secondaryText": "Join Community"},
    },
    "realestate-welcome": {
        "hero": "hero-bold", "hero_vars": {"headline": "Find Your Dream Home", "subtitle": "Personalized property search powered by local expertise. Let's get started.", "buttonText": "Browse Listings"},
        "middle": [
            ("content-stats", {"stat1Value": "500+", "stat1Label": "Active Listings", "stat2Value": "15+", "stat2Label": "Years Experience", "stat3Value": "98%", "stat3Label": "Client Satisfaction"}),
            ("content-text-image", {"heading": "Meet Your Agent", "bodyText": "Hi! I'm Jennifer Torres, your dedicated real estate agent. I'll help you navigate every step of the home buying process — from search to closing.", "image": "https://placehold.co/280x200/FFFBEB/B45309?text=Jennifer+Torres"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Let's Start Your Search", "supportText": "Tell me what you're looking for and I'll send personalized recommendations.", "buttonText": "Schedule a Consultation"},
    },
    "realestate-listing": {
        "hero": "hero-image", "hero_vars": {"headline": "New Listing: 4BR Modern Farmhouse", "subtitle": "2,800 sqft · 4 Bed · 3 Bath · 0.5 Acre · $625,000", "buttonText": "Schedule a Viewing", "heroImage": "https://placehold.co/600x250/1C1917/FFFFFF?text=Modern+Farmhouse"},
        "middle": [
            ("content-checklist", {"heading": "Property Highlights", "item1": "Open-concept kitchen with quartz countertops", "item2": "Primary suite with walk-in closet and spa bathroom", "item3": "Finished basement with home theater", "item4": "Covered patio with outdoor kitchen"}),
            ("content-stats", {"stat1Value": "$625K", "stat1Label": "List Price", "stat2Value": "2,800", "stat2Label": "Sq Ft", "stat3Value": "2024", "stat3Label": "Year Built"}),
        ],
        "cta": "cta-dual", "cta_vars": {"heading": "Interested?", "primaryText": "Schedule Viewing", "secondaryText": "Request Details"},
    },
    "realestate-newsletter": {
        "hero": "hero-minimal", "hero_vars": {"headline": "March Market Update", "bodyText": "Local real estate trends, new listings, and tips for buyers and sellers."},
        "middle": [
            ("content-stats", {"stat1Value": "+5.2%", "stat1Label": "Home Prices YoY", "stat2Value": "22", "stat2Label": "Avg Days on Market", "stat3Value": "340", "stat3Label": "Homes Sold This Month"}),
            ("content-text-image", {"heading": "Buyer's Tip: Pre-Approval Power", "bodyText": "In today's competitive market, getting pre-approved before house hunting gives you a significant advantage. Sellers take pre-approved buyers more seriously.", "image": "https://placehold.co/280x200/FFFBEB/B45309?text=Market+Trends"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Thinking About Selling?", "supportText": "Get a free home valuation in under 24 hours.", "buttonText": "Get Free Valuation"},
    },
    "agency-welcome": {
        "hero": "hero-bold", "hero_vars": {"headline": "We Build Brands That Matter", "subtitle": "Strategy. Design. Technology. Results. Welcome to Crimson Creative.", "buttonText": "See Our Work"},
        "middle": [
            ("content-stats", {"stat1Value": "200+", "stat1Label": "Projects Delivered", "stat2Value": "50+", "stat2Label": "Happy Clients", "stat3Value": "12", "stat3Label": "Awards Won"}),
            ("content-testimonial", {"quote": "Crimson Creative didn't just redesign our brand — they transformed how our customers see us. Revenue is up 40% since launch.", "authorName": "Marcus Lee", "authorRole": "CEO at Velocity Labs"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Let's Create Something Amazing", "supportText": "Free 30-minute strategy session for new clients.", "buttonText": "Book Your Session"},
    },
    "agency-case-study": {
        "hero": "hero-bold", "hero_vars": {"headline": "Case Study: Velocity Labs", "subtitle": "How we helped a B2B startup increase conversions by 340%.", "buttonText": "Read the Full Story"},
        "middle": [
            ("content-stats", {"stat1Value": "+340%", "stat1Label": "Conversions", "stat2Value": "+180%", "stat2Label": "Traffic", "stat3Value": "6 weeks", "stat3Label": "Timeline"}),
            ("content-text-image", {"heading": "The Challenge", "bodyText": "Velocity Labs had a great product but their website wasn't converting. Visitors were bouncing within seconds. They needed a complete brand overhaul that communicated trust and value.", "image": "https://placehold.co/280x200/FFF1F2/E11D48?text=Before+%26+After"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Want Results Like This?", "supportText": "Every project starts with understanding your goals.", "buttonText": "Let's Talk"},
    },
    "agency-launch": {
        "hero": "hero-image", "hero_vars": {"headline": "Now Offering: AI Brand Strategy", "subtitle": "Data-driven brand positioning powered by artificial intelligence.", "buttonText": "Learn More", "heroImage": "https://placehold.co/600x250/0C0A09/FFFFFF?text=AI+Brand+Strategy"},
        "middle": [
            ("content-checklist", {"heading": "What's Included", "item1": "AI-powered competitive analysis report", "item2": "Brand positioning matrix with data insights", "item3": "Visual identity recommendations", "item4": "90-day content strategy roadmap"}),
            ("coupon-banner", {"heading": "Launch Special", "couponCode": "AIBRAND", "expiryText": "First 10 clients get 25% off", "buttonText": "Claim Your Spot"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Limited Availability", "supportText": "We take on only 5 new AI strategy clients per month.", "buttonText": "Apply Now"},
    },
    "generic-sale": {
        "hero": "hero-bold", "hero_vars": {"headline": "Massive Sale — Up to 60% Off", "subtitle": "Our biggest sale of the year. Everything must go.", "buttonText": "Shop the Sale"},
        "middle": [
            ("product-3col", {"product1Name": "Best Seller #1", "product1Price": "$29 $72", "product2Name": "Best Seller #2", "product2Price": "$39 $98", "product3Name": "Best Seller #3", "product3Price": "$19 $48"}),
            ("countdown-urgency", {"heading": "Hurry — Sale Ends Sunday!", "bodyText": "Once it's gone, it's gone. No rainchecks, no extensions.", "buttonText": "Shop All Deals"}),
            ("coupon-banner", {"heading": "Stack & Save", "couponCode": "EXTRA15", "expiryText": "Extra 15% off sale prices", "buttonText": "Apply Code"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Free Shipping on Everything", "supportText": "No minimum order. Delivery in 3-5 business days.", "buttonText": "Start Shopping →"},
    },
    "generic-newsletter": {
        "hero": "hero-minimal", "hero_vars": {"headline": "The Weekly Brief", "bodyText": "News, insights, and tips delivered to your inbox every Friday."},
        "middle": [
            ("content-text-image", {"heading": "Featured: The Future of Remote Work", "bodyText": "As companies navigate return-to-office policies, a new study reveals that hybrid work isn't just preferred — it's more productive. Here's what the data says.", "image": "https://placehold.co/280x200/F3F4F6/6B7280?text=Remote+Work"}),
            ("content-checklist", {"heading": "Quick Links", "item1": "Read: 5 productivity hacks for remote teams", "item2": "Watch: Interview with our CEO on industry trends", "item3": "Download: Free template pack for project planning", "item4": "Join: Our community Slack with 5,000+ members"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Share the Brief", "supportText": "Know someone who'd enjoy this newsletter?", "buttonText": "Forward to a Friend"},
    },
    "generic-thankyou": {
        "hero": "hero-minimal", "hero_vars": {"headline": "Thank You!", "bodyText": "We truly appreciate your support. Here's what happens next."},
        "middle": [
            ("content-checklist", {"heading": "Next Steps", "item1": "Check your inbox for a confirmation email", "item2": "You'll receive updates within 24 hours", "item3": "Bookmark your dashboard for easy access", "item4": "Reach out anytime — we're here to help"}),
            ("content-testimonial", {"quote": "The onboarding experience was seamless. I was up and running in minutes. Highly recommend!", "authorName": "Jamie Park", "authorRole": "Happy Customer"}),
        ],
        "cta": "cta-single", "cta_vars": {"heading": "Need Help?", "supportText": "Our support team is available 24/7.", "buttonText": "Contact Support"},
    },
}


def build_template(slug, spec, palette):
    """Build a complete template from spec + palette."""
    template = {"components": []}

    # Hero
    hero = local_preset_loader(spec["hero"])
    hero_vars = {**spec.get("hero_vars", {})}
    hero_vars["primaryColor"] = palette["primary"]
    if "backgroundColor" in (hero.get("variables") or {}):
        hero_vars["backgroundColor"] = palette["primary"]
    hero["customizations"] = hero_vars
    template = inject_preset(template, hero)

    # Middle sections
    for preset_id, custom_vars in spec.get("middle", []):
        preset = local_preset_loader(preset_id)
        vars_with_palette = {**custom_vars}
        if "accentColor" in (preset.get("variables") or {}):
            vars_with_palette["accentColor"] = palette["accent"]
        if "backgroundColor" in (preset.get("variables") or {}) and "backgroundColor" not in custom_vars:
            vars_with_palette["backgroundColor"] = palette["bg"]
        if "buttonColor" in (preset.get("variables") or {}):
            vars_with_palette["buttonColor"] = palette["cta"]
        if "urgentColor" in (preset.get("variables") or {}):
            vars_with_palette["urgentColor"] = palette["secondary"]
        preset["customizations"] = vars_with_palette
        template = inject_preset(template, preset)

    # CTA
    cta = local_preset_loader(spec.get("cta", "cta-single"))
    cta_vars = {**spec.get("cta_vars", {})}
    cta_vars["buttonColor"] = palette["cta"]
    if "primaryColor" in (cta.get("variables") or {}):
        cta_vars["primaryColor"] = palette["cta"]
    cta["customizations"] = cta_vars
    template = inject_preset(template, cta)

    # Footer
    footer = local_preset_loader("footer-simple")
    footer["customizations"] = {"backgroundColor": palette["primary"]}
    template = inject_preset(template, footer)

    return template["components"]


def main():
    print(f"Generating {len(SPECS)} unique templates...")

    session = get_session()
    try:
        for slug, spec in SPECS.items():
            industry = slug.split("-")[0]
            if industry == "ecom":
                industry = "ecommerce"
            elif industry == "edu":
                industry = "education"
            elif industry == "realestate":
                industry = "real_estate"

            palette = PALETTES.get(industry, PALETTES["other"])

            print(f"  {slug}...", end=" ")

            # Build components
            components = build_template(slug, spec, palette)

            # Update DB
            existing = session.query(TemplateLibraryItem).filter_by(slug=slug).first()
            if existing:
                existing.components = components
                session.commit()
                print(f"updated ({len(components)} rows)")
            else:
                print("not found in DB, skipping")

        session.commit()
        print(f"\nDone! All {len(SPECS)} templates updated with unique designs.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
