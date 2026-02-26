"""
Ingestion script for NLP foundational resources.

Adds comprehensive NLP knowledge entries (textbooks, papers, tools, metrics)
to PostgreSQL + Qdrant for RAG retrieval.
"""
import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db import AsyncSessionLocal
from app.models import NLPKnowledge
from app.services.documents.embeddings import get_embedding_service
from app.services.qdrant import get_qdrant_service, COLLECTION_NLP_KNOWLEDGE
from qdrant_client.models import PointStruct
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NLP_RESOURCES = [
    # ── 1. NLP Foundations ──────────────────────────────────────────
    {
        "topic": "Speech and Language Processing (Jurafsky & Martin)",
        "language": "en",
        "content": (
            "Speech and Language Processing by Dan Jurafsky and James H. Martin "
            "is the definitive textbook for NLP and computational linguistics (3rd edition, 2026).\n\n"
            "The book is organized into two volumes:\n\n"
            "Volume I — Large Language Models:\n"
            "1. Introduction\n"
            "2. Words and Tokens — tokenization, byte-pair encoding, Unicode\n"
            "3. N-gram Language Models — probability, smoothing, perplexity\n"
            "4. Logistic Regression and Text Classification — sentiment, spam detection\n"
            "5. Embeddings — word2vec, GloVe, contextual embeddings\n"
            "6. Neural Networks — feedforward, backpropagation, dropout\n"
            "7. Large Language Models — GPT, scaling laws, in-context learning\n"
            "8. Transformers — self-attention, multi-head attention, positional encoding\n"
            "9. Post-training: Instruction Tuning, Alignment (RLHF, DPO), Test-Time Compute\n"
            "10. Masked Language Models — BERT, RoBERTa, fine-tuning\n"
            "11. Information Retrieval and Retrieval-Augmented Generation (RAG)\n"
            "12. Machine Translation — encoder-decoder, BLEU evaluation\n"
            "13. RNNs and LSTMs — sequence modeling, vanishing gradients\n"
            "14. Phonetics and Speech Feature Extraction\n"
            "15. Automatic Speech Recognition (ASR)\n"
            "16. Text-to-Speech (TTS)\n\n"
            "Volume II — Annotating Linguistic Structure:\n"
            "17. Sequence Labeling — POS tagging, Named Entity Recognition\n"
            "18. Context-Free Grammars and Constituency Parsing\n"
            "19. Dependency Parsing\n"
            "20. Information Extraction — relations, events, time\n"
            "21. Semantic Role Labeling\n"
            "22. Lexicons for Sentiment, Affect, and Connotation\n"
            "23. Coreference Resolution and Entity Linking\n"
            "24. Discourse Coherence\n"
            "25. Conversation and its Structure\n\n"
            "Free online: https://web.stanford.edu/~jurafsky/slp3/\n"
            "This is the most recommended textbook for learning NLP from fundamentals to modern LLMs."
        ),
        "keywords": [
            "textbook", "NLP", "Jurafsky", "Martin", "speech", "language processing",
            "transformers", "LLM", "embeddings", "parsing", "NER", "POS",
        ],
        "difficulty": "beginner",
    },
    # ── 2. Transformers / Modern NLP ────────────────────────────────
    {
        "topic": "Attention Is All You Need — The Transformer Architecture",
        "language": "en",
        "content": (
            "\"Attention Is All You Need\" (Vaswani et al., 2017) is the foundational paper "
            "that introduced the Transformer architecture, which revolutionized NLP.\n\n"
            "Key Contributions:\n"
            "- Replaced recurrence (RNNs) and convolutions entirely with self-attention\n"
            "- Introduced multi-head attention: allows the model to attend to information "
            "from different representation subspaces at different positions\n"
            "- Introduced positional encoding: sine/cosine functions to inject sequence order\n"
            "- Encoder-decoder architecture with 6 layers each\n"
            "- Scaled dot-product attention: Q·K^T / sqrt(d_k)\n\n"
            "Architecture Components:\n"
            "1. Input Embedding + Positional Encoding\n"
            "2. Encoder: Multi-Head Self-Attention → Add & Norm → Feed-Forward → Add & Norm\n"
            "3. Decoder: Masked Multi-Head Self-Attention → Cross-Attention → Feed-Forward\n"
            "4. Output: Linear layer + Softmax\n\n"
            "Results:\n"
            "- 28.4 BLEU on WMT 2014 English-to-German (new SOTA)\n"
            "- 41.8 BLEU on WMT 2014 English-to-French (new single-model SOTA)\n"
            "- Trained in 3.5 days on 8 GPUs (fraction of previous costs)\n"
            "- More parallelizable than RNNs, enabling larger models\n\n"
            "Why it matters: Every modern LLM (GPT, BERT, LLaMA, T5, etc.) is based on this architecture.\n\n"
            "Paper: https://arxiv.org/abs/1706.03762\n"
            "Authors: Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, "
            "Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin"
        ),
        "keywords": [
            "transformer", "attention", "self-attention", "multi-head",
            "positional encoding", "encoder-decoder", "Vaswani", "architecture",
        ],
        "difficulty": "intermediate",
    },
    {
        "topic": "BERT — Pre-training of Deep Bidirectional Transformers",
        "language": "en",
        "content": (
            "BERT (Bidirectional Encoder Representations from Transformers) by Devlin et al. (2018) "
            "introduced a paradigm shift in NLP: pre-train a deep bidirectional model, then fine-tune "
            "with one additional layer for any downstream task.\n\n"
            "Key Innovations:\n"
            "1. Bidirectional Pre-training: Unlike GPT (left-to-right), BERT conditions on BOTH "
            "left and right context simultaneously in all layers\n"
            "2. Masked Language Modeling (MLM): Randomly masks 15% of tokens and predicts them — "
            "forces the model to learn deep bidirectional representations\n"
            "3. Next Sentence Prediction (NSP): Binary classification of whether sentence B follows A\n\n"
            "Architecture:\n"
            "- BERT-Base: 12 layers, 768 hidden, 12 heads, 110M parameters\n"
            "- BERT-Large: 24 layers, 1024 hidden, 16 heads, 340M parameters\n"
            "- Uses WordPiece tokenization (30K vocab)\n"
            "- Special tokens: [CLS] for classification, [SEP] for segment separation, [MASK]\n\n"
            "Fine-tuning Tasks:\n"
            "- Sentence classification (e.g., sentiment analysis)\n"
            "- Token classification (e.g., NER)\n"
            "- Question answering (SQuAD)\n"
            "- Sentence pair classification (e.g., NLI)\n\n"
            "Results: SOTA on 11 NLP tasks including GLUE (80.5%), SQuAD v1.1 (93.2 F1), "
            "SQuAD v2.0 (83.1 F1)\n\n"
            "Arabic BERT variants: AraBERT, CAMeL-BERT, AraELECTRA, MARBERT\n\n"
            "Paper: https://arxiv.org/abs/1810.04805\n"
            "Authors: Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova"
        ),
        "keywords": [
            "BERT", "pre-training", "fine-tuning", "masked language model", "MLM",
            "bidirectional", "embeddings", "NER", "QA", "classification", "AraBERT",
        ],
        "difficulty": "intermediate",
    },
    # ── 3. RAG / Retrieval ──────────────────────────────────────────
    {
        "topic": "Retrieval-Augmented Generation (RAG)",
        "language": "en",
        "content": (
            "Retrieval-Augmented Generation (RAG) by Lewis et al. (2020, NeurIPS) combines "
            "pre-trained parametric memory (a seq2seq LLM) with non-parametric memory "
            "(a dense vector index of documents) for knowledge-intensive NLP tasks.\n\n"
            "Core Idea:\n"
            "Instead of storing all knowledge in model parameters, RAG retrieves relevant "
            "documents at inference time and conditions the generation on them. This allows:\n"
            "- Access to up-to-date knowledge without retraining\n"
            "- Provenance: the model can cite which documents it used\n"
            "- More factual and specific outputs\n\n"
            "RAG Architecture:\n"
            "1. Query Encoder: Encodes the input question into a dense vector\n"
            "2. Document Index: Pre-encoded document passages stored as vectors (e.g., FAISS, Qdrant)\n"
            "3. Retriever: Finds the top-k most relevant documents via Maximum Inner Product Search (MIPS)\n"
            "4. Generator: Seq2seq model (e.g., BART) generates output conditioned on question + retrieved docs\n\n"
            "Two Formulations:\n"
            "- RAG-Sequence: Same retrieved documents for the entire generated sequence\n"
            "- RAG-Token: Can use different documents per generated token (more flexible)\n\n"
            "Applications:\n"
            "- Open-domain question answering\n"
            "- Fact verification\n"
            "- Knowledge-grounded dialogue\n"
            "- Chatbots with domain-specific knowledge\n\n"
            "Modern RAG Stack (2024+):\n"
            "- Embedding models: sentence-transformers, OpenAI embeddings\n"
            "- Vector stores: Qdrant, Pinecone, Weaviate, FAISS, Chroma\n"
            "- LLMs: GPT-4, LLaMA, Mistral, Groq\n"
            "- Frameworks: LangChain, LlamaIndex\n\n"
            "Paper: https://arxiv.org/abs/2005.11401\n"
            "Authors: Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, et al."
        ),
        "keywords": [
            "RAG", "retrieval-augmented generation", "vector search", "Qdrant",
            "FAISS", "embedding", "knowledge base", "chatbot", "LLM", "retriever",
        ],
        "difficulty": "advanced",
    },
    {
        "topic": "Dense Passage Retrieval (DPR) for Open-Domain QA",
        "language": "en",
        "content": (
            "Dense Passage Retrieval (DPR) by Karpukhin et al. (2020, EMNLP) demonstrated that "
            "dense vector representations can outperform traditional sparse retrieval (TF-IDF, BM25) "
            "for open-domain question answering.\n\n"
            "Key Idea:\n"
            "Learn two separate BERT encoders — one for questions, one for passages — so that "
            "relevant question-passage pairs have high dot-product similarity in embedding space.\n\n"
            "Architecture:\n"
            "1. Question Encoder E_Q(q): Maps a question to a d-dimensional vector\n"
            "2. Passage Encoder E_P(p): Maps a passage to a d-dimensional vector\n"
            "3. Similarity: sim(q, p) = E_Q(q) · E_P(p) (dot product)\n"
            "4. Training: Contrastive loss — push relevant pairs together, irrelevant apart\n"
            "5. Retrieval: FAISS index for approximate nearest neighbor search\n\n"
            "Hard Negative Mining:\n"
            "- BM25 negatives: passages that BM25 ranked high but are not relevant\n"
            "- In-batch negatives: other passages in the same training batch\n\n"
            "Results:\n"
            "- Outperforms BM25 by 9-19% in top-20 passage retrieval accuracy\n"
            "- Establishes new SOTA on Natural Questions, TriviaQA, WebQuestions\n\n"
            "Why it matters for RAG:\n"
            "- DPR is the retrieval backbone for many RAG systems\n"
            "- Concept of dual-encoder is used in modern embedding models (sentence-transformers)\n"
            "- Understanding embeddings is crucial for building vector search systems\n\n"
            "Paper: https://arxiv.org/abs/2004.04906\n"
            "Authors: Vladimir Karpukhin, Barlas Oguz, Sewon Min, Patrick Lewis, et al."
        ),
        "keywords": [
            "DPR", "dense retrieval", "passage retrieval", "embeddings",
            "BERT encoder", "FAISS", "vector search", "similarity", "BM25",
            "contrastive learning", "open-domain QA",
        ],
        "difficulty": "advanced",
    },
    # ── 5. Evaluation Metrics ───────────────────────────────────────
    {
        "topic": "BLEU Score — Automatic Evaluation of Machine Translation",
        "language": "en",
        "content": (
            "BLEU (Bilingual Evaluation Understudy) is the most widely used automatic "
            "metric for evaluating machine translation quality. Introduced by Papineni et al. (2002).\n\n"
            "How BLEU Works:\n"
            "1. Computes precision of n-grams (1-gram to 4-gram) between candidate and reference translations\n"
            "2. Uses modified precision: clips n-gram counts to avoid rewarding repetition\n"
            "3. Applies a brevity penalty (BP) to punish outputs shorter than the reference\n"
            "4. Final score: BP × exp(Σ wn × log(pn)) where wn = 1/N (uniform weights)\n\n"
            "BLEU Score Range: 0 to 1 (often reported as 0-100)\n"
            "- 0.60+ : Very high quality (usually only with domain-specific systems)\n"
            "- 0.40-0.60 : High quality translation\n"
            "- 0.20-0.40 : Understandable but with errors\n"
            "- < 0.20 : Poor quality\n\n"
            "Limitations:\n"
            "- Only measures surface-level similarity\n"
            "- Doesn't capture meaning or fluency well\n"
            "- Penalizes valid paraphrases\n"
            "- Not suitable for single-sentence evaluation\n\n"
            "Paper: https://aclanthology.org/P02-1040/\n"
            "Authors: Kishore Papineni, Salim Roukos, Todd Ward, Wei-Jing Zhu"
        ),
        "keywords": [
            "BLEU", "evaluation", "metrics", "machine translation", "n-gram",
            "precision", "brevity penalty", "MT evaluation",
        ],
        "difficulty": "intermediate",
    },
    {
        "topic": "NLP Evaluation Metrics — ROUGE, F1, Perplexity and More",
        "language": "en",
        "content": (
            "A comprehensive overview of NLP evaluation metrics:\n\n"
            "ROUGE (Recall-Oriented Understudy for Gisting Evaluation):\n"
            "- ROUGE-N: N-gram recall between generated and reference text\n"
            "- ROUGE-L: Longest Common Subsequence (LCS) based\n"
            "- ROUGE-W: Weighted LCS (consecutive matches get higher weight)\n"
            "- Main use: summarization evaluation\n\n"
            "F1 Score:\n"
            "- Harmonic mean of precision and recall: 2 × (P × R) / (P + R)\n"
            "- Token-level F1: used in extractive QA (SQuAD)\n"
            "- Macro-F1: average F1 across all classes\n"
            "- Micro-F1: global precision/recall across all instances\n\n"
            "Exact Match (EM):\n"
            "- Binary: 1 if prediction exactly matches ground truth, 0 otherwise\n"
            "- Used in QA evaluation alongside F1\n\n"
            "Perplexity (PPL):\n"
            "- Measures how well a language model predicts a text: PPL = exp(-1/N × Σ log P(wi))\n"
            "- Lower is better — a well-trained LM assigns high probability to real text\n"
            "- Used for evaluating language models (GPT, BERT)\n\n"
            "BERTScore:\n"
            "- Uses contextual embeddings (BERT) to compute similarity\n"
            "- More semantic than surface-level metrics like BLEU/ROUGE\n\n"
            "METEOR:\n"
            "- Considers synonyms, stemming, and word order\n"
            "- Better correlation with human judgment than BLEU for some tasks\n\n"
            "HuggingFace Evaluate library: https://huggingface.co/docs/evaluate/index\n"
            "Provides easy-to-use implementations of all these metrics with `evaluate.load('metric_name')`."
        ),
        "keywords": [
            "ROUGE", "F1", "perplexity", "BERTScore", "METEOR", "evaluation",
            "metrics", "accuracy", "precision", "recall", "summarization", "QA",
        ],
        "difficulty": "intermediate",
    },
    # ── 6. Practical Modern Docs ────────────────────────────────────
    {
        "topic": "HuggingFace Transformers Library",
        "language": "en",
        "content": (
            "HuggingFace Transformers is the central model-definition framework for "
            "state-of-the-art machine learning models in NLP, vision, audio, and multimodal tasks.\n\n"
            "Key Features:\n"
            "1. Pipeline API: Simple, optimized inference for text generation, classification, "
            "NER, QA, summarization, translation, image segmentation, ASR, etc.\n"
            "2. Trainer: Comprehensive training with mixed precision, torch.compile, FlashAttention, "
            "distributed training (FSDP, DeepSpeed)\n"
            "3. Generate: Fast text generation with streaming and multiple decoding strategies\n\n"
            "Core Classes:\n"
            "- AutoModel / AutoModelForXxx: Load any model architecture\n"
            "- AutoTokenizer: Load the matching tokenizer\n"
            "- AutoConfig: Model configuration\n"
            "- Pipeline: High-level inference API\n\n"
            "Common Usage:\n"
            "```python\n"
            "from transformers import pipeline\n"
            "# Sentiment analysis\n"
            "classifier = pipeline('sentiment-analysis')\n"
            "result = classifier('I love NLP!')\n"
            "# Text generation\n"
            "generator = pipeline('text-generation', model='gpt2')\n"
            "text = generator('NLP is', max_length=50)\n"
            "# Named Entity Recognition\n"
            "ner = pipeline('ner', aggregation_strategy='simple')\n"
            "entities = ner('Hugging Face is based in New York')\n"
            "```\n\n"
            "Over 1M+ model checkpoints available on the HuggingFace Hub.\n"
            "Compatible with: vLLM, SGLang, TGI, llama.cpp, MLX, Axolotl, Unsloth, DeepSpeed.\n\n"
            "Documentation: https://huggingface.co/docs/transformers/index\n"
            "HuggingFace LLM Course: https://huggingface.co/learn/llm-course/"
        ),
        "keywords": [
            "HuggingFace", "transformers", "pipeline", "Trainer", "fine-tuning",
            "AutoModel", "tokenizer", "inference", "NER", "classification",
            "text generation", "library", "Python",
        ],
        "difficulty": "beginner",
    },
    {
        "topic": "Sentence Transformers (SBERT) — Embeddings and Semantic Search",
        "language": "en",
        "content": (
            "Sentence Transformers (SBERT) is the go-to Python library for computing "
            "text embeddings and building semantic search systems.\n\n"
            "Three Model Types:\n"
            "1. Sentence Transformer models: Compute dense embeddings for sentences/paragraphs\n"
            "2. Cross-Encoder (reranker) models: Score query-document pairs for reranking\n"
            "3. Sparse Encoder models: Generate sparse embeddings (like SPLADE)\n\n"
            "Key Capabilities:\n"
            "- Semantic search: Find similar texts by embedding similarity\n"
            "- Semantic textual similarity (STS): Compare sentence meanings\n"
            "- Paraphrase mining: Find paraphrases in large text collections\n"
            "- Clustering: Group similar texts together\n"
            "- Information retrieval: Build search engines with embeddings\n\n"
            "Usage Example:\n"
            "```python\n"
            "from sentence_transformers import SentenceTransformer\n"
            "model = SentenceTransformer('all-MiniLM-L6-v2')\n"
            "sentences = ['The weather is lovely today.', 'It is so sunny outside!']\n"
            "embeddings = model.encode(sentences)\n"
            "similarities = model.similarity(embeddings, embeddings)\n"
            "```\n\n"
            "Popular Models:\n"
            "- all-MiniLM-L6-v2: Fast, good quality (384 dim)\n"
            "- all-mpnet-base-v2: Higher quality (768 dim)\n"
            "- paraphrase-multilingual-mpnet-base-v2: Multilingual (768 dim, 50+ languages)\n"
            "- BGE, GTE, E5: State-of-the-art embedding families\n\n"
            "Over 10,000 pre-trained models available on HuggingFace Hub.\n"
            "Essential for building RAG systems — this is how documents get encoded into vectors "
            "for retrieval from vector databases like Qdrant, FAISS, Pinecone.\n\n"
            "Documentation: https://www.sbert.net/\n"
            "Citation: Reimers & Gurevych (2019), \"Sentence-BERT: Sentence Embeddings "
            "using Siamese BERT-Networks\""
        ),
        "keywords": [
            "sentence-transformers", "SBERT", "embeddings", "semantic search",
            "similarity", "vector", "paraphrase", "multilingual", "RAG",
            "Qdrant", "FAISS", "reranker", "cross-encoder",
        ],
        "difficulty": "intermediate",
    },
    # ── Bonus: Practical RAG concepts ───────────────────────────────
    {
        "topic": "Building a RAG System — Practical Architecture Guide",
        "language": "en",
        "content": (
            "A practical guide to building Retrieval-Augmented Generation (RAG) systems:\n\n"
            "Step 1 — Document Ingestion:\n"
            "- Load documents (PDF, HTML, text, database records)\n"
            "- Chunk documents into passages (500-1000 tokens recommended)\n"
            "- Chunking strategies: fixed-size, sentence-boundary, recursive, semantic\n"
            "- Generate embeddings for each chunk using a sentence-transformer model\n"
            "- Store embeddings in a vector database (Qdrant, FAISS, Pinecone, Chroma)\n\n"
            "Step 2 — Retrieval:\n"
            "- Encode the user query with the same embedding model\n"
            "- Perform approximate nearest neighbor (ANN) search in the vector database\n"
            "- Retrieve top-k most similar chunks (typically k=3 to 10)\n"
            "- Optional: Rerank results with a cross-encoder for higher precision\n"
            "- Filter by metadata (language, source type, date, access level)\n\n"
            "Step 3 — Generation:\n"
            "- Build a prompt: system instructions + retrieved context + user question\n"
            "- Send to an LLM (GPT-4, LLaMA, Groq, Mistral)\n"
            "- The LLM generates an answer grounded in the retrieved context\n"
            "- Include source citations in the response\n\n"
            "Step 4 — Evaluation:\n"
            "- Retrieval quality: Hit Rate, MRR, nDCG\n"
            "- Answer quality: RAGAS, faithfulness, relevance\n"
            "- End-to-end: human evaluation, user satisfaction\n\n"
            "Common Pitfalls:\n"
            "- Too large/small chunks → poor retrieval quality\n"
            "- Wrong embedding model → semantic mismatch\n"
            "- Low similarity threshold → noisy context\n"
            "- Overly restrictive prompts → parrot-like answers\n"
            "- No reranking → mediocre precision\n\n"
            "Tech Stack Example:\n"
            "- Embedding: paraphrase-multilingual-mpnet-base-v2\n"
            "- Vector DB: Qdrant\n"
            "- LLM: Groq (llama-3.3-70b-versatile)\n"
            "- Backend: FastAPI + PostgreSQL\n"
            "- Frontend: Django with WebSocket/REST"
        ),
        "keywords": [
            "RAG", "architecture", "chunking", "embedding", "vector database",
            "retrieval", "prompt engineering", "LLM", "Qdrant", "FAISS",
            "pipeline", "ingestion", "evaluation",
        ],
        "difficulty": "advanced",
    },
]


async def ingest_nlp_resources():
    """Ingest NLP resource knowledge into PostgreSQL + Qdrant."""
    embedding_service = get_embedding_service()
    qdrant = get_qdrant_service()
    qdrant.ensure_collections()

    async with AsyncSessionLocal() as db:
        logger.info("Starting NLP resources ingestion (%d entries)...", len(NLP_RESOURCES))
        points: list[PointStruct] = []

        for kd in NLP_RESOURCES:
            text = f"{kd['topic']}\n{kd['content']}"
            embedding = embedding_service.encode_single(text)

            entry = NLPKnowledge(
                topic=kd["topic"],
                language=kd["language"],
                content=kd["content"],
                keywords=kd["keywords"],
                difficulty=kd["difficulty"],
            )
            db.add(entry)
            await db.flush()

            points.append(
                PointStruct(
                    id=entry.id,
                    vector=embedding,
                    payload={
                        "type": "nlp_knowledge",
                        "language": entry.language,
                        "difficulty": entry.difficulty or "",
                    },
                )
            )
            logger.info("✅ Added: %s (id=%d)", entry.topic, entry.id)

        await db.commit()
        qdrant.upsert_batch(COLLECTION_NLP_KNOWLEDGE, points)
        logger.info("🎉 Ingested %d NLP resource entries", len(NLP_RESOURCES))


if __name__ == "__main__":
    asyncio.run(ingest_nlp_resources())
