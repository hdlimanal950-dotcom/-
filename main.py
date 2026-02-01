#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
ZAJMIL AI CHEF - Complete Integrated System v1.1.0 [RENDER OPTIMIZED]
═══════════════════════════════════════════════════════════════════════════════
نظام متكامل لتوليد ونشر وصفات الطبخ باستخدام الذكاء الاصطناعي

المميزات المحسّنة:
✅ قراءة شاملة لمتغيرات Render البيئية
✅ حساب ديناميكي لعدد المقالات حسب أقصر مدة لجلب المشاهدات
✅ توليد وصفات احترافية بـ Gemini AI
✅ تحسين SEO تلقائي
✅ نشر مباشر على Blogger
✅ تتبع الأداء والتحليلات
✅ ضمان الجودة والتحقق

الاستخدام:
  python main.py --mode once              # نشر وصفة واحدة
  python main.py --mode continuous        # نشر مستمر
  python main.py --mode report            # تقرير الأداء
  
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
# CONFIGURATION WITH RENDER ENVIRONMENT VARIABLES SUPPORT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    """إعدادات النظام الشاملة مع دعم كامل لمتغيرات Render"""
    
    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro")
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.9"))
    GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "8000"))
    
    # Blogger API
    BLOGGER_BLOG_ID: str = os.getenv("BLOGGER_BLOG_ID", "")
    BLOGGER_CLIENT_ID: str = os.getenv("BLOGGER_CLIENT_ID", "")
    BLOGGER_CLIENT_SECRET: str = os.getenv("BLOGGER_CLIENT_SECRET", "")
    BLOGGER_SCOPES: List[str] = field(default_factory=lambda: [
        "https://www.googleapis.com/auth/blogger"
    ])
    
    # Content Settings (قراءة من متغيرات البيئة)
    CONTENT_CATEGORIES: List[str] = field(default_factory=lambda: 
        json.loads(os.getenv("CONTENT_CATEGORIES", json.dumps([
            "حلويات عربية", "معجنات", "كيك وتورتات", "بسكويت وكوكيز",
            "حلويات باردة", "فطائر ومخبوزات", "حلويات صحية", "أطباق رمضانية"
        ])))
    )
    
    MIN_RECIPE_INGREDIENTS: int = int(os.getenv("MIN_RECIPE_INGREDIENTS", "5"))
    MIN_RECIPE_STEPS: int = int(os.getenv("MIN_RECIPE_STEPS", "6"))
    TARGET_WORD_COUNT: int = int(os.getenv("TARGET_WORD_COUNT", "1200"))
    
    # SEO (قراءة من متغيرات البيئة)
    PRIMARY_KEYWORDS: List[str] = field(default_factory=lambda: 
        json.loads(os.getenv("PRIMARY_KEYWORDS", json.dumps([
            "وصفات طبخ", "حلويات سهلة", "طريقة عمل", "وصفات منزلية",
            "حلويات لذيذة", "مطبخ عربي", "وصفات سريعة"
        ])))
    )
    
    META_DESCRIPTION_LENGTH: int = int(os.getenv("META_DESCRIPTION_LENGTH", "160"))
    ENABLE_SCHEMA_MARKUP: bool = os.getenv("ENABLE_SCHEMA_MARKUP", "true").lower() == "true"
    
    # Publishing Strategy - معايير محسّنة
    PUBLISH_INTERVAL_HOURS: int = int(os.getenv("PUBLISH_INTERVAL_HOURS", "24"))
    AUTO_PUBLISH: bool = os.getenv("AUTO_PUBLISH", "true").lower() == "true"
    DRAFT_MODE: bool = os.getenv("DRAFT_MODE", "false").lower() == "true"
    
    # ═══ إعدادات جديدة: حساب عدد المقالات الديناميكي ═══
    # أقصر مدة فعالة لجلب المشاهدات (بالساعات)
    MIN_VIEWS_FETCH_HOURS: int = int(os.getenv("MIN_VIEWS_FETCH_HOURS", "48"))
    
    # معامل الأمان (safety factor) للتحكم في الكمية
    ARTICLE_SAFETY_FACTOR: float = float(os.getenv("ARTICLE_SAFETY_FACTOR", "0.8"))
    
    # الحد الأقصى للمقالات (حماية من التضخم)
    MAX_ARTICLES_LIMIT: int = int(os.getenv("MAX_ARTICLES_LIMIT", "100"))
    
    # الحد الأدنى للمقالات (ضمان الحد الأدنى من الإنتاجية)
    MIN_ARTICLES_LIMIT: int = int(os.getenv("MIN_ARTICLES_LIMIT", "1"))
    
    # تفعيل/تعطيل الحساب الديناميكي
    ENABLE_DYNAMIC_ARTICLE_COUNT: bool = os.getenv("ENABLE_DYNAMIC_ARTICLE_COUNT", "true").lower() == "true"
    
    # عدد المقالات الثابت (في حال تعطيل الحساب الديناميكي)
    FIXED_ARTICLE_COUNT: int = int(os.getenv("FIXED_ARTICLE_COUNT", "50"))
    
    # Render Specific Settings
    RENDER_INSTANCE_ID: str = os.getenv("RENDER_INSTANCE_ID", "")
    RENDER_SERVICE_NAME: str = os.getenv("RENDER_SERVICE_NAME", "")
    RENDER_GIT_COMMIT: str = os.getenv("RENDER_GIT_COMMIT", "")
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    CREDENTIALS_PATH: Path = field(init=False)
    DATA_DIR: Path = field(init=False)
    LOG_FILE: str = os.getenv("LOG_FILE", "zajmil.log")
    PERFORMANCE_FILE: str = os.getenv("PERFORMANCE_FILE", "performance.json")
    
    def __post_init__(self):
        self.CREDENTIALS_PATH = self.BASE_DIR / "token.json"
        self.DATA_DIR = self.BASE_DIR / "data"
        self.DATA_DIR.mkdir(exist_ok=True)
    
    def calculate_optimal_article_count(self) -> int:
        """
        حساب عدد المقالات الأمثل بناءً على أقصر مدة لجلب المشاهدات
        
        المعادلة: 
        articles = (MIN_VIEWS_FETCH_HOURS / PUBLISH_INTERVAL_HOURS) × SAFETY_FACTOR
        
        Returns:
            int: عدد المقالات المحسوب ضمن الحدود المسموحة
        """
        if not self.ENABLE_DYNAMIC_ARTICLE_COUNT:
            return self.FIXED_ARTICLE_COUNT
        
        # الحساب الأساسي
        raw_count = (self.MIN_VIEWS_FETCH_HOURS / self.PUBLISH_INTERVAL_HOURS) * self.ARTICLE_SAFETY_FACTOR
        
        # تقريب للأعلى لضمان التغطية
        calculated_count = int(raw_count) + (1 if raw_count % 1 > 0 else 0)
        
        # تطبيق الحدود
        final_count = max(
            self.MIN_ARTICLES_LIMIT,
            min(calculated_count, self.MAX_ARTICLES_LIMIT)
        )
        
        return final_count
    
    def validate(self) -> bool:
        if not self.GEMINI_API_KEY:
            raise ValueError("❌ GEMINI_API_KEY is required")
        if not self.BLOGGER_BLOG_ID:
            raise ValueError("❌ BLOGGER_BLOG_ID is required")
        if not self.BLOGGER_CLIENT_ID or not self.BLOGGER_CLIENT_SECRET:
            raise ValueError("❌ Blogger OAuth credentials required")
        
        # التحقق من صحة المعايير الجديدة
        if self.MIN_VIEWS_FETCH_HOURS < self.PUBLISH_INTERVAL_HOURS:
            raise ValueError("❌ MIN_VIEWS_FETCH_HOURS must be >= PUBLISH_INTERVAL_HOURS")
        
        if self.ARTICLE_SAFETY_FACTOR <= 0 or self.ARTICLE_SAFETY_FACTOR > 2:
            raise ValueError("❌ ARTICLE_SAFETY_FACTOR must be between 0 and 2")
        
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
    
    file_handler = RotatingFileHandler(
        config.LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
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
        html = f"""
<article class="recipe-post">
    <div class="recipe-header">
        <h1>{self.title}</h1>
        <p class="recipe-meta">
            <span>⏱️ التحضير: {self.prep_time} دقيقة</span> | 
            <span>🔥 الطهي: {self.cook_time} دقيقة</span> | 
            <span>👥 {self.servings} أشخاص</span> | 
            <span>📊 {self.difficulty}</span>
        </p>
    </div>
    
    <div class="recipe-description">
        <p>{self.description}</p>
    </div>
    
    <div class="recipe-ingredients">
        <h2>🥘 المقادير</h2>
        <ul>
"""
        for ing in self.ingredients:
            html += f"            <li>{ing}</li>\n"
        
        html += """        </ul>
    </div>
    
    <div class="recipe-steps">
        <h2>👨‍🍳 طريقة التحضير</h2>
        <ol>
"""
        for step in self.steps:
            html += f"            <li>{step}</li>\n"
        
        html += f"""        </ol>
    </div>
    
    <div class="recipe-footer">
        <p>💡 <strong>نصائح للنجاح:</strong> اتبع الخطوات بدقة للحصول على أفضل النتائج</p>
        <p>⭐ شارك تجربتك في التعليقات!</p>
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
}}

.recipe-header h1 {{
    color: #2c3e50;
    font-size: 2.2em;
    margin-bottom: 10px;
    border-bottom: 3px solid #e74c3c;
    padding-bottom: 10px;
}}

.recipe-meta {{
    color: #7f8c8d;
    font-size: 0.95em;
    margin: 15px 0;
}}

.recipe-meta span {{
    margin-right: 15px;
}}

.recipe-description p {{
    font-size: 1.1em;
    color: #34495e;
    background: #ecf0f1;
    padding: 15px;
    border-left: 4px solid #3498db;
    margin: 20px 0;
}}

.recipe-ingredients, .recipe-steps {{
    margin: 30px 0;
}}

.recipe-ingredients h2, .recipe-steps h2 {{
    color: #e74c3c;
    font-size: 1.6em;
    margin-bottom: 15px;
}}

.recipe-ingredients ul {{
    list-style: none;
    padding: 0;
}}

.recipe-ingredients li {{
    background: #f8f9fa;
    padding: 10px 15px;
    margin: 8px 0;
    border-left: 4px solid #27ae60;
    font-size: 1.05em;
}}

.recipe-steps ol {{
    counter-reset: step-counter;
    list-style: none;
    padding: 0;
}}

.recipe-steps li {{
    counter-increment: step-counter;
    background: #fff;
    padding: 15px;
    margin: 15px 0;
    border: 1px solid #ddd;
    border-radius: 5px;
    position: relative;
    padding-right: 60px;
}}

.recipe-steps li:before {{
    content: counter(step-counter);
    position: absolute;
    right: 15px;
    top: 50%;
    transform: translateY(-50%);
    background: #3498db;
    color: white;
    width: 35px;
    height: 35px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 1.2em;
}}

.recipe-footer {{
    margin-top: 40px;
    padding: 20px;
    background: #fffbea;
    border-radius: 8px;
    border: 2px dashed #f39c12;
}}

.recipe-footer p {{
    margin: 10px 0;
    font-size: 1.05em;
}}
</style>
"""
        return html

# ═══════════════════════════════════════════════════════════════════════════════
# GEMINI AI ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiChefEngine:
    """محرك توليد الوصفات بواسطة Gemini AI"""
    
    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        self.model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            generation_config={
                "temperature": config.GEMINI_TEMPERATURE,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": config.GEMINI_MAX_TOKENS,
            }
        )
        
        logger.info("✅ Gemini AI Engine initialized")
    
    def generate_recipe(self, category: str) -> Optional[Recipe]:
        try:
            logger.info(f"🤖 Generating recipe for: {category}")
            
            prompt = self._build_prompt(category)
            
            response = self.model.generate_content(prompt)
            
            if not response or not response.text:
                logger.error("❌ Empty response from Gemini")
                return None
            
            recipe = self._parse_response(response.text, category)
            
            if recipe:
                logger.info(f"✅ Generated: {recipe.title}")
                return recipe
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Generation failed: {e}")
            return None
    
    def _build_prompt(self, category: str) -> str:
        return f"""أنت طاهٍ محترف ومبدع متخصص في {category}.

أنشئ وصفة طبخ احترافية وجذابة بالمواصفات التالية:

المتطلبات:
- العنوان: جذاب ومحفز، يحتوي على كلمات مفتاحية SEO
- الوصف: مشوق ومغري (100-150 كلمة)
- المقادير: {config.MIN_RECIPE_INGREDIENTS}+ عناصر بتفاصيل دقيقة
- الخطوات: {config.MIN_RECIPE_STEPS}+ خطوات واضحة ومفصلة
- الكلمات: {config.TARGET_WORD_COUNT}+ كلمة إجمالاً

تنسيق JSON:
{{
  "title": "عنوان الوصفة الجذاب",
  "description": "وصف مشوق ومفصل",
  "ingredients": ["مقدار 1", "مقدار 2", ...],
  "steps": ["خطوة 1 مفصلة", "خطوة 2 مفصلة", ...],
  "prep_time": رقم_بالدقائق,
  "cook_time": رقم_بالدقائق,
  "servings": رقم,
  "difficulty": "سهل/متوسط/صعب",
  "keywords": ["كلمة1", "كلمة2", ...],
  "tags": ["وسم1", "وسم2", ...]
}}

ملاحظات:
- استخدم لغة عربية فصحى سلسة
- أضف نصائح احترافية في الخطوات
- اجعل الوصفة عملية وقابلة للتطبيق
- ركز على الكلمات المفتاحية: {', '.join(config.PRIMARY_KEYWORDS[:3])}

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
# SEO OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════

class SEOOptimizer:
    """محسّن SEO للوصفات"""
    
    def __init__(self):
        logger.info("✅ SEO Optimizer initialized")
    
    def optimize_for_seo(self, recipe: Recipe) -> Recipe:
        recipe.meta_description = self._generate_meta_description(recipe)
        
        if not recipe.keywords:
            recipe.keywords = self._extract_keywords(recipe)
        
        if config.ENABLE_SCHEMA_MARKUP:
            pass
        
        return recipe
    
    def _generate_meta_description(self, recipe: Recipe) -> str:
        desc = recipe.description[:config.META_DESCRIPTION_LENGTH - 3]
        if len(recipe.description) > config.META_DESCRIPTION_LENGTH - 3:
            desc += "..."
        return desc
    
    def _extract_keywords(self, recipe: Recipe) -> List[str]:
        keywords = set()
        
        for kw in config.PRIMARY_KEYWORDS:
            if kw in recipe.title or kw in recipe.description:
                keywords.add(kw)
        
        keywords.add(recipe.category)
        keywords.add(recipe.title.split()[0] if recipe.title.split() else "")
        
        return list(keywords)[:10]
    
    def analyze_recipe(self, recipe: Recipe) -> Dict:
        score = 0.0
        factors = {}
        
        if len(recipe.title) >= 30 and len(recipe.title) <= 70:
            score += 20
            factors['title_length'] = "✅ مثالي"
        else:
            factors['title_length'] = "⚠️ قصير/طويل"
        
        if recipe.word_count >= config.TARGET_WORD_COUNT:
            score += 25
            factors['word_count'] = f"✅ {recipe.word_count} كلمة"
        else:
            factors['word_count'] = f"⚠️ {recipe.word_count} كلمة"
        
        if len(recipe.ingredients) >= config.MIN_RECIPE_INGREDIENTS:
            score += 15
            factors['ingredients'] = f"✅ {len(recipe.ingredients)} عنصر"
        
        if len(recipe.steps) >= config.MIN_RECIPE_STEPS:
            score += 15
            factors['steps'] = f"✅ {len(recipe.steps)} خطوة"
        
        if len(recipe.keywords) >= 3:
            score += 15
            factors['keywords'] = f"✅ {len(recipe.keywords)} كلمة"
        
        if recipe.meta_description:
            score += 10
            factors['meta_desc'] = "✅ موجود"
        
        recipe.seo_score = score
        
        return {
            'score': score,
            'factors': factors,
            'grade': 'ممتاز' if score >= 80 else 'جيد' if score >= 60 else 'مقبول'
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
        
        if not recipe.title or len(recipe.title) < 10:
            errors.append("❌ العنوان قصير جداً")
        
        if len(recipe.ingredients) < config.MIN_RECIPE_INGREDIENTS:
            errors.append(f"❌ المقادير قليلة (مطلوب {config.MIN_RECIPE_INGREDIENTS}+)")
        
        if len(recipe.steps) < config.MIN_RECIPE_STEPS:
            errors.append(f"❌ الخطوات قليلة (مطلوب {config.MIN_RECIPE_STEPS}+)")
        
        if recipe.word_count < config.TARGET_WORD_COUNT * 0.7:
            errors.append(f"❌ عدد الكلمات قليل ({recipe.word_count}/{config.TARGET_WORD_COUNT})")
        
        if not recipe.description or len(recipe.description) < 50:
            errors.append("❌ الوصف قصير جداً")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("✅ Validation passed")
        else:
            logger.warning(f"⚠️ Validation issues: {len(errors)}")
        
        return is_valid, errors

# ═══════════════════════════════════════════════════════════════════════════════
# BLOGGER PUBLISHER
# ═══════════════════════════════════════════════════════════════════════════════

class BloggerPublisher:
    """ناشر المحتوى على Blogger"""
    
    def __init__(self):
        self.blog_id = config.BLOGGER_BLOG_ID
        self.credentials = self._get_credentials()
        self.service = build('blogger', 'v3', credentials=self.credentials)
        logger.info("✅ Blogger Publisher initialized")
    
    def _get_credentials(self) -> Credentials:
        creds = None
        
        if config.CREDENTIALS_PATH.exists():
            try:
                with open(config.CREDENTIALS_PATH, 'r') as token:
                    creds = Credentials.from_authorized_user_info(
                        json.load(token), config.BLOGGER_SCOPES
                    )
            except Exception as e:
                logger.warning(f"⚠️ Token load failed: {e}")
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config(
                    {
                        "installed": {
                            "client_id": config.BLOGGER_CLIENT_ID,
                            "client_secret": config.BLOGGER_CLIENT_SECRET,
                            "redirect_uris": ["http://localhost"],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token"
                        }
                    },
                    config.BLOGGER_SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            with open(config.CREDENTIALS_PATH, 'w') as token:
                token.write(creds.to_json())
        
        self.credentials = creds
        return creds
    
    def publish_recipe(self, recipe: Recipe, as_draft: bool = None) -> Optional[str]:
        try:
            is_draft = as_draft if as_draft is not None else config.DRAFT_MODE
            
            logger.info(f"📤 Publishing: {recipe.title} | Draft: {is_draft}")
            
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
            except:
                pass
        
        return {
            'recipes': [],
            'statistics': {
                'total_published': 0,
                'avg_seo_score': 0.0,
                'categories_count': {}
            }
        }
    
    def _save(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def track_recipe(self, recipe: Recipe, published: bool = True):
        self.data['recipes'].append({
            'post_id': recipe.post_id,
            'title': recipe.title,
            'category': recipe.category,
            'seo_score': recipe.seo_score,
            'word_count': recipe.word_count,
            'published_at': recipe.published_at.isoformat() if recipe.published_at else None,
            'is_published': published
        })
        
        stats = self.data['statistics']
        if published:
            stats['total_published'] += 1
        
        cat = recipe.category
        stats['categories_count'][cat] = stats['categories_count'].get(cat, 0) + 1
        
        scores = [r['seo_score'] for r in self.data['recipes'] if r.get('seo_score', 0) > 0]
        if scores:
            stats['avg_seo_score'] = sum(scores) / len(scores)
        
        self._save()
        logger.info("✅ Recipe tracked")
    
    def get_next_category(self) -> str:
        counts = self.data['statistics'].get('categories_count', {})
        
        if not counts:
            return random.choice(config.CONTENT_CATEGORIES)
        
        sorted_cats = sorted(counts.items(), key=lambda x: x[1])
        return sorted_cats[0][0] if sorted_cats[0][1] < 3 else random.choice(config.CONTENT_CATEGORIES)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class ZajmilAIChef:
    """النظام المتكامل"""
    
    def __init__(self):
        logger.info("=" * 80)
        logger.info("🚀 Initializing Zajmil AI Chef System [RENDER OPTIMIZED]")
        logger.info("=" * 80)
        
        config.validate()
        
        # حساب وعرض عدد المقالات الأمثل
        self.optimal_article_count = config.calculate_optimal_article_count()
        logger.info(f"📊 Dynamic Article Count Calculation:")
        logger.info(f"   • Min Views Fetch Period: {config.MIN_VIEWS_FETCH_HOURS}h")
        logger.info(f"   • Publish Interval: {config.PUBLISH_INTERVAL_HOURS}h")
        logger.info(f"   • Safety Factor: {config.ARTICLE_SAFETY_FACTOR}")
        logger.info(f"   • Optimal Article Count: {self.optimal_article_count} articles")
        logger.info(f"   • Limits: {config.MIN_ARTICLES_LIMIT} - {config.MAX_ARTICLES_LIMIT}")
        
        self.gemini = GeminiChefEngine()
        self.publisher = BloggerPublisher()
        self.seo = SEOOptimizer()
        self.validator = ContentValidator()
        self.analytics = AnalyticsTracker()
        
        # عداد المقالات المنشورة في الجلسة الحالية
        self.published_count = 0
        
        logger.info("✅ All components initialized")
        logger.info("=" * 80)
    
    def generate_and_publish(self, category: Optional[str] = None) -> bool:
        try:
            logger.info("\n" + "=" * 80)
            logger.info("🎬 Starting workflow")
            logger.info("=" * 80)
            
            if not category:
                category = self.analytics.get_next_category()
            
            logger.info(f"🎯 Category: {category}")
            
            # توليد
            logger.info("\n📝 Step 1/5: Generating recipe...")
            recipe = self.gemini.generate_recipe(category)
            if not recipe:
                return False
            
            # تحقق
            logger.info("\n🔍 Step 2/5: Validating...")
            is_valid, errors = self.validator.validate(recipe)
            if not is_valid:
                logger.error(f"Errors: {errors}")
                return False
            
            # تحسين SEO
            logger.info("\n🔧 Step 3/5: Optimizing SEO...")
            recipe = self.seo.optimize_for_seo(recipe)
            seo_analysis = self.seo.analyze_recipe(recipe)
            
            # نشر
            logger.info("\n📤 Step 4/5: Publishing...")
            post_id = self.publisher.publish_recipe(recipe)
            if not post_id:
                return False
            
            # تتبع
            logger.info("\n📊 Step 5/5: Tracking...")
            self.analytics.track_recipe(recipe, not config.DRAFT_MODE)
            
            # تحديث العداد
            self.published_count += 1
            
            logger.info("=" * 80)
            logger.info("🎉 Workflow completed!")
            logger.info(f"📝 {recipe.title}")
            logger.info(f"🔍 SEO: {seo_analysis['score']:.1f}/100")
            logger.info(f"🔗 {recipe.post_url}")
            logger.info(f"📈 Progress: {self.published_count}/{self.optimal_article_count}")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Workflow failed: {e}")
            return False
    
    def run_continuous(self):
        logger.info(f"\n⏰ Continuous mode")
        logger.info(f"   • Publish Interval: {config.PUBLISH_INTERVAL_HOURS}h")
        logger.info(f"   • Target Article Count: {self.optimal_article_count}")
        logger.info(f"   • Estimated Duration: {self.optimal_article_count * config.PUBLISH_INTERVAL_HOURS:.1f}h")
        
        while self.published_count < self.optimal_article_count:
            try:
                success = self.generate_and_publish()
                
                # التحقق من الوصول للحد المطلوب
                if self.published_count >= self.optimal_article_count:
                    logger.info("\n" + "=" * 80)
                    logger.info("🎯 Target article count reached!")
                    logger.info(f"   • Published: {self.published_count}/{self.optimal_article_count}")
                    logger.info(f"   • Total Duration: {self.published_count * config.PUBLISH_INTERVAL_HOURS}h")
                    logger.info("=" * 80)
                    break
                
                # حساب وقت الانتظار
                sleep_sec = config.PUBLISH_INTERVAL_HOURS * 3600
                sleep_sec = int(sleep_sec * random.uniform(0.9, 1.1))
                
                remaining = self.optimal_article_count - self.published_count
                logger.info(f"\n😴 Sleeping {sleep_sec/3600:.1f}h...")
                logger.info(f"📊 Remaining: {remaining} articles")
                time.sleep(sleep_sec)
                
            except KeyboardInterrupt:
                logger.info("\n⏹️ Stopped by user")
                logger.info(f"📊 Published: {self.published_count}/{self.optimal_article_count}")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                logger.info("⏸️ Pausing 1h before retry...")
                time.sleep(3600)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Zajmil AI Chef - Render Optimized",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables for Render:
  GEMINI_API_KEY              Gemini AI API key (required)
  BLOGGER_BLOG_ID             Blogger blog ID (required)
  BLOGGER_CLIENT_ID           OAuth client ID (required)
  BLOGGER_CLIENT_SECRET       OAuth client secret (required)
  
  MIN_VIEWS_FETCH_HOURS       Minimum hours to fetch views (default: 48)
  PUBLISH_INTERVAL_HOURS      Publishing interval (default: 24)
  ARTICLE_SAFETY_FACTOR       Safety factor for article count (default: 0.8)
  MAX_ARTICLES_LIMIT          Maximum articles limit (default: 100)
  MIN_ARTICLES_LIMIT          Minimum articles limit (default: 1)
  
  ENABLE_DYNAMIC_ARTICLE_COUNT Enable/disable dynamic calculation (default: true)
  FIXED_ARTICLE_COUNT         Fixed count if dynamic disabled (default: 50)
  
  AUTO_PUBLISH                Auto-publish mode (default: true)
  DRAFT_MODE                  Draft mode (default: false)
        """
    )
    
    parser.add_argument('--mode', choices=['once', 'continuous', 'report'], default='once')
    parser.add_argument('--category', type=str, help='Specific category')
    parser.add_argument('--draft', action='store_true', help='Publish as draft')
    
    args = parser.parse_args()
    
    try:
        zajmil = ZajmilAIChef()
        
        if args.draft:
            config.DRAFT_MODE = True
        
        if args.mode == 'once':
            success = zajmil.generate_and_publish(args.category)
            sys.exit(0 if success else 1)
        
        elif args.mode == 'continuous':
            zajmil.run_continuous()
        
        elif args.mode == 'report':
            logger.info("📊 Analytics Report:")
            logger.info(f"   • Total Published: {zajmil.analytics.data['statistics']['total_published']}")
            logger.info(f"   • Avg SEO Score: {zajmil.analytics.data['statistics']['avg_seo_score']:.1f}")
            logger.info(f"   • Categories: {zajmil.analytics.data['statistics']['categories_count']}")
    
    except KeyboardInterrupt:
        logger.info("\n⏹️ Stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
