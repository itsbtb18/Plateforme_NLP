"""
Example test data for the Research Card UI implementation.

This file contains realistic sample content that demonstrates
how the parser handles various input formats.
"""

# Example 1: Semantic Scholar scraped paper
EXAMPLE_PAPER_1 = """
**Title:** Advanced Natural Language Processing Framework for Arabic Named Entity Recognition

**Authors:** Nada Essa, Mostafa M. El-Gayar, Eman El-Daydamony

**Year:** 2025

**Abstract:** With the rise of Arabic digital content, effective named entity recognition (NER) methods are essential. Current Arabic NER systems face challenges such as language complexity and vocabulary limitations. We introduce an innovative framework using Arabic Named Entity Recognition to enhance abstractive summarization, crucial for NLP applications like question answering and knowledge graph construction. Our model, based on natural language generation techniques, adapts to diverse datasets. It identifies key information, synthesizes it into coherent summaries, and ensures grammatical accuracy through deep learning. Evaluated on the EASC dataset, our model achieved a 74% ROUGE-1 score and a 97.6% accuracy in semantic coherence, with high readability and relevance scores. This sets a new standard for Arabic text summarization, greatly improving NLP information processing.

[Read the full paper](https://www.semanticscholar.org/paper/8f3b8bd4d453be41f115b495d641dedb86b5a1d2)
"""

# Example 2: Google Scholar style
EXAMPLE_PAPER_2 = """
**Title:** Machine learning and deep learning techniques in Arabic question answering systems

**Authors:** AI Research Team, Cairo University

**Year:** 2024

**Abstract:** Recent advances in machine learning and deep learning have revolutionized question answering systems. This survey examines state-of-the-art techniques specifically designed for Arabic language processing. We analyze transformer-based models, attention mechanisms, and fine-tuning strategies for Arabic QA tasks.

[Paper on ArXiv](https://arxiv.org/abs/2401.56789)
"""

# Example 3: Minimal format (authors and abstract only)
EXAMPLE_PAPER_3 = """
**Authors:** Dr. Fatima Al-Mansouri, Prof. Mohammed Hassan

**Year:** 2025

**Abstract:** This research explores the intersection of sentiment analysis and aspect-based opinion mining in Arabic social media. Using transformer models and contextual embeddings, we achieved 89% accuracy on our custom dataset. The work contributes to better understanding public discourse in Arab society.
"""

# Example 4: Plain URL without markdown
EXAMPLE_PAPER_4 = """
**Authors:** Academic Team

**Year:** 2025

**Abstract:** Our latest findings on morphological analysis of Arabic dialects. Full paper available at https://university.edu/research/2025/morphology-analysis.pdf
"""

# Example 5: News article style
EXAMPLE_NEWS_1 = """
**Title:** Breakthrough in Arabic Artificial Intelligence Research

**Authors:** Technology News Team

**Year:** 2025

**Abstract:** Scientists at leading research institutions have achieved a major milestone in Arabic language AI. The new system can understand dialectal variations and cultural context with unprecedented accuracy, opening doors for better machine translation, chatbots, and information retrieval systems specifically designed for Arabic speakers.
"""

# Example 6: Blog post format
EXAMPLE_BLOG_POST = """
**Title:** Understanding Modern NLP Approaches for Understaffed Languages

**Authors:** Dr. Ahmed Hassan, Tech Blogger

**Year:** 2025

**Abstract:** In this article, we discuss how modern NLP techniques can be adapted for low-resource languages like Arabic. We cover transformer architectures, data augmentation strategies, and practical implementation tips. Read our complete guide on Medium.

[Full article](https://medium.com/@techblog/nlp-arabic)
"""

# Example 7: Malformed/incomplete content (tests fallback)
EXAMPLE_INCOMPLETE = """
Some content without proper formatting.
This should still display in the abstract section.
"""

# Example 8: Multiple sections
EXAMPLE_STRUCTURED = """
**Title:** Comprehensive Arabic NLP Framework

**Authors:** Research Team A, Research Team B, Research Team C

**Year:** 2024

**Abstract:** A comprehensive framework for Arabic natural language processing combining multiple state-of-the-art techniques.

**Introduction:** The introduction covers the importance of Arabic NLP.

**Methodology:** We employed transformer models and custom embeddings.

**Results:** Achieved 92% accuracy on benchmark datasets.

[Full Paper](https://example.com/paper.pdf)
"""

# Test cases
PARSER_TEST_CASES = [
    ("Example 1: Semantic Scholar Paper", EXAMPLE_PAPER_1),
    ("Example 2: Google Scholar Style", EXAMPLE_PAPER_2),
    ("Example 3: Minimal Format", EXAMPLE_PAPER_3),
    ("Example 4: Plain URL", EXAMPLE_PAPER_4),
    ("Example 5: News Article", EXAMPLE_NEWS_1),
    ("Example 6: Blog Post", EXAMPLE_BLOG_POST),
    ("Example 7: Incomplete Content", EXAMPLE_INCOMPLETE),
    ("Example 8: Structured Format", EXAMPLE_STRUCTURED),
]


def test_parser():
    """
    Test the parser with all example content.
    
    Usage:
    ```
    python manage.py shell
    >>> from test_data import test_parser
    >>> test_parser()
    ```
    """
    from pages.content_parser import extract_structured_content
    
    print("\n" + "="*70)
    print("RESEARCH CARD PARSER - TEST RESULTS")
    print("="*70 + "\n")
    
    for test_name, content in PARSER_TEST_CASES:
        print(f"📋 {test_name}")
        print("-" * 70)
        
        try:
            result = extract_structured_content(content)
            
            print(f"  ✓ Title:    {result['title'] or '(none)'}")
            print(f"  ✓ Authors:  {result['authors'] or '(none)'}")
            print(f"  ✓ Year:     {result['year'] or '(none)'}")
            print(f"  ✓ Link:     {result['link'] or '(none)'}")
            print(f"  ✓ Abstract: {(result['abstract'][:60] + '...') if result['abstract'] else '(none)'}")
            
        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
        
        print()
    
    print("="*70)
    print("All tests completed!")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_parser()
