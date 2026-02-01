#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
ZAJMIL AI CHEF - Complete Integrated System v2.0.0 [RENDER PRODUCTION READY]
═══════════════════════════════════════════════════════════════════════════════
نظام متكامل لتوليد ونشر وصفات الطبخ باستخدام الذكاء الاصطناعي

المميزات المحسّنة v2.0:
✅ مصادقة ديناميكية 100% من متغيرات Render البيئية
✅ لا حاجة لرفع ملفات token.json أو client_secret.json
✅ نموذج Gemini Flash السريع (تقليل Timeout)
✅ مسارات ديناميكية متوافقة مع Render
✅ تحسينات SEO متقدمة لجلب مشاهدات سريعة
✅ حساب ديناميكي لعدد المقالات حسب أقصر مدة لجلب المشاهدات

الاستخدام:
  python main.py --mode once              # نشر وصفة واحدة
  python main.py --mode continuous        # نشر مستمر
  python main.py --mode report            # تقرير الأداء
  
متغيرات Render المطلوبة:
  - GEMINI_API_KEY
  - BLOGGER_BLOG_ID
  - TOKEN_JSON (محتوى ملف token.json كنص JSON)
  - CLIENT_SECRET_JSON (محتوى ملف client_secret.json كنص JSON)
  
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
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from logging.handlers import RotatingFileHandler
from xml.etree import ElementTree as ET

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS - Google APIs & AI
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("❌ ERROR: google-generativeai not installed")
    print("   Install: pip install google-generativeai")
    sys.exit(1)

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
# RENDER ENVIRONMENT SETUP - CRITICAL FOR CLOUD DEPLOYMENT
# ═══════════════════════════════════════════════════════════════════════════════

def setup_render_environment():
    """
    إعداد البيئة الديناميكية لـ Render
    
    يقوم بـ:
    1. قراءة TOKEN_JSON و CLIENT_SECRET_JSON من متغيرات البيئة
    2. كتابتها كملفات مؤقتة في المسار المناسب
    3. التحقق من صحة البيانات
    
    Returns:
        Tuple[Path, Path]: مسارات token.json و client_secret.json
    """
    print("\n" + "=" * 80)
    print("🔧 RENDER ENVIRONMENT SETUP")
    print("=" * 80)
    
    # تحديد المسار الأساسي (Render يستخدم /tmp للكتابة المؤقتة)
    is_render = os.getenv("RENDER", "false").lower() == "true"
    base_path = Path("/tmp") if is_render else Path(__file__).resolve().parent
    
    print(f"📁 Base Path: {base_path}")
    print(f"🌐 Render Mode: {is_render}")
    
    # إنشاء مجلد data إذا لم يكن موجوداً
    data_dir = base_path / "data"
    data_dir.mkdir(exist_ok=True, parents=True)
    print(f"✅ Data directory created: {data_dir}")
    
    # ═══ معالجة TOKEN_JSON ═══
    token_path = base_path / "token.json"
    token_json_env = os.getenv("TOKEN_JSON", "")
    
    if token_json_env:
        try:
            # التحقق من صحة JSON قبل الكتابة
            token_data = json.loads(token_json_env)
            
            with open(token_path, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, indent=2)
            
            print(f"✅ Token file created from environment: {token_path}")
        except json.JSONDecodeError as e:
            print(f"⚠️ WARNING: Invalid TOKEN_JSON format: {e}")
            print("   Authentication may fail. Ensure TOKEN_JSON is valid JSON.")
    else:
        if not token_path.exists():
            print("⚠️ WARNING: TOKEN_JSON not found in environment variables")
            print("   File will be created after first OAuth flow")
    
    # ═══ معالجة CLIENT_SECRET_JSON ═══
    client_secret_path = base_path / "client_secret.json"
    client_secret_env = os.getenv("CLIENT_SECRET_JSON", "")
    
    if client_secret_env:
        try:
            # التحقق من صحة JSON قبل الكتابة
            client_data = json.loads(client_secret_env)
            
            with open(client_secret_path, 'w', encoding='utf-8') as f:
                json.dump(client_data, f, indent=2)
            
            print(f"✅ Client secret file created from environment: {client_secret_path}")
        except json.JSONDecodeError as e:
            print(f"⚠️ WARNING: Invalid CLIENT_SECRET_JSON format: {e}")
    else:
        print("ℹ️ INFO: CLIENT_SECRET_JSON not provided (will use CLIENT_ID/SECRET directly)")
    
    print("=" * 80 + "\n")
    
    return token_path, client_secret_path, base_path

# تنفيذ الإعداد فوراً عند بدء البرنامج
TOKEN_PATH, CLIENT_SECRET_PATH, BASE_PATH = setup_render_environment()

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION WITH FULL RENDER SUPPORT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    """إعدادات النظام الشاملة مع دعم كامل لـ Render"""
    
    # Gemini AI - استخدام Flash كنموذج افتراضي للسرعة
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")  # ⚡ FLASH بدلاً من PRO
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.9"))
    GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "8000"))
    
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
    
    # SEO - تحسينات متقدمة لجلب مشاهدات سريعة
    PRIMARY_KEYWORDS: List[str] = field(default_factory=lambda: 
        json.loads(os.getenv("PRIMARY_KEYWORDS", json.dumps([
            "وصفات طبخ", "حلويات سهلة", "طريقة عمل", "وصفات منزلية",
            "حلويات لذيذة", "مطبخ عربي", "وصفات سريعة", "أطباق شهية"
        ])))
    )
    
    META_DESCRIPTION_LENGTH: int = int(os.getenv("META_DESCRIPTION_LENGTH", "160"))
    ENABLE_SCHEMA_MARKUP: bool = os.getenv("ENABLE_SCHEMA_MARKUP", "true").lower() == "true"
    
    # تحسينات SEO لجلب مشاهدات أسرع
    ENABLE_RICH_SNIPPETS: bool = os.getenv("ENABLE_RICH_SNIPPETS", "true").lower() == "true"
    ENABLE_SOCIAL_META_TAGS: bool = os.getenv("ENABLE_SOCIAL_META_TAGS", "true").lower() == "true"
    AGGRESSIVE_SEO_MODE: bool = os.getenv("AGGRESSIVE_SEO_MODE", "true").lower() == "true"
    
    # Publishing Strategy
    PUBLISH_INTERVAL_HOURS: int = int(os.getenv("PUBLISH_INTERVAL_HOURS", "24"))
    AUTO_PUBLISH: bool = os.getenv("AUTO_PUBLISH", "true").lower() == "true"
    DRAFT_MODE: bool = os.getenv("DRAFT_MODE", "false").lower() == "true"
    
    # Dynamic Article Count Calculation
    MIN_VIEWS_FETCH_HOURS: int = int(os.getenv("MIN_VIEWS_FETCH_HOURS", "48"))
    ARTICLE_SAFETY_FACTOR: float = float(os.getenv("ARTICLE_SAFETY_FACTOR", "0.8"))
    MAX_ARTICLES_LIMIT: int = int(os.getenv("MAX_ARTICLES_LIMIT", "100"))
    MIN_ARTICLES_LIMIT: int = int(os.getenv("MIN_ARTICLES_LIMIT", "1"))
    ENABLE_DYNAMIC_ARTICLE_COUNT: bool = os.getenv("ENABLE_DYNAMIC_ARTICLE_COUNT", "true").lower() == "true"
    FIXED_ARTICLE_COUNT: int = int(os.getenv("FIXED_ARTICLE_COUNT", "50"))
    
    # Render Specific Settings
    RENDER_INSTANCE_ID: str = os.getenv("RENDER_INSTANCE_ID", "")
    RENDER_SERVICE_NAME: str = os.getenv("RENDER_SERVICE_NAME", "")
    RENDER_GIT_COMMIT: str = os.getenv("RENDER_GIT_COMMIT", "")
    IS_RENDER_ENV: bool = os.getenv("RENDER", "false").lower() == "true"
    
    # Paths - استخدام المسارات الديناميكية من setup_render_environment
    BASE_DIR: Path = BASE_PATH
    CREDENTIALS_PATH: Path = TOKEN_PATH
    CLIENT_SECRET_FILE: Path = CLIENT_SECRET_PATH
    DATA_DIR: Path = field(init=False)
    LOG_FILE: str = os.getenv("LOG_FILE", "zajmil.log")
    PERFORMANCE_FILE: str = os.getenv("PERFORMANCE_FILE", "performance.json")
    
    def __post_init__(self):
        self.DATA_DIR = self.BASE_DIR / "data"
        self.DATA_DIR.mkdir(exist_ok=True, parents=True)
    
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
        
        # التحقق من تسمية النموذج
        if not self.GEMINI_MODEL:
            errors.append("❌ GEMINI_MODEL is required")
        else:
            # التحقق من صحة اسم النموذج
            valid_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro', 'gemini-flash']
            model_base = self.GEMINI_MODEL.replace('models/', '').strip()
            
            if model_base not in valid_models:
                errors.append(f"⚠️ WARNING: Model '{model_base}' may not be supported")
                errors.append(f"   Valid models: {', '.join(valid_models)}")
        
        if not self.BLOGGER_BLOG_ID:
            errors.append("❌ BLOGGER_BLOG_ID is required")
        
        # التحقق من بيانات المصادقة
        has_token = self.CREDENTIALS_PATH.exists() or os.getenv("TOKEN_JSON")
        has_client_creds = (self.BLOGGER_CLIENT_ID and self.BLOGGER_CLIENT_SECRET) or \
                          self.CLIENT_SECRET_FILE.exists() or os.getenv("CLIENT_SECRET_JSON")
        
        if not has_token and not has_client_creds:
            errors.append("❌ Authentication credentials missing")
            errors.append("   Provide either: TOKEN_JSON or (BLOGGER_CLIENT_ID + BLOGGER_CLIENT_SECRET)")
        
        if self.MIN_VIEWS_FETCH_HOURS < self.PUBLISH_INTERVAL_HOURS:
            errors.append("❌ MIN_VIEWS_FETCH_HOURS must be >= PUBLISH_INTERVAL_HOURS")
        
        if self.ARTICLE_SAFETY_FACTOR <= 0 or self.ARTICLE_SAFETY_FACTOR > 2:
            errors.append("❌ ARTICLE_SAFETY_FACTOR must be between 0 and 2")
        
        if errors:
            for error in errors:
                print(error)
            raise ValueError("Configuration validation failed")
        
        return True

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
    """نموذج الوصفة مع تحسينات SEO متقدمة"""
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
        
        # حساب الوقت الإجمالي
        total_time = self.prep_time + self.cook_time
        
        # بناء Schema.org Markup للظهور في Rich Snippets
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
        
        # Social Meta Tags للمشاركة الاجتماعية
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
        
        # بناء HTML الأساسي
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

/* Responsive Design */
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
# GEMINI AI ENGINE - OPTIMIZED FOR FLASH MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiChefEngine:
    """محرك توليد الوصفات بواسطة Gemini AI - محسّن للسرعة والاستقرار"""
    
    def __init__(self):
        # ═══ التهيئة المبسطة والموثوقة ═══
        
        # الخطوة 1: تكوين API الأساسي مع transport='rest' للاستقرار
        genai.configure(api_key=config.GEMINI_API_KEY, transport='rest')
        
        logger.info("🔧 Gemini API configured with REST transport (Render-compatible)")
        
        # الخطوة 2: توحيد تسمية النموذج
        model_name = self._normalize_model_name(config.GEMINI_MODEL)
        logger.info(f"📝 Normalized model name: {model_name}")
        
        # الخطوة 3: إنشاء النموذج مع الإعدادات المحسّنة
        try:
            self.model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": config.GEMINI_TEMPERATURE,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": config.GEMINI_MAX_TOKENS,
                }
            )
            logger.info(f"✅ Gemini AI Engine initialized successfully")
            logger.info(f"   • Model: {model_name}")
            logger.info(f"   • API Version: Auto-detected by Google AI library")
            logger.info(f"   • Transport: REST (stable for Render)")
            logger.info(f"   • Temperature: {config.GEMINI_TEMPERATURE}")
            logger.info(f"   • Max Tokens: {config.GEMINI_MAX_TOKENS}")
            
            # الخطوة 4: اختبار الاتصال
            self._test_connection()
            
        except Exception as e:
            logger.critical(f"❌ Failed to initialize Gemini model: {e}")
            raise
    
    def _normalize_model_name(self, model_name: str) -> str:
        """
        توحيد تسمية النموذج بإضافة 'models/' إذا لم تكن موجودة
        
        Args:
            model_name: اسم النموذج من الإعدادات
            
        Returns:
            str: اسم النموذج الموحد
            
        Examples:
            'gemini-1.5-flash' -> 'models/gemini-1.5-flash'
            'models/gemini-1.5-flash' -> 'models/gemini-1.5-flash'
            'gemini-1.5-pro' -> 'models/gemini-1.5-pro'
        """
        # إزالة أي مسافات
        model_name = model_name.strip()
        
        # التحقق إذا كانت البادئة موجودة بالفعل
        if model_name.startswith('models/'):
            return model_name
        
        # إضافة البادئة
        normalized = f"models/{model_name}"
        
        logger.debug(f"Model name normalized: '{model_name}' -> '{normalized}'")
        
        return normalized
    
    def _test_connection(self):
        """
        اختبار الاتصال بـ Gemini API
        
        يرسل طلب بسيط للتحقق من:
        - صحة API Key
        - توفر النموذج
        - سلامة الاتصال
        """
        try:
            logger.info("🔍 Testing Gemini API connection...")
            
            test_response = self.model.generate_content(
                "اكتب 'مرحبا' فقط",
                request_options={'timeout': 30}
            )
            
            if test_response and test_response.text:
                logger.info("✅ Gemini API connection test successful")
                logger.debug(f"   Test response: {test_response.text[:50]}...")
            else:
                logger.warning("⚠️ API responded but with empty content")
                
        except Exception as e:
            logger.error(f"❌ API connection test failed: {e}")
            logger.warning("⚠️ Will continue, but API may not be working correctly")
            logger.warning("   Check: API key, model name, network connectivity")
    
    def generate_recipe(self, category: str, max_retries: int = 3) -> Optional[Recipe]:
        """
        توليد وصفة مع آلية إعادة المحاولة
        
        Args:
            category: فئة الوصفة
            max_retries: عدد المحاولات القصوى
            
        Returns:
            Recipe أو None
        """
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🤖 Generating recipe for: {category} (Attempt {attempt}/{max_retries})")
                
                prompt = self._build_enhanced_prompt(category)
                
                # استدعاء API مع timeout محدد
                response = self.model.generate_content(
                    prompt,
                    request_options={'timeout': 60}  # 60 ثانية timeout
                )
                
                if not response or not response.text:
                    logger.error(f"❌ Empty response from Gemini (Attempt {attempt})")
                    if attempt < max_retries:
                        logger.info(f"⏳ Retrying in 5 seconds...")
                        time.sleep(5)
                        continue
                    return None
                
                recipe = self._parse_response(response.text, category)
                
                if recipe:
                    logger.info(f"✅ Generated successfully: {recipe.title}")
                    return recipe
                else:
                    logger.warning(f"⚠️ Parsing failed (Attempt {attempt})")
                    if attempt < max_retries:
                        logger.info(f"⏳ Retrying with modified prompt...")
                        time.sleep(3)
                        continue
                
            except Exception as e:
                logger.error(f"❌ Generation failed (Attempt {attempt}/{max_retries}): {e}")
                
                if attempt < max_retries:
                    logger.info(f"⏳ Retrying in 10 seconds...")
                    time.sleep(10)
                else:
                    logger.error(f"💥 All {max_retries} attempts failed")
                    return None
        
        return None
    
    def _build_enhanced_prompt(self, category: str) -> str:
        """بناء prompt محسّن لجودة أعلى وسرعة أفضل"""
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
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                logger.error("❌ No JSON found in response")
                return None
            
            data = json.loads(json_match.group())
            
            recipe = Recipe(
                title=data.get('title', ''),
                category=category,
                description=data.get('description', ''),
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
# ADVANCED SEO OPTIMIZER - FOR FAST TRAFFIC
# ═══════════════════════════════════════════════════════════════════════════════

class SEOOptimizer:
    """محسّن SEO متقدم لجلب مشاهدات سريعة"""
    
    def __init__(self):
        logger.info("✅ Advanced SEO Optimizer initialized")
    
    def optimize_for_seo(self, recipe: Recipe) -> Recipe:
        """تحسين شامل لـ SEO"""
        
        # توليد meta description محسّنة
        recipe.meta_description = self._generate_optimized_meta(recipe)
        
        # تعزيز الكلمات المفتاحية
        if not recipe.keywords or len(recipe.keywords) < 3:
            recipe.keywords = self._extract_enhanced_keywords(recipe)
        
        # إضافة tags إضافية إذا كانت قليلة
        if len(recipe.tags) < 5:
            recipe.tags = self._enhance_tags(recipe)
        
        # إضافة كلمات مفتاحية في العنوان إذا لم تكن موجودة
        if config.AGGRESSIVE_SEO_MODE:
            recipe.title = self._optimize_title(recipe.title)
        
        return recipe
    
    def _generate_optimized_meta(self, recipe: Recipe) -> str:
        """توليد meta description محسّنة مع كلمات مفتاحية"""
        base_desc = recipe.description[:config.META_DESCRIPTION_LENGTH - 40]
        
        # إضافة كلمة مفتاحية في النهاية
        key_phrase = f" | {config.PRIMARY_KEYWORDS[0]}"
        max_len = config.META_DESCRIPTION_LENGTH - len(key_phrase) - 3
        
        if len(base_desc) > max_len:
            base_desc = base_desc[:max_len] + "..."
        
        return base_desc + key_phrase
    
    def _extract_enhanced_keywords(self, recipe: Recipe) -> List[str]:
        """استخراج كلمات مفتاحية محسّنة"""
        keywords = set()
        
        # إضافة الكلمات الأساسية
        for kw in config.PRIMARY_KEYWORDS:
            keywords.add(kw)
        
        # إضافة الفئة
        keywords.add(recipe.category)
        
        # إضافة كلمات من العنوان
        title_words = recipe.title.split()
        keywords.update([w for w in title_words if len(w) > 3][:3])
        
        # إضافة كلمات شائعة في الطبخ
        common_keywords = ["وصفة", "طبخ", "سهل", "لذيذ", "منزلي", "سريع", "شهي"]
        keywords.update(random.sample(common_keywords, min(3, len(common_keywords))))
        
        return list(keywords)[:10]
    
    def _enhance_tags(self, recipe: Recipe) -> List[str]:
        """تعزيز الوسوم (tags)"""
        tags = set(recipe.tags) if recipe.tags else set()
        
        tags.add(recipe.category)
        tags.add("وصفات عربية")
        tags.add("طبخ منزلي")
        
        # إضافة مستوى الصعوبة
        tags.add(f"{recipe.difficulty}")
        
        # إضافة نوع الوجبة
        if "حلو" in recipe.category.lower():
            tags.add("حلويات")
        
        return list(tags)[:8]
    
    def _optimize_title(self, title: str) -> str:
        """تحسين العنوان بإضافة كلمات مفتاحية إذا لم تكن موجودة"""
        trigger_words = ["طريقة عمل", "وصفة", "كيفية تحضير"]
        
        # التحقق إذا كان العنوان يحتوي على كلمة محفزة
        has_trigger = any(tw in title for tw in trigger_words)
        
        if not has_trigger and not title.startswith("طريقة"):
            title = f"طريقة عمل {title}"
        
        return title
    
    def analyze_recipe(self, recipe: Recipe) -> Dict:
        """تحليل شامل لـ SEO"""
        score = 0.0
        factors = {}
        
        # تحليل العنوان (25 نقطة)
        title_len = len(recipe.title)
        if 30 <= title_len <= 70:
            score += 25
            factors['title_length'] = "✅ مثالي"
        elif 20 <= title_len <= 80:
            score += 15
            factors['title_length'] = "⚠️ مقبول"
        else:
            factors['title_length'] = "❌ غير مناسب"
        
        # فحص وجود كلمات مفتاحية في العنوان (15 نقطة)
        has_keywords = any(kw in recipe.title.lower() for kw in ["طريقة", "وصفة", "كيفية"])
        if has_keywords:
            score += 15
            factors['title_keywords'] = "✅ يحتوي على كلمات بحث"
        else:
            factors['title_keywords'] = "⚠️ بدون كلمات بحث"
        
        # عدد الكلمات (20 نقطة)
        if recipe.word_count >= config.TARGET_WORD_COUNT:
            score += 20
            factors['word_count'] = f"✅ {recipe.word_count} كلمة"
        elif recipe.word_count >= config.TARGET_WORD_COUNT * 0.8:
            score += 12
            factors['word_count'] = f"⚠️ {recipe.word_count} كلمة"
        else:
            factors['word_count'] = f"❌ {recipe.word_count} كلمة (قليل)"
        
        # المقادير (10 نقاط)
        if len(recipe.ingredients) >= config.MIN_RECIPE_INGREDIENTS:
            score += 10
            factors['ingredients'] = f"✅ {len(recipe.ingredients)} عنصر"
        else:
            factors['ingredients'] = f"⚠️ {len(recipe.ingredients)} عنصر"
        
        # الخطوات (10 نقاط)
        if len(recipe.steps) >= config.MIN_RECIPE_STEPS:
            score += 10
            factors['steps'] = f"✅ {len(recipe.steps)} خطوة"
        else:
            factors['steps'] = f"⚠️ {len(recipe.steps)} خطوة"
        
        # الكلمات المفتاحية (15 نقطة)
        if len(recipe.keywords) >= 6:
            score += 15
            factors['keywords'] = f"✅ {len(recipe.keywords)} كلمة"
        elif len(recipe.keywords) >= 3:
            score += 8
            factors['keywords'] = f"⚠️ {len(recipe.keywords)} كلمة"
        else:
            factors['keywords'] = f"❌ {len(recipe.keywords)} كلمة"
        
        # Meta Description (5 نقاط)
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
# CONTENT VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ContentValidator:
    """مدقق جودة المحتوى"""
    
    def __init__(self):
        logger.info("✅ Content Validator initialized")
    
    def validate(self, recipe: Recipe) -> Tuple[bool, List[str]]:
        errors = []
        warnings = []
        
        # التحقق من العنوان
        if not recipe.title or len(recipe.title) < 10:
            errors.append("❌ العنوان قصير جداً")
        elif len(recipe.title) > 100:
            warnings.append("⚠️ العنوان طويل قد يؤثر على SEO")
        
        # التحقق من المقادير
        if len(recipe.ingredients) < config.MIN_RECIPE_INGREDIENTS:
            errors.append(f"❌ المقادير قليلة (مطلوب {config.MIN_RECIPE_INGREDIENTS}+)")
        
        # التحقق من الخطوات
        if len(recipe.steps) < config.MIN_RECIPE_STEPS:
            errors.append(f"❌ الخطوات قليلة (مطلوب {config.MIN_RECIPE_STEPS}+)")
        
        # التحقق من عدد الكلمات
        min_words = int(config.TARGET_WORD_COUNT * 0.7)
        if recipe.word_count < min_words:
            errors.append(f"❌ عدد الكلمات قليل ({recipe.word_count}/{config.TARGET_WORD_COUNT})")
        
        # التحقق من الوصف
        if not recipe.description or len(recipe.description) < 80:
            errors.append("❌ الوصف قصير جداً (مطلوب 80+ حرف)")
        
        # التحقق من الكلمات المفتاحية
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
# BLOGGER PUBLISHER - RENDER COMPATIBLE
# ═══════════════════════════════════════════════════════════════════════════════

class BloggerPublisher:
    """ناشر المحتوى على Blogger - متوافق 100% مع Render"""
    
    def __init__(self):
        self.blog_id = config.BLOGGER_BLOG_ID
        self.credentials = self._get_credentials_secure()
        
        if not self.credentials:
            raise ValueError("❌ Failed to obtain Blogger credentials. Check TOKEN_JSON or OAuth settings.")
        
        self.service = build('blogger', 'v3', credentials=self.credentials)
        logger.info("✅ Blogger Publisher initialized (Render-compatible)")
    
    def _get_credentials_secure(self) -> Optional[Credentials]:
        """
        الحصول على بيانات الاعتماد بشكل آمن ومتوافق مع Render
        
        آلية العمل:
        1. محاولة تحميل من token.json (المُنشأ من TOKEN_JSON env var)
        2. إذا فشل، محاولة refresh باستخدام refresh_token
        3. عدم محاولة فتح متصفح أبداً (غير متاح على Render)
        
        Returns:
            Credentials أو None
        """
        creds = None
        
        # المحاولة 1: تحميل من ملف token.json
        if config.CREDENTIALS_PATH.exists():
            try:
                with open(config.CREDENTIALS_PATH, 'r', encoding='utf-8') as token:
                    token_data = json.load(token)
                    creds = Credentials.from_authorized_user_info(
                        token_data, config.BLOGGER_SCOPES
                    )
                logger.info("✅ Credentials loaded from token file")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load token file: {e}")
        
        # المحاولة 2: Refresh إذا كانت منتهية
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("✅ Credentials refreshed successfully")
                
                # حفظ التحديث
                with open(config.CREDENTIALS_PATH, 'w', encoding='utf-8') as token:
                    token.write(creds.to_json())
                
            except Exception as e:
                logger.error(f"❌ Failed to refresh credentials: {e}")
                creds = None
        
        # المحاولة 3: إذا لم تنجح الطرق السابقة - لا نحاول المتصفح
        if not creds or not creds.valid:
            logger.error("=" * 80)
            logger.error("❌ AUTHENTICATION FAILED")
            logger.error("=" * 80)
            logger.error("No valid credentials available.")
            logger.error("")
            logger.error("For Render deployment, you MUST provide TOKEN_JSON:")
            logger.error("1. Run authentication locally first to generate token.json")
            logger.error("2. Copy the entire content of token.json")
            logger.error("3. Set it as TOKEN_JSON environment variable in Render")
            logger.error("")
            logger.error("Example TOKEN_JSON format:")
            logger.error('{')
            logger.error('  "token": "ya29.xxx...",')
            logger.error('  "refresh_token": "1//xxx...",')
            logger.error('  "token_uri": "https://oauth2.googleapis.com/token",')
            logger.error('  "client_id": "xxx.apps.googleusercontent.com",')
            logger.error('  "client_secret": "xxx",')
            logger.error('  "scopes": ["https://www.googleapis.com/auth/blogger"]')
            logger.error('}')
            logger.error("=" * 80)
            
            return None
        
        self.credentials = creds
        return creds
    
    def publish_recipe(self, recipe: Recipe, as_draft: bool = None) -> Optional[str]:
        """نشر الوصفة على Blogger"""
        try:
            is_draft = as_draft if as_draft is not None else config.DRAFT_MODE
            
            logger.info(f"📤 Publishing: {recipe.title[:50]}... | Draft: {is_draft}")
            
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
            logger.info(f"🔗 URL: {recipe.post_url}")
            
            return recipe.post_id
            
        except HttpError as e:
            logger.error(f"❌ Blogger API error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Publishing failed: {e}")
            return None

# ═══════════════════════════════════════════════════════════════════════════════
# ANALYTICS TRACKER
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
            except Exception as e:
                logger.warning(f"⚠️ Failed to load analytics: {e}")
        
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
        logger.info("✅ Recipe tracked in analytics")
    
    def get_next_category(self) -> str:
        """اختيار الفئة التالية بناءً على التوزيع المتوازن"""
        counts = self.data['statistics'].get('categories_count', {})
        
        if not counts:
            return random.choice(config.CONTENT_CATEGORIES)
        
        # ترتيب الفئات حسب الأقل استخداماً
        sorted_cats = sorted(counts.items(), key=lambda x: x[1])
        
        # اختيار الفئة الأقل استخداماً إذا كانت أقل من 3 مقالات
        if sorted_cats and sorted_cats[0][1] < 3:
            return sorted_cats[0][0]
        
        # اختيار عشوائي من الفئات الأقل استخداماً
        least_used = [cat for cat, count in sorted_cats[:3]]
        return random.choice(least_used) if least_used else random.choice(config.CONTENT_CATEGORIES)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class ZajmilAIChef:
    """النظام المتكامل - جاهز للإنتاج على Render"""
    
    def __init__(self):
        logger.info("=" * 80)
        logger.info("🚀 Initializing Zajmil AI Chef System v2.0 [RENDER PRODUCTION]")
        logger.info("=" * 80)
        
        # التحقق من الإعدادات
        config.validate()
        
        # عرض معلومات البيئة
        logger.info(f"🌐 Environment: {'Render Cloud' if config.IS_RENDER_ENV else 'Local'}")
        logger.info(f"📁 Base Path: {config.BASE_DIR}")
        logger.info(f"🤖 AI Model: {config.GEMINI_MODEL}")
        
        # حساب وعرض عدد المقالات الأمثل
        self.optimal_article_count = config.calculate_optimal_article_count()
        logger.info(f"\n📊 Dynamic Article Count Configuration:")
        logger.info(f"   • Min Views Fetch Period: {config.MIN_VIEWS_FETCH_HOURS}h")
        logger.info(f"   • Publish Interval: {config.PUBLISH_INTERVAL_HOURS}h")
        logger.info(f"   • Safety Factor: {config.ARTICLE_SAFETY_FACTOR}")
        logger.info(f"   • Optimal Article Count: {self.optimal_article_count} articles")
        logger.info(f"   • Limits: {config.MIN_ARTICLES_LIMIT} - {config.MAX_ARTICLES_LIMIT}")
        
        # تهيئة المكونات
        try:
            self.gemini = GeminiChefEngine()
            self.publisher = BloggerPublisher()
            self.seo = SEOOptimizer()
            self.validator = ContentValidator()
            self.analytics = AnalyticsTracker()
        except Exception as e:
            logger.critical(f"❌ Component initialization failed: {e}")
            raise
        
        # عداد المقالات المنشورة
        self.published_count = 0
        
        logger.info("\n✅ All components initialized successfully")
        logger.info("=" * 80)
    
    def generate_and_publish(self, category: Optional[str] = None) -> bool:
        """سير العمل الكامل: توليد → تحقق → تحسين → نشر → تتبع"""
        try:
            logger.info("\n" + "=" * 80)
            logger.info("🎬 Starting Recipe Workflow")
            logger.info("=" * 80)
            
            # اختيار الفئة
            if not category:
                category = self.analytics.get_next_category()
            
            logger.info(f"🎯 Selected Category: {category}")
            
            # الخطوة 1: التوليد
            logger.info("\n📝 Step 1/5: Generating recipe with Gemini AI...")
            recipe = self.gemini.generate_recipe(category)
            if not recipe:
                logger.error("❌ Generation failed")
                return False
            
            logger.info(f"✅ Recipe generated: {recipe.title[:60]}...")
            
            # الخطوة 2: التحقق
            logger.info("\n🔍 Step 2/5: Validating content quality...")
            is_valid, messages = self.validator.validate(recipe)
            if not is_valid:
                logger.error(f"❌ Validation failed:")
                for msg in messages:
                    logger.error(f"   {msg}")
                return False
            
            logger.info("✅ Content validation passed")
            
            # الخطوة 3: تحسين SEO
            logger.info("\n🔧 Step 3/5: Optimizing for SEO...")
            recipe = self.seo.optimize_for_seo(recipe)
            seo_analysis = self.seo.analyze_recipe(recipe)
            
            logger.info(f"✅ SEO Score: {seo_analysis['score']:.1f}/100 ({seo_analysis['grade']})")
            for factor, value in seo_analysis['factors'].items():
                logger.info(f"   {factor}: {value}")
            
            # الخطوة 4: النشر
            logger.info("\n📤 Step 4/5: Publishing to Blogger...")
            post_id = self.publisher.publish_recipe(recipe)
            if not post_id:
                logger.error("❌ Publishing failed")
                return False
            
            logger.info("✅ Successfully published")
            
            # الخطوة 5: التتبع
            logger.info("\n📊 Step 5/5: Tracking analytics...")
            self.analytics.track_recipe(recipe, not config.DRAFT_MODE)
            
            # تحديث العداد
            self.published_count += 1
            
            # ملخص نهائي
            logger.info("\n" + "=" * 80)
            logger.info("🎉 Workflow Completed Successfully!")
            logger.info("=" * 80)
            logger.info(f"📝 Title: {recipe.title}")
            logger.info(f"📂 Category: {recipe.category}")
            logger.info(f"🔍 SEO Score: {seo_analysis['score']:.1f}/100")
            logger.info(f"📊 Word Count: {recipe.word_count}")
            logger.info(f"🔗 URL: {recipe.post_url}")
            logger.info(f"📈 Session Progress: {self.published_count}/{self.optimal_article_count}")
            logger.info("=" * 80 + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Workflow failed with exception: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def run_continuous(self):
        """وضع النشر المستمر مع توقف تلقائي عند الوصول للحد المطلوب"""
        logger.info("\n" + "=" * 80)
        logger.info("⏰ CONTINUOUS PUBLISHING MODE")
        logger.info("=" * 80)
        logger.info(f"📊 Target: {self.optimal_article_count} articles")
        logger.info(f"⏱️ Interval: {config.PUBLISH_INTERVAL_HOURS}h per article")
        logger.info(f"📅 Estimated Duration: {self.optimal_article_count * config.PUBLISH_INTERVAL_HOURS:.1f}h")
        logger.info(f"🎯 Mode: {'Draft' if config.DRAFT_MODE else 'Published'}")
        logger.info("=" * 80 + "\n")
        
        start_time = datetime.now()
        
        while self.published_count < self.optimal_article_count:
            try:
                logger.info(f"\n{'='*80}")
                logger.info(f"Article {self.published_count + 1}/{self.optimal_article_count}")
                logger.info(f"{'='*80}")
                
                success = self.generate_and_publish()
                
                # التحقق من الوصول للحد المطلوب
                if self.published_count >= self.optimal_article_count:
                    elapsed = datetime.now() - start_time
                    logger.info("\n" + "=" * 80)
                    logger.info("🎯 TARGET REACHED!")
                    logger.info("=" * 80)
                    logger.info(f"✅ Published: {self.published_count}/{self.optimal_article_count} articles")
                    logger.info(f"⏱️ Total Duration: {elapsed}")
                    logger.info(f"📊 Average SEO Score: {self.analytics.data['statistics']['avg_seo_score']:.1f}")
                    logger.info("=" * 80)
                    break
                
                # حساب وقت الانتظار مع تنويع عشوائي بسيط
                sleep_sec = config.PUBLISH_INTERVAL_HOURS * 3600
                sleep_sec = int(sleep_sec * random.uniform(0.95, 1.05))  # ±5%
                
                remaining = self.optimal_article_count - self.published_count
                next_publish = datetime.now() + timedelta(seconds=sleep_sec)
                
                logger.info(f"\n😴 Sleeping for {sleep_sec/3600:.2f}h...")
                logger.info(f"📊 Remaining: {remaining} articles")
                logger.info(f"🕐 Next publish at: {next_publish.strftime('%Y-%m-%d %H:%M:%S')}")
                
                time.sleep(sleep_sec)
                
            except KeyboardInterrupt:
                logger.info("\n⏹️ Stopped by user (Ctrl+C)")
                logger.info(f"📊 Published: {self.published_count}/{self.optimal_article_count}")
                break
            except Exception as e:
                logger.error(f"❌ Error in continuous loop: {e}")
                logger.info("⏸️ Pausing 1h before retry...")
                time.sleep(3600)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """نقطة الدخول الرئيسية للبرنامج"""
    
    parser = argparse.ArgumentParser(
        description="Zajmil AI Chef v2.0 - Production Ready for Render",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
═══════════════════════════════════════════════════════════════════════════════
RENDER ENVIRONMENT VARIABLES GUIDE
═══════════════════════════════════════════════════════════════════════════════

REQUIRED:
  GEMINI_API_KEY              Your Gemini AI API key
  BLOGGER_BLOG_ID             Your Blogger blog ID
  TOKEN_JSON                  Complete token.json content as JSON string
  
OPTIONAL (OAuth):
  CLIENT_SECRET_JSON          Complete client_secret.json as JSON string
  BLOGGER_CLIENT_ID           OAuth client ID
  BLOGGER_CLIENT_SECRET       OAuth client secret

PUBLISHING:
  PUBLISH_INTERVAL_HOURS      Hours between posts (default: 24)
  DRAFT_MODE                  Publish as draft (default: false)
  AUTO_PUBLISH                Enable auto-publishing (default: true)

DYNAMIC ARTICLE COUNT:
  MIN_VIEWS_FETCH_HOURS       Min hours to fetch views (default: 48)
  ARTICLE_SAFETY_FACTOR       Safety multiplier (default: 0.8)
  MAX_ARTICLES_LIMIT          Maximum articles (default: 100)
  MIN_ARTICLES_LIMIT          Minimum articles (default: 1)
  ENABLE_DYNAMIC_ARTICLE_COUNT Enable calculation (default: true)
  FIXED_ARTICLE_COUNT         Fixed count if disabled (default: 50)

SEO OPTIMIZATION:
  AGGRESSIVE_SEO_MODE         Enable aggressive SEO (default: true)
  ENABLE_RICH_SNIPPETS        Enable rich snippets (default: true)
  ENABLE_SOCIAL_META_TAGS     Enable social tags (default: true)
  TARGET_WORD_COUNT           Target words per recipe (default: 1200)

AI MODEL:
  GEMINI_MODEL                Model name (default: gemini-1.5-flash)
  GEMINI_TEMPERATURE          Creativity level (default: 0.9)

═══════════════════════════════════════════════════════════════════════════════
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['once', 'continuous', 'report'],
        default='once',
        help='Execution mode'
    )
    parser.add_argument(
        '--category',
        type=str,
        help='Specific recipe category'
    )
    parser.add_argument(
        '--draft',
        action='store_true',
        help='Publish as draft'
    )
    
    args = parser.parse_args()
    
    try:
        # تهيئة النظام
        zajmil = ZajmilAIChef()
        
        # تطبيق خيار draft من الأوامر
        if args.draft:
            config.DRAFT_MODE = True
            logger.info("📝 Draft mode enabled via command line")
        
        # تنفيذ حسب الوضع المطلوب
        if args.mode == 'once':
            logger.info("🎯 Mode: Single Recipe\n")
            success = zajmil.generate_and_publish(args.category)
            sys.exit(0 if success else 1)
        
        elif args.mode == 'continuous':
            logger.info("♾️ Mode: Continuous Publishing\n")
            zajmil.run_continuous()
            sys.exit(0)
        
        elif args.mode == 'report':
            logger.info("📊 ANALYTICS REPORT")
            logger.info("=" * 80)
            stats = zajmil.analytics.data['statistics']
            logger.info(f"Total Published: {stats['total_published']}")
            logger.info(f"Total Drafts: {stats['total_drafts']}")
            logger.info(f"Average SEO Score: {stats['avg_seo_score']:.1f}/100")
            logger.info(f"\nCategories Distribution:")
            for cat, count in sorted(stats['categories_count'].items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  • {cat}: {count} articles")
            logger.info("=" * 80)
            sys.exit(0)
    
    except KeyboardInterrupt:
        logger.info("\n⏹️ Program interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"\n💥 FATAL ERROR: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
