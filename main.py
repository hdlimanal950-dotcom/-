#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
ZAJMIL AI CHEF - Complete Integrated System v1.0.0
═══════════════════════════════════════════════════════════════════════════════
نظام متكامل لتوليد ونشر وصفات الطبخ باستخدام الذكاء الاصطناعي

المميزات:
✅ توليد وصفات احترافية بـ Gemini AI
✅ تحسين SEO تلقائي
✅ نشر مباشر على Blogger
✅ تتبع الأداء والتحليلات
✅ ضمان الجودة والتحقق

الاستخدام:
  python zajmil_complete.py --mode once              # نشر وصفة واحدة
  python zajmil_complete.py --mode continuous        # نشر مستمر
  python zajmil_complete.py --mode report            # تقرير الأداء
  
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
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    """إعدادات النظام الشاملة"""
    
    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "models/gemini-1.5-pro"
    GEMINI_TEMPERATURE: float = 0.9
    GEMINI_MAX_TOKENS: int = 8000
    
    # Blogger API
    BLOGGER_BLOG_ID: str = os.getenv("BLOGGER_BLOG_ID", "")
    BLOGGER_CLIENT_ID: str = os.getenv("BLOGGER_CLIENT_ID", "")
    BLOGGER_CLIENT_SECRET: str = os.getenv("BLOGGER_CLIENT_SECRET", "")
    BLOGGER_SCOPES: List[str] = field(default_factory=lambda: [
        "https://www.googleapis.com/auth/blogger"
    ])
    
    # Content Settings
    CONTENT_CATEGORIES: List[str] = field(default_factory=lambda: [
        "حلويات عربية", "معجنات", "كيك وتورتات", "بسكويت وكوكيز",
        "حلويات باردة", "فطائر ومخبوزات", "حلويات صحية", "أطباق رمضانية"
    ])
    
    MIN_RECIPE_INGREDIENTS: int = 5
    MIN_RECIPE_STEPS: int = 6
    TARGET_WORD_COUNT: int = 1200
    
    # SEO
    PRIMARY_KEYWORDS: List[str] = field(default_factory=lambda: [
        "وصفات طبخ", "حلويات سهلة", "طريقة عمل", "وصفات منزلية",
        "حلويات لذيذة", "مطبخ عربي", "وصفات سريعة"
    ])
    
    META_DESCRIPTION_LENGTH: int = 160
    ENABLE_SCHEMA_MARKUP: bool = True
    
    # Publishing
    PUBLISH_INTERVAL_HOURS: int = int(os.getenv("PUBLISH_INTERVAL_HOURS", "24"))
    AUTO_PUBLISH: bool = os.getenv("AUTO_PUBLISH", "true").lower() == "true"
    DRAFT_MODE: bool = os.getenv("DRAFT_MODE", "false").lower() == "true"
    
    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    CREDENTIALS_PATH: Path = field(init=False)
    DATA_DIR: Path = field(init=False)
    LOG_FILE: str = "zajmil.log"
    PERFORMANCE_FILE: str = "performance.json"
    
    def __post_init__(self):
        self.CREDENTIALS_PATH = self.BASE_DIR / "token.json"
        self.DATA_DIR = self.BASE_DIR / "data"
        self.DATA_DIR.mkdir(exist_ok=True)
    
    def validate(self) -> bool:
        if not self.GEMINI_API_KEY:
            raise ValueError("❌ GEMINI_API_KEY is required")
        if not self.BLOGGER_BLOG_ID:
            raise ValueError("❌ BLOGGER_BLOG_ID is required")
        if not self.BLOGGER_CLIENT_ID or not self.BLOGGER_CLIENT_SECRET:
            raise ValueError("❌ Blogger OAuth credentials required")
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
        <p><strong>الوسوم:</strong> {' '.join(['#' + t for t in self.tags])}</p>
    </div>
</article>

<script type="application/ld+json">
{{
  "@context": "https://schema.org/",
  "@type": "Recipe",
  "name": "{self.title}",
  "description": "{self.description}",
  "prepTime": "PT{self.prep_time}M",
  "cookTime": "PT{self.cook_time}M",
  "recipeYield": "{self.servings} أشخاص",
  "recipeCategory": "{self.category}",
  "recipeIngredient": {json.dumps(self.ingredients, ensure_ascii=False)},
  "recipeInstructions": {json.dumps([{"@type": "HowToStep", "text": s} for s in self.steps], ensure_ascii=False)}
}}
</script>
"""
        return html

# ═══════════════════════════════════════════════════════════════════════════════
# GEMINI AI ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiChefEngine:
    """محرك الذكاء الاصطناعي"""
    
    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            config.GEMINI_MODEL,
            generation_config=genai.types.GenerationConfig(
                temperature=config.GEMINI_TEMPERATURE,
                max_output_tokens=config.GEMINI_MAX_TOKENS,
                top_p=0.95, top_k=40
            )
        )
        logger.info(f"✅ Gemini initialized | Model: {config.GEMINI_MODEL}")
    
    def generate_recipe(self, category: str) -> Optional[Recipe]:
        try:
            logger.info(f"🤖 Generating recipe | Category: {category}")
            
            prompt = f"""أنت شيف محترف متخصص في **{category}** وخبير SEO.

**مهمتك**: إنشاء وصفة حصرية وفريدة في فئة "{category}" باللغة العربية.

**المتطلبات**:
1. الأصالة والإبداع
2. {config.MIN_RECIPE_INGREDIENTS}+ مكونات مفصلة
3. {config.MIN_RECIPE_STEPS}+ خطوات واضحة
4. استخدام كلمات مفتاحية: {', '.join(config.PRIMARY_KEYWORDS[:3])}
5. المحتوى ~{config.TARGET_WORD_COUNT} كلمة

**قالب JSON** (بدون أي نص إضافي):
```json
{{
  "title": "عنوان جذاب يحتوي كلمة مفتاحية",
  "description": "وصف شامل 200-300 كلمة",
  "ingredients": ["مكون 1 مفصل", "مكون 2...", "..."],
  "steps": ["خطوة 1 مفصلة", "خطوة 2...", "..."],
  "prep_time": 30,
  "cook_time": 45,
  "servings": 6,
  "difficulty": "متوسط",
  "meta_description": "وصف مختصر {config.META_DESCRIPTION_LENGTH} حرف",
  "keywords": ["كلمة1", "كلمة2", "..."],
  "tags": ["وسم1", "وسم2", "..."]
}}
```

ابدأ:"""
            
            response = self.model.generate_content(prompt, request_options={"timeout": 60})
            
            if not response or not response.text:
                return None
            
            recipe_data = self._extract_json(response.text)
            if not recipe_data:
                return None
            
            recipe = self._build_recipe(recipe_data, category)
            logger.info(f"✅ Recipe generated: {recipe.title}")
            return recipe
            
        except Exception as e:
            logger.error(f"❌ Generation failed: {e}")
            return None
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        try:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group(0))
            return json.loads(text)
        except:
            return None
    
    def _build_recipe(self, data: Dict, category: str) -> Recipe:
        word_count = (
            len(data.get('description', '').split()) +
            sum(len(i.split()) for i in data.get('ingredients', [])) +
            sum(len(s.split()) for s in data.get('steps', []))
        )
        
        return Recipe(
            title=data.get('title', 'وصفة لذيذة'),
            category=category,
            description=data.get('description', ''),
            ingredients=data.get('ingredients', []),
            steps=data.get('steps', []),
            prep_time=data.get('prep_time', 30),
            cook_time=data.get('cook_time', 45),
            servings=data.get('servings', 4),
            difficulty=data.get('difficulty', 'متوسط'),
            meta_description=data.get('meta_description', data.get('description', '')[:160]),
            keywords=data.get('keywords', []),
            tags=data.get('tags', []),
            word_count=word_count
        )

# ═══════════════════════════════════════════════════════════════════════════════
# SEO OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════════

class SEOOptimizer:
    """محسّن SEO"""
    
    STOP_WORDS = {'في', 'من', 'إلى', 'على', 'عن', 'مع', 'هذا', 'التي', 'أن', 'كان'}
    
    def analyze_recipe(self, recipe: Recipe) -> Dict:
        analysis = {'score': 0.0, 'issues': [], 'recommendations': []}
        
        score = 100.0
        
        # العنوان
        if len(recipe.title) < 30:
            analysis['issues'].append("العنوان قصير")
            score -= 20
        
        title_lower = recipe.title.lower()
        kw_in_title = sum(1 for kw in config.PRIMARY_KEYWORDS if kw in title_lower)
        if kw_in_title == 0:
            analysis['issues'].append("لا كلمات مفتاحية في العنوان")
            score -= 30
        
        # المحتوى
        if recipe.word_count < config.TARGET_WORD_COUNT * 0.7:
            analysis['issues'].append(f"المحتوى قصير ({recipe.word_count})")
            score -= 25
        
        # البنية
        if len(recipe.ingredients) < config.MIN_RECIPE_INGREDIENTS:
            analysis['issues'].append("عدد المكونات قليل")
            score -= 20
        
        if len(recipe.steps) < config.MIN_RECIPE_STEPS:
            analysis['issues'].append("عدد الخطوات قليل")
            score -= 20
        
        # Meta
        if not recipe.meta_description:
            analysis['issues'].append("Meta Description مفقود")
            score -= 30
        
        analysis['score'] = max(score, 0.0)
        recipe.seo_score = analysis['score']
        
        logger.info(f"📊 SEO Score: {analysis['score']:.1f}/100")
        return analysis
    
    def optimize_for_seo(self, recipe: Recipe) -> Recipe:
        if not recipe.meta_description:
            recipe.meta_description = recipe.description[:config.META_DESCRIPTION_LENGTH]
        
        if len(recipe.keywords) < 5:
            recipe.keywords = self._extract_keywords(recipe)
        
        if len(recipe.tags) < 5:
            recipe.tags = self._generate_tags(recipe)
        
        return recipe
    
    def _extract_keywords(self, recipe: Recipe) -> List[str]:
        keywords = []
        full_text = f"{recipe.title} {recipe.description}".lower()
        
        for kw in config.PRIMARY_KEYWORDS:
            if kw in full_text:
                keywords.append(kw)
        
        keywords.append(recipe.category)
        return list(set(keywords))[:10]
    
    def _generate_tags(self, recipe: Recipe) -> List[str]:
        tags = [
            recipe.category.replace(' ', '_'),
            f"وصفات_{recipe.difficulty}",
            "وصفات_منزلية", "طبخ_سهل", "مطبخ_عربي"
        ]
        
        total_time = recipe.prep_time + recipe.cook_time
        if total_time < 30:
            tags.append("وصفات_سريعة")
        
        return tags[:10]

# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ContentValidator:
    """مُدقق الجودة"""
    
    def validate(self, recipe: Recipe) -> Tuple[bool, List[str]]:
        errors = []
        
        if not recipe.title or len(recipe.title) < 10:
            errors.append("العنوان قصير جداً")
        
        if not recipe.description or len(recipe.description) < 50:
            errors.append("الوصف قصير جداً")
        
        if len(recipe.ingredients) < config.MIN_RECIPE_INGREDIENTS:
            errors.append(f"المكونات قليلة ({len(recipe.ingredients)})")
        
        if len(recipe.steps) < config.MIN_RECIPE_STEPS:
            errors.append(f"الخطوات قليلة ({len(recipe.steps)})")
        
        if recipe.prep_time <= 0 or recipe.cook_time <= 0:
            errors.append("الأوقات غير صحيحة")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("✅ Validation passed")
        else:
            logger.error(f"❌ Validation failed: {len(errors)} errors")
        
        return is_valid, errors

# ═══════════════════════════════════════════════════════════════════════════════
# BLOGGER PUBLISHER
# ═══════════════════════════════════════════════════════════════════════════════

class BloggerPublisher:
    """ناشر Blogger"""
    
    def __init__(self):
        self.blog_id = config.BLOGGER_BLOG_ID
        self.credentials = None
        self.service = None
        self._authenticate()
        logger.info("✅ Blogger Publisher initialized")
    
    def _authenticate(self):
        token_path = config.CREDENTIALS_PATH
        
        if token_path.exists():
            try:
                with open(token_path, 'r') as f:
                    token_data = json.load(f)
                    self.credentials = Credentials.from_authorized_user_info(
                        token_data, config.BLOGGER_SCOPES
                    )
            except:
                pass
        
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                except:
                    self.credentials = None
            
            if not self.credentials:
                flow = InstalledAppFlow.from_client_config(
                    {
                        "installed": {
                            "client_id": config.BLOGGER_CLIENT_ID,
                            "client_secret": config.BLOGGER_CLIENT_SECRET,
                            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token"
                        }
                    },
                    config.BLOGGER_SCOPES
                )
                self.credentials = flow.run_local_server(port=0)
            
            with open(token_path, 'w') as f:
                f.write(self.credentials.to_json())
        
        self.service = build('blogger', 'v3', credentials=self.credentials)
    
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
        logger.info("🚀 Initializing Zajmil AI Chef System")
        logger.info("=" * 80)
        
        config.validate()
        
        self.gemini = GeminiChefEngine()
        self.publisher = BloggerPublisher()
        self.seo = SEOOptimizer()
        self.validator = ContentValidator()
        self.analytics = AnalyticsTracker()
        
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
            
            logger.info("=" * 80)
            logger.info("🎉 Workflow completed!")
            logger.info(f"📝 {recipe.title}")
            logger.info(f"🔍 SEO: {seo_analysis['score']:.1f}/100")
            logger.info(f"🔗 {recipe.post_url}")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Workflow failed: {e}")
            return False
    
    def run_continuous(self):
        logger.info(f"\n⏰ Continuous mode | Interval: {config.PUBLISH_INTERVAL_HOURS}h")
        
        while True:
            try:
                success = self.generate_and_publish()
                
                sleep_sec = config.PUBLISH_INTERVAL_HOURS * 3600
                sleep_sec = int(sleep_sec * random.uniform(0.9, 1.1))
                
                logger.info(f"\n😴 Sleeping {sleep_sec/3600:.1f}h...")
                time.sleep(sleep_sec)
                
            except KeyboardInterrupt:
                logger.info("\n⏹️ Stopped")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(3600)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Zajmil AI Chef")
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
            logger.info("📊 Analytics coming soon...")
    
    except KeyboardInterrupt:
        logger.info("\n⏹️ Stopped")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"💥 Fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()