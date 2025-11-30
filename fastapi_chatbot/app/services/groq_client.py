from groq import Groq
from app.config import get_settings
import logging
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)
settings = get_settings()

class GroqClient:
    """Client for Groq API interactions - NEVER logs API key"""
    
    def __init__(self):
        # Read API key from settings (loaded from .env)
        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise ValueError("❌ GROQ_API_KEY not found in environment variables")
        
        self.client = Groq(api_key=api_key)
        self.model = settings.GROQ_MODEL
        logger.info(f"✅ Groq client initialized with model: {self.model}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> str:
        """Generate chat completion using Groq LLM"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            if stream:
                return response  # Return generator for streaming
            
            return response.choices[0].message.content
        
        except Exception as e:
            logger.error(f"❌ Groq API error (details hidden for security): {type(e).__name__}")
            raise
    
    async def generate_answer_with_context(
        self,
        question: str,
        context: str,
        language: str = "en",
        chat_history: Optional[List[Dict]] = None
    ) -> str:
        """Generate answer using RAG pattern with retrieved context"""
        
        system_prompt = self._build_system_prompt(language)
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history if provided (last 3 turns = 6 messages)
        if chat_history:
            messages.extend(chat_history[-6:])
        
        # Build user message with context
        user_message = self._build_rag_prompt(question, context, language)
        messages.append({"role": "user", "content": user_message})
        
        return await self.chat_completion(messages, temperature=0.7, max_tokens=2000)
    
    async def quick_answer(self, question: str, language: str = "en") -> str:
        """Generate quick answer without context"""
        system_prompt = self._build_system_prompt(language)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        
        return await self.chat_completion(messages, temperature=0.7, max_tokens=500)
    
    def _build_system_prompt(self, language: str) -> str:
        """Build system prompt based on detected language"""
        
        if language == "ar":
            return """أنت مساعد ذكي متخصص في معالجة اللغة الطبيعية العربية (Arabic NLP).
مهمتك مساعدة الباحثين والطلاب في:
• فهم مفاهيم ومصطلحات Arabic NLP بشكل واضح ودقيق
• شرح ميزات المنصة وكيفية استخدامها
• توفير معلومات عن الموارد البحثية (مقالات، مشاريع، مؤسسات، بيانات)
• الإجابة على الأسئلة التقنية بطريقة تربوية

قواعد الإجابة:
1. استخدم اللغة العربية الفصحى الواضحة
2. قدم إجابات شاملة ومنظمة
3. اذكر المصادر عندما تكون متاحة
4. إذا لم تكن متأكداً، اذكر ذلك بوضوح
5. استخدم أمثلة عملية عند الحاجة"""
        
        elif language == "fr":
            return """Vous êtes un assistant IA spécialisé en traitement automatique du langage naturel arabe (Arabic NLP).
Votre mission est d'aider les chercheurs et étudiants à:
• Comprendre les concepts et la terminologie Arabic NLP de manière claire et précise
• Expliquer les fonctionnalités de la plateforme et comment les utiliser
• Fournir des informations sur les ressources de recherche (articles, projets, institutions, données)
• Répondre aux questions techniques de manière pédagogique

Règles de réponse:
1. Utilisez un français clair et précis
2. Fournissez des réponses complètes et structurées
3. Citez les sources lorsqu'elles sont disponibles
4. Si vous n'êtes pas certain, indiquez-le clairement
5. Utilisez des exemples pratiques si nécessaire"""
        
        else:  # English
            return """You are an AI assistant specialized in Arabic Natural Language Processing (NLP).
Your mission is to help researchers and students:
• Understand Arabic NLP concepts and terminology clearly and accurately
• Explain platform features and how to use them
• Provide information about research resources (articles, projects, institutions, datasets)
• Answer technical questions in an educational manner

Response rules:
1. Use clear and precise English
2. Provide comprehensive and well-structured answers
3. Cite sources when available
4. If uncertain, state it clearly
5. Use practical examples when helpful"""
    
    def _build_rag_prompt(self, question: str, context: str, language: str) -> str:
        """Build RAG prompt with context"""
        
        if language == "ar":
            return f"""السياق من قاعدة المعرفة:
{context}

السؤال: {question}

قدم إجابة واضحة ودقيقة بناءً على السياق أعلاه. إذا كان السياق لا يجيب بشكل كامل على السؤال، اذكر ذلك وقدم أفضل إجابة عامة لديك."""
        
        elif language == "fr":
            return f"""Contexte de la base de connaissances:
{context}

Question: {question}

Veuillez fournir une réponse claire et précise basée sur le contexte ci-dessus. Si le contexte ne répond pas complètement à la question, indiquez-le et fournissez votre meilleure réponse générale."""
        
        else:
            return f"""Context from knowledge base:
{context}

Question: {question}

Please provide a clear and accurate answer based on the context above. If the context doesn't fully answer the question, state so and provide your best general knowledge answer."""

# Singleton instance
_groq_client = None

def get_groq_client() -> GroqClient:
    """Get or create Groq client instance"""
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client
