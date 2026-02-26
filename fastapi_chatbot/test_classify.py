"""Test query classification for the three reported queries."""
from app.services.classifier import get_query_classifier
from app.services.classifier.patterns import extract_resource_type

clf = get_query_classifier()

queries = [
    "give me all the tools created by me",
    "give me all the tools of the plateform",
    "give me all the resources here in the plateform",
    "my tools",
    "show me the courses",
    "list all tools",
    "what tools did i create",
    "tools i shared",
]

for q in queries:
    r = clf.classify(q)
    rt = extract_resource_type(q)
    print("Q: '%s'" % q)
    print("  intent=%s  confidence=%.2f  resource_type=%s  extract_rt=%s" % (
        r.intent, r.confidence, r.detected_resource_type, rt
    ))
    print()
