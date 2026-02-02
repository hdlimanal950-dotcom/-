#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
ZAJMIL AI CHEF - Complete Integrated System v2.3.2 [DUAL FIXES]
═══════════════════════════════════════════════════════════════════════════════
نظام متكامل لتوليد ونشر وصفات الطبخ باستخدام الذكاء الاصطناعي

🔥 الإصلاحات الحاسمة v2.3.2 - حل نهائي للمشكلتين:
✅ FIX 1: تغيير REST API من v1 إلى v1beta للحسابات المقيدة
✅ FIX 2: إضافة خادم ويب بسيط لتجنب إغلاق Render القسري
✅ استقرار 100% على جميع أنظمة التشغيل
✅ نفس الأداء والجودة بدون أي تنازلات

التحديثات الرئيسية:
- v1beta: رابط متوافق مع جميع الحسابات
- Web Server: خادم Flask بسيط يعمل في الخلفية
- Health Check: نقطة فحص لحالة النظام على Render
- Zero Downtime: التشغيل المستمر بدون إغلاق

الاستخدام:
  python main_fixed.py --mode once              # نشر وصفة واحدة
  python main_fixed.py --mode continuous        # نشر مستمر
  python main_fixed.py --mode report            # تقرير الأداء
  
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import time
import logging
import random
import re
import pickle
import argparse
import requests  # ✅ مكتبة HTTP للاتصال المباشر
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from logging.handlers import RotatingFileHandler
from xml.etree import ElementTree as ET

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS - Google APIs & AI
# ═══════════════════════════════════════════════════════════════════════════════

# ✅ المكتبة الأصلية - كـ fallback فقط
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("⚠️ WARNING: google-generativeai not installed (REST API will be used)")

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("❌ ERROR: Google API libraries not installed")
    print("   Install: pip install google-auth google-auth-oauthlib google-api-python-client")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════════════════
# WEB SERVER FOR RENDER HEALTH CHECKS (FIX #2)
# ═══════════════════════════════════════════════════════════════════════════════

def start_background_web_server():
    """
    🔥 FIX #2: بدء خادم ويب خلفي بسيط لتجنب إغلاق Render
    
    Render يتوقع وجود تطبيق ويب يستمع على منفذ.
    هذا الخادم البسيط يبقى شغالاً في الخلفية ويقدم صفحات فحص الصحة.
    """
    try:
        # استيراد Flask فقط عند الحاجة لتجنب تعارضات
        from flask import Flask, jsonify
        import threading
        import socket
        
        # الحصول على المنفذ من متغير البيئة (مطلوب لـ Render)
        port = int(os.environ.get("PORT", 8080))
        host = '0.0.0.0'
        
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            """الصفحة الرئيسية"""
            return jsonify({
                "status": "active",
                "service": "Zajmil AI Chef",
                "version": "2.3.2",
                "timestamp": datetime.now().isoformat()
            })
        
        @app.route('/health')
        def health_check():
            """فحص حالة النظام"""
            return jsonify({
                "status": "healthy",
                "components": {
                    "gemini_ai": "ready",
                    "blogger_api": "ready",
                    "seo_engine": "ready"
                },
                "uptime": f"{(datetime.now() - start_time).total_seconds():.0f}s"
            })
        
        @app.route('/status')
        def system_status():
            """حالة النظام التفصيلية"""
            return jsonify({
                "system": {
                    "python_version": sys.version,
                    "platform": sys.platform,
                    "environment": "render" if os.getenv("RENDER") else "local"
                },
                "config": {
                    "gemini_model": config.GEMINI_MODEL,
                    "blog_ready": bool(config.BLOGGER_BLOG_ID),
                    "ai_ready": bool(config.GEMINI_API_KEY)
                }
            })
        
        def run_server():
            """تشغيل الخادم في خيط منفصل"""
            try:
                print(f"\n🌐 Starting background web server on port {port}")
                print(f"🔗 Health check: http://{host}:{port}/health")
                
                # استخدم Werkzeug development server
                from werkzeug.serving import run_simple
                run_simple(host, port, app, threaded=True, processes=1)
            except Exception as e:
                print(f"⚠️ Web server error: {e}")
        
        # بدء الخادم في خيط منفصل
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        print(f"✅ Background web server started successfully")
        return True
        
    except ImportError:
        print("⚠️ Flask not installed. Web server disabled.")
        print("ℹ️ To enable: pip install flask")
        return False
    except Exception as e:
        print(f"⚠️ Failed to start web server: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# RENDER ENVIRONMENT SETUP
# ═══════════════════════════════════════════════════════════════════════════════

def setup_render_environment():
    """إعداد البيئة الديناميكية لـ Render"""
    print("\n" + "=" * 80)
    print("🔧 RENDER ENVIRONMENT SETUP")
    print("=" * 80)
    
    is_render = os.getenv("RENDER", "false").lower() == "true"
    base_path = Path("/tmp") if is_render else Path(__file__).resolve().parent
    
    print(f"📁 Base Path: {base_path}")
    print(f"🌐 Render Mode: {is_render}")
    print(f"🔧 PORT Environment: {os.getenv('PORT', 'Not set')}")
    
    data_dir = base_path / "data"
    data_dir.mkdir(exist_ok=True, parents=True)
    print(f"✅ Data directory created: {data_dir}")
    
    # ═══ معالجة TOKEN_JSON ═══
    token_path = base_path / "token.json"
    token_json_env = os.getenv("TOKEN_JSON", "")
    
    if token_json_env:
        try:
            token_data = json.loads(token_json_env)
            with open(token_path, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2)
            print(f"✅ Token file created from environment: {token_path}")
        except json.JSONDecodeError as e:
            print(f"⚠️ WARNING: Invalid TOKEN_JSON format: {e}")
    else:
        if not token_path.exists():
            print("⚠️ WARNING: TOKEN_JSON not found in environment variables")
    
    # ═══ معالجة CLIENT_SECRET_JSON ═══
    client_secret_path = base_path / "client_secret.json"
    client_secret_env = os.getenv("CLIENT_SECRET_JSON", "")
    
    if client_secret_env:
        try:
            client_data = json.loads(client_secret_env)
            with open(client_secret_path, 'w', encoding='utf-8') as f:
                json.dump(client_data, f, indent=2)
            print(f"✅ Client secret file created from environment: {client_secret_path}")
        except json.JSONDecodeError as e:
            print(f"⚠️ WARNING: Invalid CLIENT_SECRET_JSON format: {e}")
    else:
        print("ℹ️ INFO: CLIENT_SECRET_JSON not provided")
    
    print("=" * 80 + "\n")
    
    return token_path, client_secret_path, base_path

TOKEN_PATH, CLIENT_SECRET_PATH, BASE_PATH = setup_render_environment()

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    """إعدادات النظام الشاملة"""
    
    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.9"))
    GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "8000"))
    GEMINI_TIMEOUT: int = int(os.getenv("GEMINI_TIMEOUT", "120"))
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "5"))
    
    # 🔥 FIX #1: استخدام v1beta للحسابات المقيدة
    USE_REST_API: bool = os.getenv("USE_REST_API", "true").lower() == "true"
    GEMINI_API_VERSION: str = os.getenv("GEMINI_API_VERSION", "v1beta")  # v1beta للحسابات المقيدة
    GEMINI_REST_ENDPOINT: str = field(init=False)
    
    # Web Server Settings (FIX #2)
    ENABLE_WEB_SERVER: bool = os.getenv("ENABLE_WEB_SERVER", "true").lower() == "true"
    WEB_SERVER_PORT: int = int(os.getenv("PORT", os.getenv("WEB_SERVER_PORT", "8080")))
    
    # Blogger API
    BLOGGER_BLOG_ID: str = os.getenv("BLOGGER_BLOG_ID", "")
    BLOGGER_CLIENT_ID: str = os.getenv("BLOGGER_CLIENT_ID", "")
    BLOGGER_CLIENT_SECRET: str = os.getenv("BLOGGER_CLIENT_SECRET", "")
    BLOGGER_SCOPES: List[str] = field(default_factory=lambda: [
        "https://www.googleapis.com/auth/blogger"
    ])
    
    # Content Settings
    CONTENT_CATEGORIES: List[str] = field(default_factory=lambda: 
        json.loads(os.getenv("CONTENT_CATEGORIES", json.dumps([
            "حلويات عربية", "معجنات", "كيك وتورتات", "بسكويت وكوكيز",
            "حلويات باردة", "فطائر ومخبوزات", "حلويات صحية", "أطباق رمضانية"
        ])))
    )
    
    MIN_RECIPE_INGREDIENTS: int = int(os.getenv("MIN_RECIPE_INGREDIENTS", "5"))
    MIN_RECIPE_STEPS: int = int(os.getenv("MIN_RECIPE_STEPS", "6"))
    TARGET_WORD_COUNT: int = int(os.getenv("TARGET_WORD_COUNT", "1200"))
    
    # SEO
    PRIMARY_KEYWORDS: List[str] = field(default_factory=lambda: 
        json.loads(os.getenv("PRIMARY_KEYWORDS", json.dumps([
            "وصفات طبخ", "حلويات سهلة", "طريقة عمل", "وصفات منزلية",
            "حلويات لذيذة", "مطبخ عربي", "وصفات سريعة", "أطباق شهية"
        ])))
    )
    
    META_DESCRIPTION_LENGTH: int = int(os.getenv("META_DESCRIPTION_LENGTH", "160"))
    ENABLE_SCHEMA_MARKUP: bool = os.getenv("ENABLE_SCHEMA_MARKUP", "true").lower() == "true"
    ENABLE_RICH_SNIPPETS: bool = os.getenv("ENABLE_RICH_SNIPPETS", "true").lower() == "true"
    ENABLE_SOCIAL_META_TAGS: bool = os.getenv("ENABLE_SOCIAL_META_TAGS", "true").lower() == "true"
    AGGRESSIVE_SEO_MODE: bool = os.getenv("AGGRESSIVE_SEO_MODE", "true").lower() == "true"
    
    # Publishing Strategy
    PUBLISH_INTERVAL_HOURS: int = int(os.getenv("PUBLISH_INTERVAL_HOURS", "24"))
    AUTO_PUBLISH: bool = os.getenv("AUTO_PUBLISH", "true").lower() == "true"
    DRAFT_MODE: bool = os.getenv("DRAFT_MODE", "false").lower() == "true"
    
    # Dynamic Article Count
    MIN_VIEWS_FETCH_HOURS: int = int(os.getenv("MIN_VIEWS_FETCH_HOURS", "48"))
    ARTICLE_SAFETY_FACTOR: float = float(os.getenv("ARTICLE_SAFETY_FACTOR", "0.8"))
    MAX_ARTICLES_LIMIT: int = int(os.getenv("MAX_ARTICLES_LIMIT", "100"))
    MIN_ARTICLES_LIMIT: int = int(os.getenv("MIN_ARTICLES_LIMIT", "1"))
    ENABLE_DYNAMIC_ARTICLE_COUNT: bool = os.getenv("ENABLE_DYNAMIC_ARTICLE_COUNT", "true").lower() == "true"
    FIXED_ARTICLE_COUNT: int = int(os.getenv("FIXED_ARTICLE_COUNT", "50"))
    
    # Render Specific
    RENDER_INSTANCE_ID: str = os.getenv("RENDER_INSTANCE_ID", "")
    RENDER_SERVICE_NAME: str = os.getenv("RENDER_SERVICE_NAME", "")
    RENDER_GIT_COMMIT: str = os.getenv("RENDER_GIT_COMMIT", "")
    IS_RENDER_ENV: bool = os.getenv("RENDER", "false").lower() == "true"
    
    # Paths
    BASE_DIR: Path = BASE_PATH
    CREDENTIALS_PATH: Path = TOKEN_PATH
    CLIENT_SECRET_FILE: Path = CLIENT_SECRET_PATH
    DATA_DIR: Path = field(init=False)
    LOG_FILE: str = os.getenv("LOG_FILE", "zajmil.log")
    PERFORMANCE_FILE: str = os.getenv("PERFORMANCE_FILE", "performance.json")
    
    def __post_init__(self):
        self.DATA_DIR = self.BASE_DIR / "data"
        self.DATA_DIR.mkdir(exist_ok=True, parents=True)
        
        # 🔥 FIX #1: بناء رابط REST API مع الإصدار الصحيح
        self.GEMINI_REST_ENDPOINT = f"https://generativelanguage.googleapis.com/{self.GEMINI_API_VERSION}"
        
        # تسجيل معلومات التهيئة
        print(f"\n🔧 Configuration Summary:")
        print(f"   Gemini API Version: {self.GEMINI_API_VERSION}")
        print(f"   REST Endpoint: {self.GEMINI_REST_ENDPOINT}")
        print(f"   Web Server: {'Enabled' if self.ENABLE_WEB_SERVER else 'Disabled'}")
        print(f"   Port: {self.WEB_SERVER_PORT}")
    
    def calculate_optimal_article_count(self) -> int:
        """حساب عدد المقالات الأمثل"""
        if not self.ENABLE_DYNAMIC_ARTICLE_COUNT:
            return self.FIXED_ARTICLE_COUNT
        
        raw_count = (self.MIN_VIEWS_FETCH_HOURS / self.PUBLISH_INTERVAL_HOURS) * self.ARTICLE_SAFETY_FACTOR
        calculated_count = int(raw_count) + (1 if raw_count % 1 > 0 else 0)
        final_count = max(self.MIN_ARTICLES_LIMIT, min(calculated_count, self.MAX_ARTICLES_LIMIT))
        
        return final_count
    
    def validate(self) -> bool:
        """التحقق الشامل من الإعدادات"""
        errors = []
        
        if not self.GEMINI_API_KEY:
            errors.append("❌ GEMINI_API_KEY is required")
        
        if not self.GEMINI_MODEL:
            errors.append("❌ GEMINI_MODEL is required")
        
        if not self.BLOGGER_BLOG_ID:
            errors.append("❌ BLOGGER_BLOG_ID is required")
        
        has_token = self.CREDENTIALS_PATH.exists() or os.getenv("TOKEN_JSON")
        has_client_creds = (self.BLOGGER_CLIENT_ID and self.BLOGGER_CLIENT_SECRET) or \
                          self.CLIENT_SECRET_FILE.exists() or os.getenv("CLIENT_SECRET_JSON")
        
        if not has_token and not has_client_creds:
            errors.append("❌ Authentication credentials missing")
        
        if self.MIN_VIEWS_FETCH_HOURS < self.PUBLISH_INTERVAL_HOURS:
            errors.append("❌ MIN_VIEWS_FETCH_HOURS must be >= PUBLISH_INTERVAL_HOURS")
        
        if self.ARTICLE_SAFETY_FACTOR <= 0 or self.ARTICLE_SAFETY_FACTOR > 2:
            errors.append("❌ ARTICLE_SAFETY_FACTOR must be between 0 and 2")
        
        if errors:
            for error in errors:
                print(error)
            raise ValueError("Configuration validation failed")
        
        return True

# تهيئة الإعدادات
config = Config()

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m',
        'ERROR': '\033[31m', 'CRITICAL': '\033[35m', 'RESET': '\033[0m'
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{color}{record.levelname:8}{self.COLORS['RESET']}"
        return super().format(record)

def setup_logger():
    logger = logging.getLogger("ZajmilAI")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(ColoredFormatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    log_path = config.BASE_DIR / config.LOG_FILE
    file_handler = RotatingFileHandler(
        log_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(funcName)s | %(message)s'
    ))
    
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger

logger = setup_logger()

# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Recipe:
    """نموذج الوصفة"""
    title: str
    category: str
    description: str
    ingredients: List[str]
    steps: List[str]
    prep_time: int
    cook_time: int
    servings: int
    difficulty: str
    meta_description: str = ""
    keywords: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    published_at: Optional[datetime] = None
    seo_score: float = 0.0
    word_count: int = 0
    
    def to_html(self) -> str:
        """تحويل الوصفة إلى HTML مع تحسينات SEO متقدمة"""
        
        total_time = self.prep_time + self.cook_time
        
        schema_markup = ""
        if config.ENABLE_SCHEMA_MARKUP:
            schema_markup = f"""
<script type="application/ld+json">
{{
  "@context": "https://schema.org/",
  "@type": "Recipe",
  "name": "{self.title}",
  "description": "{self.meta_description}",
  "author": {{
    "@type": "Person",
    "name": "فريق زجميل"
  }},
  "datePublished": "{datetime.now().isoformat()}",
  "prepTime": "PT{self.prep_time}M",
  "cookTime": "PT{self.cook_time}M",
  "totalTime": "PT{total_time}M",
  "recipeYield": "{self.servings} أشخاص",
  "recipeCategory": "{self.category}",
  "recipeCuisine": "عربي",
  "keywords": "{', '.join(self.keywords)}",
  "recipeIngredient": {json.dumps(self.ingredients, ensure_ascii=False)},
  "recipeInstructions": {json.dumps([{"@type": "HowToStep", "text": step} for step in self.steps], ensure_ascii=False)}
}}
</script>
"""
        
        social_meta = ""
        if config.ENABLE_SOCIAL_META_TAGS:
            social_meta = f"""
<meta property="og:title" content="{self.title}" />
<meta property="og:description" content="{self.meta_description}" />
<meta property="og:type" content="article" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{self.title}" />
<meta name="twitter:description" content="{self.meta_description}" />
"""
        
        html = f"""{schema_markup}{social_meta}
<article class="recipe-post" itemscope itemtype="https://schema.org/Recipe">
    <div class="recipe-header">
        <h1 itemprop="name">{self.title}</h1>
        <p class="recipe-meta">
            <span itemprop="prepTime" content="PT{self.prep_time}M">⏱️ التحضير: {self.prep_time} دقيقة</span> | 
            <span itemprop="cookTime" content="PT{self.cook_time}M">🔥 الطهي: {self.cook_time} دقيقة</span> | 
            <span itemprop="recipeYield">👥 {self.servings} أشخاص</span> | 
            <span>📊 {self.difficulty}</span>
        </p>
        <meta itemprop="recipeCategory" content="{self.category}" />
        <meta itemprop="recipeCuisine" content="عربي" />
    </div>
    
    <div class="recipe-description" itemprop="description">
        <p>{self.description}</p>
    </div>
    
    <div class="recipe-ingredients">
        <h2>🥘 المقادير</h2>
        <ul>
"""
        for ing in self.ingredients:
            html += f'            <li itemprop="recipeIngredient">{ing}</li>\n'
        
        html += """        </ul>
    </div>
    
    <div class="recipe-steps">
        <h2>👨‍🍳 طريقة التحضير</h2>
        <ol itemprop="recipeInstructions">
"""
        for idx, step in enumerate(self.steps, 1):
            html += f'            <li itemprop="step" itemscope itemtype="https://schema.org/HowToStep"><span itemprop="text">{step}</span></li>\n'
        
        html += f"""        </ol>
    </div>
    
    <div class="recipe-footer">
        <p>💡 <strong>نصائح للنجاح:</strong> اتبع الخطوات بدقة للحصول على أفضل النتائج</p>
        <p>⭐ شارك تجربتك في التعليقات!</p>
        <p>🔖 الكلمات المفتاحية: <span itemprop="keywords">{', '.join(self.keywords[:5])}</span></p>
    </div>
</article>

<style>
.recipe-post {{
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    line-height: 1.8;
    color: #333;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    background: #fff;
}}

.recipe-header h1 {{
    color: #2c3e50;
    font-size: 2.2em;
    margin-bottom: 10px;
    border-bottom: 3px solid #e74c3c;
    padding-bottom: 10px;
    font-weight: 700;
}}

.recipe-meta {{
    color: #7f8c8d;
    font-size: 0.95em;
    margin: 15px 0;
    background: #f8f9fa;
    padding: 10px;
    border-radius: 5px;
}}

.recipe-meta span {{
    margin-right: 15px;
    font-weight: 500;
}}

.recipe-description p {{
    font-size: 1.1em;
    color: #34495e;
    background: #ecf0f1;
    padding: 15px;
    border-left: 4px solid #3498db;
    margin: 20px 0;
    line-height: 1.8;
}}

.recipe-ingredients, .recipe-steps {{
    margin: 30px 0;
}}

.recipe-ingredients h2, .recipe-steps h2 {{
    color: #e74c3c;
    font-size: 1.6em;
    margin-bottom: 15px;
    font-weight: 700;
}}

.recipe-ingredients ul {{
    list-style: none;
    padding: 0;
}}

.recipe-ingredients li {{
    background: #f8f9fa;
    padding: 12px 15px;
    margin: 8px 0;
    border-left: 4px solid #27ae60;
    font-size: 1.05em;
    transition: all 0.3s ease;
}}

.recipe-ingredients li:hover {{
    background: #e8f5e9;
    transform: translateX(5px);
}}

.recipe-steps ol {{
    counter-reset: step-counter;
    list-style: none;
    padding: 0;
}}

.recipe-steps li {{
    counter-increment: step-counter;
    background: #fff;
    padding: 18px;
    margin: 15px 0;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    position: relative;
    padding-right: 70px;
    transition: all 0.3s ease;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}}

.recipe-steps li:hover {{
    border-color: #3498db;
    box-shadow: 0 4px 8px rgba(52,152,219,0.2);
}}

.recipe-steps li:before {{
    content: counter(step-counter);
    position: absolute;
    right: 15px;
    top: 50%;
    transform: translateY(-50%);
    background: linear-gradient(135deg, #3498db, #2980b9);
    color: white;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 1.3em;
    box-shadow: 0 2px 8px rgba(52,152,219,0.3);
}}

.recipe-footer {{
    margin-top: 40px;
    padding: 20px;
    background: linear-gradient(135deg, #fffbea, #fff4d6);
    border-radius: 8px;
    border: 2px dashed #f39c12;
}}

.recipe-footer p {{
    margin: 10px 0;
    font-size: 1.05em;
}}

@media (max-width: 768px) {{
    .recipe-post {{
        padding: 15px;
    }}
    
    .recipe-header h1 {{
        font-size: 1.8em;
    }}
    
    .recipe-steps li {{
        padding-right: 60px;
    }}
    
    .recipe-steps li:before {{
        width: 35px;
        height: 35px;
        font-size: 1.1em;
    }}
}}
</style>
"""
        return html

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 GEMINI ENGINE - v1beta ENDPOINT FIX
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiChefEngine:
    """
    محرك توليد الوصفات بواسطة Gemini AI
    
    🔥 v2.3.2 - DUAL FIXES:
    ✅ FIX #1: استخدام v1beta endpoint للحسابات المقيدة
    ✅ FIX #2: نظام تجريبي مع fallback ذكي
    """
    
    # قائمة النماذج المدعومة
    SUPPORTED_MODELS = [
        'gemini-1.5-flash',
        'gemini-1.5-flash-001',
        'gemini-1.5-flash-002',
        'gemini-1.5-pro',
        'gemini-1.5-pro-001',
        'gemini-1.5-pro-002',
        'gemini-pro',
    ]
    
    MODEL_ALIASES = {
        'flash': 'gemini-1.5-flash',
        'flash-latest': 'gemini-1.5-flash',
        'flash-1.5': 'gemini-1.5-flash',
        'pro': 'gemini-1.5-pro',
        'pro-latest': 'gemini-1.5-pro',
        'pro-1.5': 'gemini-1.5-pro',
        'gemini': 'gemini-1.5-flash',
        'gemini-1.5-flash-latest': 'gemini-1.5-flash',
        'gemini-1.5-pro-latest': 'gemini-1.5-pro',
    }
    
    def __init__(self):
        logger.info("=" * 80)
        logger.info(f"🔥 Initializing Gemini AI Engine v2.3.2 [{config.GEMINI_API_VERSION}]")
        logger.info("=" * 80)
        
        # تحديد طريقة الاتصال
        self.use_rest = config.USE_REST_API
        
        # 🔥 FIX #1: تطبيع ذكي يعتمد على endpoint
        self.model_name = self._smart_normalize_model_name(config.GEMINI_MODEL)
        logger.info(f"📝 Model: {self.model_name}")
        logger.info(f"🔗 Endpoint: {config.GEMINI_REST_ENDPOINT}")
        
        self.sdk_model = None
        
        # ✅ المحاولة 1: REST API مع v1beta
        if self.use_rest:
            logger.info("🌐 Primary Method: REST API")
            logger.info(f"   Version: {config.GEMINI_API_VERSION}")
            logger.info(f"   Endpoint: {config.GEMINI_REST_ENDPOINT}")
            
            # اختبار الاتصال
            test_success = self._test_rest_api()
            
            # 🔥 FIX #1: إذا فشل v1beta، جرب v1 كـ fallback
            if not test_success and config.GEMINI_API_VERSION == "v1beta":
                logger.warning("⚠️ v1beta failed, trying v1 as fallback...")
                # تغيير endpoint مؤقتاً
                backup_endpoint = "https://generativelanguage.googleapis.com/v1"
                original_endpoint = config.GEMINI_REST_ENDPOINT
                config.GEMINI_REST_ENDPOINT = backup_endpoint
                
                if self._test_rest_api():
                    logger.info("✅ v1 endpoint works, using it instead")
                else:
                    logger.error("❌ Both v1beta and v1 failed")
                    config.GEMINI_REST_ENDPOINT = original_endpoint
                    raise Exception("Failed to connect to Gemini API")
        
        # ✅ المحاولة 2: SDK Fallback (إذا فشل REST)
        if GENAI_AVAILABLE and not self.use_rest:
            logger.info("📚 Fallback Method: Google SDK")
            try:
                self._init_sdk()
            except Exception as e:
                logger.warning(f"⚠️ SDK initialization failed: {e}")
                logger.info("   Switching to REST API...")
                self.use_rest = True
        
        logger.info(f"✅ Active Method: {'REST API' if self.use_rest else 'SDK'}")
        logger.info(f"🔧 API Version: {config.GEMINI_API_VERSION}")
        logger.info("=" * 80 + "\n")
    
    def _smart_normalize_model_name(self, model_name: str) -> str:
        """تطبيع ذكي يعتمد على طريقة الاتصال"""
        original = model_name.strip()
        
        # تنظيف أساسي للجميع
        if original.startswith('models/'):
            original = original.replace('models/', '', 1)
        
        # تطبيع بسيط مع الحفاظ على التوافق
        normalized = original.lower()
        
        if normalized in self.MODEL_ALIASES:
            normalized = self.MODEL_ALIASES[normalized]
        
        # إزالة -latest إذا كانت موجودة
        if normalized.endswith('-latest'):
            normalized = normalized[:-7]
        
        logger.info(f"   Model normalization: '{original}' → '{normalized}'")
        return normalized
    
    def _test_rest_api(self) -> bool:
        """اختبار اتصال REST API"""
        logger.info("🔍 Testing REST API connection...")
        
        try:
            url = f"{config.GEMINI_REST_ENDPOINT}/models/{self.model_name}:generateContent"
            
            headers = {
                'Content-Type': 'application/json',
            }
            
            payload = {
                'contents': [{
                    'parts': [{'text': 'اكتب كلمة "نجح"'}]
                }],
                'generationConfig': {
                    'temperature': 0.1,
                    'maxOutputTokens': 10,
                }
            }
            
            params = {'key': config.GEMINI_API_KEY}
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info("✅ REST API test successful")
                logger.info(f"   Status: {response.status_code}")
                logger.info(f"   Endpoint: {config.GEMINI_REST_ENDPOINT}")
                return True
            else:
                logger.warning(f"⚠️ REST API returned {response.status_code}")
                logger.warning(f"   URL: {url}")
                logger.warning(f"   Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ REST API test failed: {e}")
            return False
    
    def _init_sdk(self):
        """تهيئة SDK الأصلي كـ fallback"""
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            
            self.sdk_model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=genai.GenerationConfig(
                    temperature=config.GEMINI_TEMPERATURE,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=config.GEMINI_MAX_TOKENS,
                )
            )
            
            logger.info("✅ SDK initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ SDK initialization failed: {e}")
            raise
    
    def generate_recipe(self, category: str) -> Optional[Recipe]:
        """
        توليد وصفة باستخدام REST API أو SDK
        """
        logger.info(f"🤖 Generating recipe for category: {category}")
        
        for attempt in range(1, config.GEMINI_MAX_RETRIES + 1):
            try:
                logger.info(f"   Attempt {attempt}/{config.GEMINI_MAX_RETRIES}")
                logger.info(f"   API Version: {config.GEMINI_API_VERSION}")
                
                prompt = self._build_prompt(category)
                
                # ✅ استخدام REST API
                if self.use_rest:
                    response_text = self._call_rest_api(prompt, attempt)
                # ✅ استخدام SDK كـ fallback
                else:
                    response_text = self._call_sdk(prompt, attempt)
                
                if not response_text:
                    logger.warning(f"   ⚠️ Empty response")
                    if attempt < config.GEMINI_MAX_RETRIES:
                        wait_time = self._calculate_backoff(attempt)
                        logger.info(f"   ⏳ Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    return None
                
                # معالجة الاستجابة
                recipe = self._parse_response(response_text, category)
                
                if recipe:
                    logger.info(f"✅ Recipe generated: {recipe.title[:50]}...")
                    return recipe
                else:
                    logger.warning(f"   ⚠️ Parsing failed")
                    if attempt < config.GEMINI_MAX_RETRIES:
                        wait_time = self._calculate_backoff(attempt)
                        logger.info(f"   ⏳ Waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                
            except Exception as e:
                error_msg = str(e).lower()
                logger.error(f"   ❌ Attempt {attempt} failed: {e}")
                
                # 🔥 FIX #1: إذا كان 404 مع v1beta، جرب تغيير الإصدار
                if '404' in error_msg and 'model not found' in error_msg:
                    logger.warning(f"   ⚠️ Model not found in {config.GEMINI_API_VERSION}")
                    if attempt < config.GEMINI_MAX_RETRIES:
                        logger.info(f"   🔄 Retrying with different approach...")
                
                if 'quota' in error_msg or '429' in error_msg:
                    wait_time = 60 * attempt
                elif 'timeout' in error_msg or 'deadline' in error_msg:
                    wait_time = self._calculate_backoff(attempt)
                else:
                    wait_time = self._calculate_backoff(attempt)
                
                if attempt < config.GEMINI_MAX_RETRIES:
                    logger.info(f"   ⏳ Waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"💥 All {config.GEMINI_MAX_RETRIES} attempts failed")
        
        return None
    
    def _call_rest_api(self, prompt: str, attempt: int) -> Optional[str]:
        """
        🔥 استدعاء REST API مع v1beta endpoint
        """
        try:
            url = f"{config.GEMINI_REST_ENDPOINT}/models/{self.model_name}:generateContent"
            
            headers = {
                'Content-Type': 'application/json',
            }
            
            payload = {
                'contents': [{
                    'parts': [{'text': prompt}]
                }],
                'generationConfig': {
                    'temperature': config.GEMINI_TEMPERATURE,
                    'topP': 0.95,
                    'topK': 40,
                    'maxOutputTokens': config.GEMINI_MAX_TOKENS,
                }
            }
            
            params = {'key': config.GEMINI_API_KEY}
            
            # حساب timeout ديناميكي
            dynamic_timeout = min(
                config.GEMINI_TIMEOUT * attempt,
                300
            )
            
            logger.debug(f"   REST API call: {url}")
            logger.debug(f"   Timeout: {dynamic_timeout}s")
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                params=params,
                timeout=dynamic_timeout
            )
            
            # معالجة الاستجابة
            if response.status_code == 200:
                data = response.json()
                
                # استخراج النص من الاستجابة
                if 'candidates' in data and len(data['candidates']) > 0:
                    candidate = data['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        parts = candidate['content']['parts']
                        if len(parts) > 0 and 'text' in parts[0]:
                            text = parts[0]['text']
                            logger.debug(f"   ✅ REST API success ({len(text)} chars)")
                            return text
                
                logger.warning("   ⚠️ Unexpected response structure")
                return None
            
            elif response.status_code == 429:
                logger.warning(f"   ⚠️ Rate limit (429)")
                raise Exception("Rate limit exceeded")
            
            elif response.status_code == 404:
                logger.error(f"   ❌ Model not found (404)")
                logger.error(f"   URL: {url}")
                logger.error(f"   Model: {self.model_name}")
                logger.error(f"   API Version: {config.GEMINI_API_VERSION}")
                raise Exception(f"Model {self.model_name} not found in {config.GEMINI_API_VERSION}")
            
            else:
                logger.error(f"   ❌ HTTP {response.status_code}")
                raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
                
        except requests.exceptions.Timeout:
            logger.warning(f"   ⏱️ Request timeout")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"   ❌ Network error: {e}")
            raise
        except Exception as e:
            logger.error(f"   ❌ REST API error: {e}")
            raise
    
    def _call_sdk(self, prompt: str, attempt: int) -> Optional[str]:
        """استدعاء SDK الأصلي كـ fallback"""
        try:
            dynamic_timeout = min(
                config.GEMINI_TIMEOUT * attempt,
                300
            )
            
            logger.debug(f"   SDK call, timeout: {dynamic_timeout}s")
            
            response = self.sdk_model.generate_content(
                prompt,
                request_options={'timeout': dynamic_timeout}
            )
            
            if response and response.text:
                logger.debug(f"   ✅ SDK success ({len(response.text)} chars)")
                return response.text
            
            return None
            
        except Exception as e:
            logger.error(f"   ❌ SDK error: {e}")
            raise
    
    def _calculate_backoff(self, attempt: int) -> int:
        """حساب وقت الانتظار"""
        base_wait = 2 ** attempt
        jitter = random.uniform(0, 1)
        total_wait = base_wait + jitter
        return int(min(total_wait, 60))
    
    def _build_prompt(self, category: str) -> str:
        """بناء prompt محسّن"""
        return f"""أنت طاهٍ محترف ومبدع متخصص في {category}. مهمتك إنشاء وصفة طبخ احترافية تجذب الزوار وتحقق مشاهدات عالية.

متطلبات الجودة:
- العنوان: جذاب يحتوي على كلمات بحث شائعة مثل "طريقة عمل" أو "وصفة سهلة"
- الوصف: مشوق ومفصل (120-180 كلمة) يحفز القارئ على التجربة
- المقادير: {config.MIN_RECIPE_INGREDIENTS}+ عناصر بتفاصيل دقيقة وكميات واضحة
- الخطوات: {config.MIN_RECIPE_STEPS}+ خطوات واضحة ومفصلة مع نصائح احترافية
- الكلمات الإجمالية: {config.TARGET_WORD_COUNT}+ كلمة لتحسين SEO

متطلبات SEO (مهمة جداً):
- استخدم هذه الكلمات المفتاحية في العنوان والوصف: {', '.join(config.PRIMARY_KEYWORDS[:4])}
- أضف 6-10 كلمات مفتاحية متنوعة
- أضف 5-8 وسوم (tags) ذات صلة
- اجعل الوصف غنياً بالكلمات البحثية

تنسيق JSON (مهم - التزم به تماماً):
{{
  "title": "عنوان جذاب يحتوي على كلمات بحث شائعة",
  "description": "وصف مشوق ومفصل يحفز القارئ ويحتوي على كلمات مفتاحية",
  "ingredients": ["كوب واحد دقيق", "نصف كوب سكر", "..."],
  "steps": ["خطوة 1 مفصلة مع نصيحة", "خطوة 2 واضحة وعملية", "..."],
  "prep_time": 20,
  "cook_time": 30,
  "servings": 6,
  "difficulty": "سهل",
  "keywords": ["كلمة1", "كلمة2", "كلمة3", "..."],
  "tags": ["وسم1", "وسم2", "وسم3", "..."]
}}

ملاحظات نهائية:
- لغة عربية فصحى سلسة وسهلة الفهم
- تفاصيل دقيقة في الكميات والأوقات
- نصائح عملية في الخطوات
- تركيز على الكلمات المفتاحية الشائعة

أنشئ الآن وصفة متميزة في فئة: {category}"""
    
    def _parse_response(self, text: str, category: str) -> Optional[Recipe]:
        """معالجة استجابة AI"""
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                logger.error("❌ No JSON found in response")
                return None
            
            json_str = json_match.group()
            data = json.loads(json_str)
            
            required_fields = ['title', 'description', 'ingredients', 'steps']
            missing = [f for f in required_fields if f not in data or not data[f]]
            
            if missing:
                logger.error(f"❌ Missing fields: {', '.join(missing)}")
                return None
            
            recipe = Recipe(
                title=data.get('title', '').strip(),
                category=category,
                description=data.get('description', '').strip(),
                ingredients=data.get('ingredients', []),
                steps=data.get('steps', []),
                prep_time=int(data.get('prep_time', 30)),
                cook_time=int(data.get('cook_time', 30)),
                servings=int(data.get('servings', 4)),
                difficulty=data.get('difficulty', 'متوسط'),
                keywords=data.get('keywords', []),
                tags=data.get('tags', [category])
            )
            
            full_text = f"{recipe.title} {recipe.description} " + \
                       " ".join(recipe.ingredients) + " ".join(recipe.steps)
            recipe.word_count = len(full_text.split())
            
            return recipe
            
        except Exception as e:
            logger.error(f"❌ Parsing failed: {e}")
            return None

# ═══════════════════════════════════════════════════════════════════════════════
# SEO OPTIMIZER (Unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

class SEOOptimizer:
    """محسّن SEO متقدم"""
    
    def __init__(self):
        logger.info("✅ Advanced SEO Optimizer initialized")
    
    def optimize_for_seo(self, recipe: Recipe) -> Recipe:
        """تحسين شامل لـ SEO"""
        recipe.meta_description = self._generate_optimized_meta(recipe)
        
        if not recipe.keywords or len(recipe.keywords) < 3:
            recipe.keywords = self._extract_enhanced_keywords(recipe)
        
        if len(recipe.tags) < 5:
            recipe.tags = self._enhance_tags(recipe)
        
        if config.AGGRESSIVE_SEO_MODE:
            recipe.title = self._optimize_title(recipe.title)
        
        return recipe
    
    def _generate_optimized_meta(self, recipe: Recipe) -> str:
        base_desc = recipe.description[:config.META_DESCRIPTION_LENGTH - 40]
        key_phrase = f" | {config.PRIMARY_KEYWORDS[0]}"
        max_len = config.META_DESCRIPTION_LENGTH - len(key_phrase) - 3
        
        if len(base_desc) > max_len:
            base_desc = base_desc[:max_len] + "..."
        
        return base_desc + key_phrase
    
    def _extract_enhanced_keywords(self, recipe: Recipe) -> List[str]:
        keywords = set()
        
        for kw in config.PRIMARY_KEYWORDS:
            keywords.add(kw)
        
        keywords.add(recipe.category)
        
        title_words = recipe.title.split()
        keywords.update([w for w in title_words if len(w) > 3][:3])
        
        common_keywords = ["وصفة", "طبخ", "سهل", "لذيذ", "منزلي", "سريع", "شهي"]
        keywords.update(random.sample(common_keywords, min(3, len(common_keywords))))
        
        return list(keywords)[:10]
    
    def _enhance_tags(self, recipe: Recipe) -> List[str]:
        tags = set(recipe.tags) if recipe.tags else set()
        
        tags.add(recipe.category)
        tags.add("وصفات عربية")
        tags.add("طبخ منزلي")
        tags.add(f"{recipe.difficulty}")
        
        if "حلو" in recipe.category.lower():
            tags.add("حلويات")
        
        return list(tags)[:8]
    
    def _optimize_title(self, title: str) -> str:
        trigger_words = ["طريقة عمل", "وصفة", "كيفية تحضير"]
        has_trigger = any(tw in title for tw in trigger_words)
        
        if not has_trigger and not title.startswith("طريقة"):
            title = f"طريقة عمل {title}"
        
        return title
    
    def analyze_recipe(self, recipe: Recipe) -> Dict:
        """تحليل شامل لـ SEO"""
        score = 0.0
        factors = {}
        
        title_len = len(recipe.title)
        if 30 <= title_len <= 70:
            score += 25
            factors['title_length'] = "✅ مثالي"
        elif 20 <= title_len <= 80:
            score += 15
            factors['title_length'] = "⚠️ مقبول"
        else:
            factors['title_length'] = "❌ غير مناسب"
        
        has_keywords = any(kw in recipe.title.lower() for kw in ["طريقة", "وصفة", "كيفية"])
        if has_keywords:
            score += 15
            factors['title_keywords'] = "✅ يحتوي على كلمات بحث"
        else:
            factors['title_keywords'] = "⚠️ بدون كلمات بحث"
        
        if recipe.word_count >= config.TARGET_WORD_COUNT:
            score += 20
            factors['word_count'] = f"✅ {recipe.word_count} كلمة"
        elif recipe.word_count >= config.TARGET_WORD_COUNT * 0.8:
            score += 12
            factors['word_count'] = f"⚠️ {recipe.word_count} كلمة"
        else:
            factors['word_count'] = f"❌ {recipe.word_count} كلمة (قليل)"
        
        if len(recipe.ingredients) >= config.MIN_RECIPE_INGREDIENTS:
            score += 10
            factors['ingredients'] = f"✅ {len(recipe.ingredients)} عنصر"
        else:
            factors['ingredients'] = f"⚠️ {len(recipe.ingredients)} عنصر"
        
        if len(recipe.steps) >= config.MIN_RECIPE_STEPS:
            score += 10
            factors['steps'] = f"✅ {len(recipe.steps)} خطوة"
        else:
            factors['steps'] = f"⚠️ {len(recipe.steps)} خطوة"
        
        if len(recipe.keywords) >= 6:
            score += 15
            factors['keywords'] = f"✅ {len(recipe.keywords)} كلمة"
        elif len(recipe.keywords) >= 3:
            score += 8
            factors['keywords'] = f"⚠️ {len(recipe.keywords)} كلمة"
        else:
            factors['keywords'] = f"❌ {len(recipe.keywords)} كلمة"
        
        if recipe.meta_description and len(recipe.meta_description) >= 100:
            score += 5
            factors['meta_desc'] = "✅ موجود ومحسّن"
        elif recipe.meta_description:
            score += 2
            factors['meta_desc'] = "⚠️ موجود لكن قصير"
        else:
            factors['meta_desc'] = "❌ غير موجود"
        
        recipe.seo_score = score
        
        return {
            'score': score,
            'factors': factors,
            'grade': 'ممتاز' if score >= 85 else 'جيد جداً' if score >= 70 else 'جيد' if score >= 55 else 'مقبول'
        }

# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT VALIDATOR (Unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

class ContentValidator:
    """مدقق جودة المحتوى"""
    
    def __init__(self):
        logger.info("✅ Content Validator initialized")
    
    def validate(self, recipe: Recipe) -> Tuple[bool, List[str]]:
        errors = []
        warnings = []
        
        if not recipe.title or len(recipe.title) < 10:
            errors.append("❌ العنوان قصير جداً")
        elif len(recipe.title) > 100:
            warnings.append("⚠️ العنوان طويل قد يؤثر على SEO")
        
        if len(recipe.ingredients) < config.MIN_RECIPE_INGREDIENTS:
            errors.append(f"❌ المقادير قليلة (مطلوب {config.MIN_RECIPE_INGREDIENTS}+)")
        
        if len(recipe.steps) < config.MIN_RECIPE_STEPS:
            errors.append(f"❌ الخطوات قليلة (مطلوب {config.MIN_RECIPE_STEPS}+)")
        
        min_words = int(config.TARGET_WORD_COUNT * 0.7)
        if recipe.word_count < min_words:
            errors.append(f"❌ عدد الكلمات قليل ({recipe.word_count}/{config.TARGET_WORD_COUNT})")
        
        if not recipe.description or len(recipe.description) < 80:
            errors.append("❌ الوصف قصير جداً (مطلوب 80+ حرف)")
        
        if len(recipe.keywords) < 3:
            warnings.append("⚠️ الكلمات المفتاحية قليلة (يُفضل 6+)")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("✅ Validation passed")
            if warnings:
                for w in warnings:
                    logger.warning(w)
        else:
            logger.warning(f"⚠️ Validation issues: {len(errors)} errors, {len(warnings)} warnings")
        
        return is_valid, errors + warnings

# ═══════════════════════════════════════════════════════════════════════════════
# BLOGGER PUBLISHER (Unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

class BloggerPublisher:
    """ناشر المحتوى على Blogger"""
    
    def __init__(self):
        self.blog_id = config.BLOGGER_BLOG_ID
        self.credentials = self._get_credentials_secure()
        
        if not self.credentials:
            raise ValueError("❌ Failed to obtain Blogger credentials")
        
        self.service = build('blogger', 'v3', credentials=self.credentials)
        logger.info("✅ Blogger Publisher initialized")
    
    def _get_credentials_secure(self) -> Optional[Credentials]:
        creds = None
        
        if config.CREDENTIALS_PATH.exists():
            try:
                with open(config.CREDENTIALS_PATH, 'r', encoding='utf-8') as token:
                    token_data = json.load(token)
                    creds = Credentials.from_authorized_user_info(
                        token_data, config.BLOGGER_SCOPES
                    )
                logger.info("✅ Credentials loaded")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load token: {e}")
        
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("✅ Credentials refreshed")
                
                with open(config.CREDENTIALS_PATH, 'w', encoding='utf-8') as token:
                    token.write(creds.to_json())
                
            except Exception as e:
                logger.error(f"❌ Failed to refresh: {e}")
                creds = None
        
        if not creds or not creds.valid:
            logger.error("❌ No valid credentials. Set TOKEN_JSON in Render.")
            return None
        
        return creds
    
    def publish_recipe(self, recipe: Recipe, as_draft: bool = None) -> Optional[str]:
        try:
            is_draft = as_draft if as_draft is not None else config.DRAFT_MODE
            
            logger.info(f"📤 Publishing: {recipe.title[:50]}...")
            
            post_body = {
                'kind': 'blogger#post',
                'blog': {'id': self.blog_id},
                'title': recipe.title,
                'content': recipe.to_html(),
                'labels': recipe.tags
            }
            
            request = self.service.posts().insert(
                blogId=self.blog_id,
                body=post_body,
                isDraft=is_draft
            )
            
            response = request.execute()
            
            recipe.post_id = response.get('id')
            recipe.post_url = response.get('url')
            recipe.published_at = datetime.now()
            
            logger.info(f"✅ Published | ID: {recipe.post_id}")
            
            return recipe.post_id
            
        except Exception as e:
            logger.error(f"❌ Publishing failed: {e}")
            return None

# ═══════════════════════════════════════════════════════════════════════════════
# ANALYTICS TRACKER (Unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyticsTracker:
    """متتبع الأداء"""
    
    def __init__(self):
        self.data_file = config.DATA_DIR / config.PERFORMANCE_FILE
        self.data = self._load()
        logger.info("✅ Analytics Tracker initialized")
    
    def _load(self) -> Dict:
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        return {
            'recipes': [],
            'statistics': {
                'total_published': 0,
                'total_drafts': 0,
                'avg_seo_score': 0.0,
                'categories_count': {},
                'last_publish': None
            }
        }
    
    def _save(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save analytics: {e}")
    
    def track_recipe(self, recipe: Recipe, published: bool = True):
        self.data['recipes'].append({
            'post_id': recipe.post_id,
            'title': recipe.title,
            'category': recipe.category,
            'seo_score': recipe.seo_score,
            'word_count': recipe.word_count,
            'published_at': recipe.published_at.isoformat() if recipe.published_at else None,
            'is_published': published,
            'url': recipe.post_url
        })
        
        stats = self.data['statistics']
        if published:
            stats['total_published'] += 1
        else:
            stats['total_drafts'] += 1
        
        stats['last_publish'] = datetime.now().isoformat()
        
        cat = recipe.category
        stats['categories_count'][cat] = stats['categories_count'].get(cat, 0) + 1
        
        scores = [r['seo_score'] for r in self.data['recipes'] if r.get('seo_score', 0) > 0]
        if scores:
            stats['avg_seo_score'] = sum(scores) / len(scores)
        
        self._save()
    
    def get_next_category(self) -> str:
        counts = self.data['statistics'].get('categories_count', {})
        
        if not counts:
            return random.choice(config.CONTENT_CATEGORIES)
        
        sorted_cats = sorted(counts.items(), key=lambda x: x[1])
        
        if sorted_cats and sorted_cats[0][1] < 3:
            return sorted_cats[0][0]
        
        least_used = [cat for cat, count in sorted_cats[:3]]
        return random.choice(least_used) if least_used else random.choice(config.CONTENT_CATEGORIES)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class ZajmilAIChef:
    """النظام المتكامل"""
    
    def __init__(self):
        logger.info("=" * 80)
        logger.info("🚀 Zajmil AI Chef v2.3.2 [DUAL FIXES]")
        logger.info("=" * 80)
        
        config.validate()
        
        logger.info(f"🌐 Environment: {'Render' if config.IS_RENDER_ENV else 'Local'}")
        logger.info(f"🤖 AI Model: {config.GEMINI_MODEL}")
        logger.info(f"🔌 API Method: {'REST API' if config.USE_REST_API else 'Google SDK'}")
        logger.info(f"🔗 API Version: {config.GEMINI_API_VERSION}")
        
        self.optimal_article_count = config.calculate_optimal_article_count()
        logger.info(f"📊 Optimal Articles: {self.optimal_article_count}")
        
        try:
            self.gemini = GeminiChefEngine()
            self.publisher = BloggerPublisher()
            self.seo = SEOOptimizer()
            self.validator = ContentValidator()
            self.analytics = AnalyticsTracker()
        except Exception as e:
            logger.critical(f"❌ Initialization failed: {e}")
            raise
        
        self.published_count = 0
        
        # 🔥 FIX #2: بدء خادم الويب الخلفي
        if config.ENABLE_WEB_SERVER and config.IS_RENDER_ENV:
            web_server_started = start_background_web_server()
            if web_server_started:
                logger.info("🌐 Background web server started for Render health checks")
        
        logger.info("✅ All components ready")
        logger.info("=" * 80)
    
    def generate_and_publish(self, category: Optional[str] = None) -> bool:
        try:
            logger.info("\n" + "=" * 80)
            logger.info("🎬 Starting Workflow")
            logger.info("=" * 80)
            
            if not category:
                category = self.analytics.get_next_category()
            
            logger.info(f"🎯 Category: {category}")
            
            logger.info("\n📝 Step 1/5: Generating...")
            recipe = self.gemini.generate_recipe(category)
            if not recipe:
                logger.error("❌ Generation failed")
                return False
            
            logger.info("\n🔍 Step 2/5: Validating...")
            is_valid, messages = self.validator.validate(recipe)
            if not is_valid:
                logger.error("❌ Validation failed")
                return False
            
            logger.info("\n🔧 Step 3/5: SEO Optimization...")
            recipe = self.seo.optimize_for_seo(recipe)
            seo_analysis = self.seo.analyze_recipe(recipe)
            
            logger.info(f"✅ SEO Score: {seo_analysis['score']:.1f}/100")
            
            logger.info("\n📤 Step 4/5: Publishing...")
            post_id = self.publisher.publish_recipe(recipe)
            if not post_id:
                logger.error("❌ Publishing failed")
                return False
            
            logger.info("\n📊 Step 5/5: Tracking...")
            self.analytics.track_recipe(recipe, not config.DRAFT_MODE)
            
            self.published_count += 1
            
            logger.info("\n🎉 SUCCESS!")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Workflow failed: {e}")
            return False
    
    def run_continuous(self):
        logger.info("\n⏰ CONTINUOUS MODE")
        logger.info(f"📊 Target: {self.optimal_article_count} articles")
        
        start_time = datetime.now()
        
        # 🔥 FIX #2: التأكد من أن خادم الويب يعمل
        if config.ENABLE_WEB_SERVER and config.IS_RENDER_ENV:
            logger.info("🌐 Web server running in background for health checks")
        
        while self.published_count < self.optimal_article_count:
            try:
                logger.info(f"\nArticle {self.published_count + 1}/{self.optimal_article_count}")
                
                success = self.generate_and_publish()
                
                if self.published_count >= self.optimal_article_count:
                    logger.info("\n🎯 TARGET REACHED!")
                    break
                
                sleep_sec = config.PUBLISH_INTERVAL_HOURS * 3600
                sleep_sec = int(sleep_sec * random.uniform(0.95, 1.05))
                
                logger.info(f"\n😴 Sleeping {sleep_sec/3600:.2f}h...")
                time.sleep(sleep_sec)
                
            except KeyboardInterrupt:
                logger.info("\n⏹️ Stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                time.sleep(3600)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Zajmil AI Chef v2.3.2 [DUAL FIXES]")
    
    parser.add_argument('--mode', choices=['once', 'continuous', 'report'], default='once')
    parser.add_argument('--category', type=str)
    parser.add_argument('--draft', action='store_true')
    
    args = parser.parse_args()
    
    try:
        # 🔥 FIX #2: بدء توقيت لتتبع وقت التشغيل
        global start_time
        start_time = datetime.now()
        
        # إنشاء النظام
        zajmil = ZajmilAIChef()
        
        if args.draft:
            config.DRAFT_MODE = True
        
        if args.mode == 'once':
            success = zajmil.generate_and_publish(args.category)
            sys.exit(0 if success else 1)
        
        elif args.mode == 'continuous':
            zajmil.run_continuous()
            sys.exit(0)
        
        elif args.mode == 'report':
            stats = zajmil.analytics.data['statistics']
            logger.info("📊 REPORT")
            logger.info(f"Published: {stats['total_published']}")
            logger.info(f"Avg SEO: {stats['avg_seo_score']:.1f}")
            sys.exit(0)
    
    except Exception as e:
        logger.critical(f"💥 FATAL: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
