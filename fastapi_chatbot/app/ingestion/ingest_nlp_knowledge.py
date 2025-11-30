"""
Ingestion script for Arabic NLP knowledge base
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db import AsyncSessionLocal
from app.models import NLPKnowledge
from app.services.embeddings import get_embedding_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Arabic NLP knowledge base
NLP_KNOWLEDGE = [
    {
        "topic": "Arabic Stemming",
        "language": "en",
        "content": """Stemming is the process of reducing Arabic words to their root form (stem).
Arabic stemming is challenging due to:
- Rich morphology with prefixes, suffixes, and infixes
- Derivational and inflectional morphology
- Agglutinative nature

Common stemming algorithms:
1. Light Stemming: Removes common prefixes/suffixes (Al-, -at, -un)
2. Root-based Stemming: Extracts tri-literal/quad-literal roots
3. Khoja Stemmer: Popular root-based stemmer
4. ISRI Stemmer: Information Science Research Institute stemmer

Applications:
- Information retrieval
- Text classification
- Machine translation""",
        "keywords": ["stemming", "morphology", "root", "Arabic"],
        "difficulty": "intermediate"
    },
    {
        "topic": "الجذعنة العربية (Stemming)",
        "language": "ar",
        "content": """الجذعنة هي عملية تحويل الكلمات العربية إلى جذورها الأساسية.
تحديات الجذعنة العربية:
- الصرف الغني بالسوابق واللواحق والحشوات
- الصرف الاشتقاقي والتصريفي
- الطبيعة الإلصاقية

خوارزميات الجذعنة الشائعة:
1. الجذعنة الخفيفة: إزالة السوابق/اللواحق الشائعة (ال-، -ات، -ون)
2. الجذعنة القائمة على الجذر: استخراج الجذور الثلاثية/الرباعية
3. خوجة (Khoja): جذعنة شائعة قائمة على الجذر
4. ISRI: جذعنة معهد بحوث علوم المعلومات

التطبيقات:
- استرجاع المعلومات
- تصنيف النصوص
- الترجمة الآلية""",
        "keywords": ["جذعنة", "صرف", "جذر", "عربي"],
        "difficulty": "intermediate"
    },
    {
        "topic": "Named Entity Recognition (NER) for Arabic",
        "language": "en",
        "content": """NER identifies and classifies named entities in Arabic text.

Entity types:
- Person names (PERSON)
- Locations (LOCATION)
- Organizations (ORGANIZATION)
- Dates/Times (DATE, TIME)
- Monetary values (MONEY)

Challenges for Arabic NER:
- Lack of capitalization
- Name ambiguity
- Dialect variations
- Limited annotated corpora

Approaches:
1. Rule-based: Gazetteers, patterns
2. Machine Learning: CRF, SVM
3. Deep Learning: BiLSTM-CRF, BERT (AraBERT, CAMeL BERT)

Tools:
- CAMeL Tools
- Stanford NER
- spaCy with Arabic models""",
        "keywords": ["NER", "entities", "Arabic", "BERT"],
        "difficulty": "advanced"
    },
    {
        "topic": "Arabic Diacritization",
        "language": "en",
        "content": """Diacritization adds vowel marks (diacritics) to Arabic text.

Arabic diacritics:
- Fatha (َ): Short 'a' sound
- Damma (ُ): Short 'u' sound
- Kasra (ِ): Short 'i' sound
- Sukun (ْ): No vowel
- Shadda (ّ): Gemination
- Tanwin: Nunation marks

Importance:
- Resolves ambiguity
- Essential for TTS and ASR
- Helps learners
- Improves machine translation

Methods:
1. Rule-based: Morphological analysis
2. Statistical: HMM, CRF
3. Neural: RNN, Transformer models

State-of-the-art:
- Shakkala
- Mishkal
- Farasa""",
        "keywords": ["diacritization", "tashkeel", "harakat", "vowels"],
        "difficulty": "intermediate"
    },
    {
        "topic": "التشكيل العربي (Arabic Diacritization)",
        "language": "ar",
        "content": """التشكيل يضيف علامات الحركات للنص العربي.

الحركات العربية:
- الفتحة (َ): صوت 'a' قصير
- الضمة (ُ): صوت 'u' قصير
- الكسرة (ِ): صوت 'i' قصير
- السكون (ْ): بدون حركة
- الشدة (ّ): تضعيف
- التنوين: نون ساكنة

الأهمية:
- حل الغموض اللغوي
- ضروري لتحويل النص إلى كلام
- مساعدة المتعلمين
- تحسين الترجمة الآلية

الطرق:
1. قائمة على القواعد: تحليل صرفي
2. إحصائية: HMM, CRF
3. عصبية: RNN, Transformer

أحدث الأدوات:
- شكّلة
- مشكال
- فرسا""",
        "keywords": ["تشكيل", "حركات", "ضبط", "تطويع"],
        "difficulty": "intermediate"
    },
    {
        "topic": "Arabic Word Embeddings",
        "language": "en",
        "content": """Word embeddings are dense vector representations of words.

Types:
1. Static embeddings:
   - Word2Vec (Skip-gram, CBOW)
   - GloVe
   - FastText (handles morphology well)

2. Contextual embeddings:
   - AraBERT
   - CAMeL BERT
   - AraGPT
   - mBERT (multilingual)

Pretrained Arabic models:
- AraBERT v1/v2
- CAMeL-BERT (MSA, dialects)
- AraELECTRA
- MARBERT

Training corpora:
- Arabic Wikipedia
- OSIAN
- Arabic Gigaword
- Common Crawl

Applications:
- Semantic similarity
- Text classification
- Machine translation
- Question answering""",
        "keywords": ["embeddings", "BERT", "word2vec", "vectors"],
        "difficulty": "advanced"
    }
]

async def ingest_nlp_knowledge():
    """Ingest NLP knowledge base with embeddings"""
    embedding_service = get_embedding_service()
    
    async with AsyncSessionLocal() as db:
        logger.info("🚀 Starting NLP knowledge ingestion...")
        
        for knowledge_data in NLP_KNOWLEDGE:
            # Generate embedding
            text_for_embedding = f"{knowledge_data['topic']} {knowledge_data['content']}"
            embedding = embedding_service.encode_single(text_for_embedding)
            
            # Create knowledge entry
            knowledge = NLPKnowledge(
                topic=knowledge_data['topic'],
                language=knowledge_data['language'],
                content=knowledge_data['content'],
                keywords=knowledge_data['keywords'],
                difficulty=knowledge_data['difficulty'],
                embedding=embedding
            )
            
            db.add(knowledge)
            logger.info(f"✅ Added: {knowledge_data['topic']}")
        
        await db.commit()
        logger.info(f"🎉 Ingested {len(NLP_KNOWLEDGE)} knowledge entries")

if __name__ == "__main__":
    asyncio.run(ingest_nlp_knowledge())
