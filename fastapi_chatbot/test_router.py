"""Test router helpers."""


def main() -> None:
    from app.services.router.engine import QueryRouter

    r = QueryRouter()

    queries = [
        "give me all the tools created by me",
        "give me all the tools of the plateform",
        "give me all the resources here in the plateform",
    ]

    for q in queries:
        ct = r._extract_content_type(q)
        ident = r._is_identity_question(q)
        print("Q: '%s'" % q)
        print("  content_type=%s  identity=%s" % (ct, ident))


if __name__ == "__main__":
    main()
